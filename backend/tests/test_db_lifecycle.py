"""Tests for database startup and shutdown lifecycle hooks."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apex_backend import create_app
from apex_backend.core.config import get_settings
from apex_backend.db import lifecycle as db_lifecycle
from apex_backend.db import session as db_session
from apex_backend.db.lifecycle import (
    DATABASE_CONFIGURATION_UNAVAILABLE_MESSAGE,
    DATABASE_DISABLED_MESSAGE,
    DATABASE_ENABLED_MESSAGE,
    DATABASE_SHUTDOWN_FAILED_MESSAGE,
)
from apex_backend.db.session import DatabaseLifecycleError, DatabaseLoopMismatchError

DUMMY_USER = "phase1c-user"
DUMMY_PASSWORD = "phase1c-dummy-password"
DUMMY_HOST = "db.phase1c.invalid"
VALID_URL = (
    f"postgresql+psycopg://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex"
)
INVALID_URL = (
    f"postgresql://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex"
)
SENSITIVE_PARTS = (DUMMY_USER, DUMMY_PASSWORD, DUMMY_HOST)


def _configure(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clean_engine_state() -> Iterator[None]:
    asyncio.run(db_session._reset_database_for_testing())
    yield
    asyncio.run(db_session._reset_database_for_testing())


@pytest.fixture(autouse=True)
def _enable_lifecycle_logging() -> Iterator[None]:
    """Keep this module independent of Alembic's global logging configuration."""
    lifecycle_logger = logging.getLogger(db_lifecycle.__name__)
    was_disabled = lifecycle_logger.disabled
    lifecycle_logger.disabled = False
    yield
    lifecycle_logger.disabled = was_disabled


@pytest.mark.anyio
async def test_startup_without_database_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch, "")

    with caplog.at_level(logging.INFO, logger=db_lifecycle.__name__):
        await db_lifecycle.database_startup()

    assert DATABASE_DISABLED_MESSAGE in caplog.text
    assert db_session._engine is None
    assert db_session._session_factory is None


@pytest.mark.anyio
async def test_startup_with_valid_database_does_not_create_engine(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch, VALID_URL)

    def _unexpected_create(*_: Any, **__: Any) -> None:
        raise AssertionError("startup must not create an engine")

    monkeypatch.setattr(db_session, "create_async_engine", _unexpected_create)

    with caplog.at_level(logging.INFO, logger=db_lifecycle.__name__):
        await db_lifecycle.database_startup()

    assert DATABASE_ENABLED_MESSAGE in caplog.text
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in caplog.text
    assert db_session._engine is None
    assert db_session._session_factory is None


@pytest.mark.anyio
async def test_startup_with_invalid_database_warns_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch, INVALID_URL)

    with caplog.at_level(logging.WARNING, logger=db_lifecycle.__name__):
        await db_lifecycle.database_startup()

    assert DATABASE_CONFIGURATION_UNAVAILABLE_MESSAGE in caplog.text
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in caplog.text
    assert db_session._engine is None
    assert db_session._session_factory is None


def test_lifespan_client_starts_without_database(
    lifespan_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _unexpected_create(*_: Any, **__: Any) -> None:
        raise AssertionError("lifespan must not create an engine")

    monkeypatch.setattr(db_session, "create_async_engine", _unexpected_create)

    response = lifespan_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert db_session._engine is None


def test_lifespan_with_valid_database_starts_without_connecting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    def _unexpected_create(*_: Any, **__: Any) -> None:
        raise AssertionError("startup must not create an engine")

    monkeypatch.setattr(db_session, "create_async_engine", _unexpected_create)

    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert db_session._engine is None

    assert db_session._engine is None


def test_lifespan_with_invalid_database_starts_with_sanitized_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _configure(monkeypatch, INVALID_URL)

    with caplog.at_level(logging.WARNING, logger=db_lifecycle.__name__):
        with TestClient(create_app()) as client:
            response = client.get("/health")

            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    assert DATABASE_CONFIGURATION_UNAVAILABLE_MESSAGE in caplog.text
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in caplog.text
    assert db_session._engine is None


def test_lifespan_shutdown_calls_dispose_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "")
    calls: list[bool] = []

    async def _fake_dispose(*, _permit: object | None = None) -> None:
        calls.append(True)

    monkeypatch.setattr(db_lifecycle, "dispose_engine", _fake_dispose)

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert calls == []

    assert calls == [True]


@pytest.mark.anyio
async def test_shutdown_calls_dispose_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    async def _fake_dispose(*, _permit: object | None = None) -> None:
        calls.append(True)

    monkeypatch.setattr(db_lifecycle, "dispose_engine", _fake_dispose)

    await db_lifecycle.database_startup()
    await db_lifecycle.database_shutdown()

    assert calls == [True]


@pytest.mark.anyio
async def test_shutdown_sanitizes_ordinary_disposal_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _fail_dispose(*, _permit: object | None = None) -> None:
        raise RuntimeError(f"disposal failed for {VALID_URL}")

    monkeypatch.setattr(db_lifecycle, "dispose_engine", _fail_dispose)

    await db_lifecycle.database_startup()
    with caplog.at_level(logging.WARNING, logger=db_lifecycle.__name__):
        await db_lifecycle.database_shutdown()

    assert DATABASE_SHUTDOWN_FAILED_MESSAGE in caplog.text
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in caplog.text


@pytest.mark.anyio
@pytest.mark.parametrize("control_exception", [KeyboardInterrupt, SystemExit])
async def test_shutdown_does_not_swallow_control_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    control_exception: type[BaseException],
) -> None:
    async def _fail_dispose(*, _permit: object | None = None) -> None:
        raise control_exception("control flow stop")

    monkeypatch.setattr(db_lifecycle, "dispose_engine", _fail_dispose)

    await db_lifecycle.database_startup()
    with pytest.raises(control_exception):
        await db_lifecycle.database_shutdown()


@pytest.mark.anyio
async def test_second_lifespan_cannot_reopen_gate_during_drain() -> None:
    await db_lifecycle.database_startup()
    db_session.begin_database_shutdown()

    with pytest.raises(DatabaseLifecycleError):
        await db_lifecycle.database_startup()

    db_session.mark_database_shutdown_complete()


@pytest.mark.anyio
async def test_shutdown_from_other_loop_is_rejected() -> None:
    await db_lifecycle.database_startup()

    def _worker() -> None:
        asyncio.run(db_lifecycle.database_shutdown())

    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(DatabaseLoopMismatchError):
            executor.submit(_worker).result()

    db_session.mark_database_shutdown_complete()


@pytest.mark.anyio
async def test_drain_timeout_closes_lifecycle_and_invalidates_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await db_lifecycle.database_startup()
    monkeypatch.setattr(db_lifecycle, "DATABASE_DRAIN_TIMEOUT_SECONDS", 0.0)

    async with db_session._register_db_work():
        permit = db_session.begin_database_shutdown()
        await db_lifecycle.database_shutdown()

    assert db_session._lifecycle_phase == db_session._PHASE_CLOSED
    assert db_session._disposal_token is None
    with pytest.raises(DatabaseLifecycleError):
        await db_session.dispose_engine(_permit=permit)


@pytest.mark.anyio
async def test_drain_cancellation_closes_lifecycle_and_invalidates_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await db_lifecycle.database_startup()
    started = asyncio.Event()

    async def _blocking_wait(_: float) -> bool:
        started.set()
        await asyncio.Event().wait()
        return True

    monkeypatch.setattr(db_lifecycle, "wait_for_database_work", _blocking_wait)

    permit = db_session.begin_database_shutdown()
    shutdown = asyncio.create_task(db_lifecycle.database_shutdown())
    await started.wait()
    shutdown.cancel()

    with pytest.raises(asyncio.CancelledError):
        await shutdown

    assert db_session._lifecycle_phase == db_session._PHASE_CLOSED
    assert db_session._disposal_token is None
    with pytest.raises(DatabaseLifecycleError):
        await db_session.dispose_engine(_permit=permit)

    await db_lifecycle.database_startup()
    assert db_session._lifecycle_phase == db_session._PHASE_OPEN


@pytest.mark.anyio
async def test_disposal_cancellation_closes_lifecycle_and_invalidates_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class BlockingEngine:
        def __init__(self) -> None:
            self.started = asyncio.Event()

        async def dispose(self) -> None:
            self.started.set()
            await asyncio.Event().wait()

    engine = BlockingEngine()
    monkeypatch.setattr(db_session, "create_async_engine", lambda *_, **__: engine)

    await db_lifecycle.database_startup()
    async with db_session._register_db_work():
        await db_session.get_engine()

    permit = db_session.begin_database_shutdown()
    shutdown = asyncio.create_task(db_lifecycle.database_shutdown())
    await engine.started.wait()
    shutdown.cancel()

    with pytest.raises(asyncio.CancelledError):
        await shutdown

    assert db_session._lifecycle_phase == db_session._PHASE_CLOSED
    assert db_session._disposal_token is None
    assert db_session._engine is None
    with pytest.raises(DatabaseLifecycleError):
        await db_session.dispose_engine(_permit=permit)
