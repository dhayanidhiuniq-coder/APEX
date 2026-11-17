"""Tests for the lazy asynchronous engine and session lifecycle."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from apex_backend.core.config import get_settings
from apex_backend.db import session as db_session
from apex_backend.db.config import DatabaseConfigurationError
from apex_backend.db.session import (
    DatabaseLifecycleError,
    DatabaseLoopMismatchError,
    DatabaseNotConfiguredError,
    DatabaseShuttingDownError,
    DatabaseWorkNotRegisteredError,
    dispose_engine,
    get_db_session,
    get_engine,
    get_session_factory,
)

DUMMY_USER = "phase1b-user"
DUMMY_PASSWORD = "phase1b-dummy-password"
DUMMY_HOST = "db.phase1b.invalid"
VALID_URL = (
    f"postgresql+psycopg://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex"
)
SENSITIVE_PARTS = (DUMMY_USER, DUMMY_PASSWORD, DUMMY_HOST)


def _configure(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()


async def _reset_state() -> None:
    await db_session._reset_database_for_testing()


async def _tracked_get_engine() -> Any:
    async with db_session._register_db_work():
        return await get_engine()


async def _tracked_get_factory() -> Any:
    async with db_session._register_db_work():
        return await get_session_factory()


@pytest.fixture(autouse=True)
async def _clean_engine_state() -> AsyncIterator[None]:
    await _reset_state()
    yield
    await _reset_state()


class FakeAsyncSession:
    """Records lifecycle calls without touching a database."""

    def __init__(self) -> None:
        self.commits = 0
        self.flushes = 0
        self.rollbacks = 0
        self.closes = 0

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        self.flushes += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def close(self) -> None:
        self.closes += 1


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


pytestmark = pytest.mark.anyio


async def test_get_engine_fails_before_creation_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "")

    def _unexpected_create(*_: Any, **__: Any) -> None:
        raise AssertionError("engine creation must not be attempted")

    monkeypatch.setattr(db_session, "create_async_engine", _unexpected_create)

    async with db_session._register_db_work():
        with pytest.raises(DatabaseNotConfiguredError):
            await get_engine()

    assert db_session._engine is None
    assert db_session._session_factory is None


async def test_engine_and_factory_are_lazy_singletons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)
    created: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    real_create_async_engine = db_session.create_async_engine

    def _spy(*args: Any, **kwargs: Any) -> Any:
        created.append((args, kwargs))
        return real_create_async_engine(*args, **kwargs)

    monkeypatch.setattr(db_session, "create_async_engine", _spy)

    assert db_session._engine is None
    assert db_session._session_factory is None

    async with db_session._register_db_work():
        first_engine = await get_engine()
        second_engine = await get_engine()
        first_factory = await get_session_factory()
        second_factory = await get_session_factory()

    assert first_engine is second_engine
    assert first_factory is second_factory
    assert len(created) == 1
    assert created[0][0] == (VALID_URL,)


async def test_engine_uses_async_postgresql_dialect_and_pool_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    async with db_session._register_db_work():
        engine = await get_engine()

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert engine.echo is False
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 10
    assert engine.pool._timeout == 30
    assert engine.pool._recycle == 1800
    assert engine.pool._pre_ping is True


async def test_session_factory_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    async with db_session._register_db_work():
        engine = await get_engine()
        factory = await get_session_factory()

    assert factory.class_ is AsyncSession
    assert factory.kw["bind"] is engine
    assert factory.kw["expire_on_commit"] is False
    assert factory.kw["autoflush"] is False


async def test_concurrent_lazy_initialization_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    engines = await asyncio.gather(*(_tracked_get_engine() for _ in range(20)))
    factories = await asyncio.gather(*(_tracked_get_factory() for _ in range(20)))

    assert all(engine is engines[0] for engine in engines)
    assert all(factory is factories[0] for factory in factories)


async def test_cross_loop_calls_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    def _worker() -> Any:
        async def _use() -> Any:
            async with db_session._register_db_work():
                return await get_engine()

        return asyncio.run(_use())

    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(DatabaseLoopMismatchError):
            executor.submit(_worker).result()

    assert db_session._engine is None


async def test_direct_helpers_cannot_bypass_tracker() -> None:
    with pytest.raises(DatabaseWorkNotRegisteredError):
        await get_engine()
    with pytest.raises(DatabaseWorkNotRegisteredError):
        await get_session_factory()
    with pytest.raises(DatabaseLifecycleError):
        await dispose_engine()


async def test_child_task_cannot_reuse_parent_registration() -> None:
    started = asyncio.Event()
    errors: list[BaseException] = []

    async def _child() -> None:
        await started.wait()
        try:
            await get_engine()
        except BaseException as exc:
            errors.append(exc)

    async with db_session._register_db_work():
        child = asyncio.create_task(_child())
        started.set()
        db_session.begin_database_shutdown()
        await child
        assert db_session.active_database_work_count() == 1

    assert len(errors) == 1
    assert isinstance(errors[0], DatabaseWorkNotRegisteredError)
    assert db_session.active_database_work_count() == 0
    db_session.mark_database_shutdown_complete()


async def test_registration_after_shutdown_is_rejected() -> None:
    db_session.begin_database_shutdown()
    with pytest.raises(DatabaseShuttingDownError):
        async with db_session._register_db_work():
            pass
    db_session.mark_database_shutdown_complete()


async def test_dispose_engine_rejected_with_active_work() -> None:
    async with db_session._register_db_work():
        permit = db_session.begin_database_shutdown()
        with pytest.raises(DatabaseLifecycleError):
            await dispose_engine(_permit=permit)
    db_session.mark_database_shutdown_complete()


async def test_fresh_lifespan_cannot_reopen_gate_during_drain() -> None:
    db_session.begin_database_shutdown()
    with pytest.raises(DatabaseLifecycleError):
        db_session.reset_database_shutdown_state()
    db_session.mark_database_shutdown_complete()


async def test_dispose_engine_clears_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FakeEngine:
        def __init__(self) -> None:
            self.dispose_calls = 0

        async def dispose(self) -> None:
            self.dispose_calls += 1

    fake_engine = FakeEngine()
    monkeypatch.setattr(
        db_session, "create_async_engine", lambda *_, **__: fake_engine
    )
    async with db_session._register_db_work():
        engine = await get_engine()
        factory = await get_session_factory()

    permit = db_session.begin_database_shutdown()
    await dispose_engine(_permit=permit)

    assert engine is fake_engine
    assert factory.kw["bind"] is engine
    assert fake_engine.dispose_calls == 1
    assert db_session._engine is None
    assert db_session._session_factory is None

    with pytest.raises(DatabaseLifecycleError):
        await dispose_engine(_permit=permit)
    assert fake_engine.dispose_calls == 1


async def test_dispose_engine_clears_state_when_disposal_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FailingEngine:
        async def dispose(self) -> None:
            raise RuntimeError("disposal failed")

    fake_engine = FailingEngine()
    monkeypatch.setattr(
        db_session, "create_async_engine", lambda *_, **__: fake_engine
    )
    async with db_session._register_db_work():
        engine = await get_engine()
        factory = await get_session_factory()

    permit = db_session.begin_database_shutdown()
    with pytest.raises(RuntimeError, match="disposal failed"):
        await dispose_engine(_permit=permit)

    assert engine is fake_engine
    assert factory.kw["bind"] is engine
    assert db_session._engine is None
    assert db_session._session_factory is None

    with pytest.raises(DatabaseLifecycleError):
        await dispose_engine(_permit=permit)


async def test_permit_from_previous_lifespan_is_rejected_after_reset() -> None:
    permit = db_session.begin_database_shutdown()
    db_session.mark_database_shutdown_complete()
    db_session.reset_database_shutdown_state()

    assert db_session._lifecycle_phase == db_session._PHASE_OPEN
    with pytest.raises(DatabaseLifecycleError):
        await dispose_engine(_permit=permit)

    new_permit = db_session.begin_database_shutdown()
    assert new_permit is not permit
    db_session.mark_database_shutdown_complete()


async def test_real_engine_is_disposed_and_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)
    async with db_session._register_db_work():
        engine = await get_engine()

    permit = db_session.begin_database_shutdown()
    await dispose_engine(_permit=permit)
    db_session.reset_database_shutdown_state()

    async with db_session._register_db_work():
        replacement = await get_engine()

    assert replacement is not engine
    assert db_session._engine is replacement


async def test_engine_creation_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    def _fail(*_: Any, **__: Any) -> None:
        raise ValueError(f"driver rejected {VALID_URL}")

    monkeypatch.setattr(db_session, "create_async_engine", _fail)

    async with db_session._register_db_work():
        with pytest.raises(DatabaseConfigurationError) as error:
            await get_engine()

    message = str(error.value)
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert db_session._engine is None


async def test_db_session_normal_cleanup_does_not_commit_or_flush(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeAsyncSession()

    async def _fake_factory() -> Any:
        return lambda: fake_session

    monkeypatch.setattr(db_session, "get_session_factory", _fake_factory)

    generator = db_session.get_db_session()
    yielded = await anext(generator)

    assert yielded is fake_session
    assert fake_session.commits == 0
    assert fake_session.flushes == 0

    with pytest.raises(StopAsyncIteration):
        await anext(generator)

    assert fake_session.closes == 1
    assert fake_session.rollbacks == 0
    assert fake_session.commits == 0
    assert fake_session.flushes == 0


async def test_db_session_rolls_back_and_closes_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeAsyncSession()

    async def _fake_factory() -> Any:
        return lambda: fake_session

    monkeypatch.setattr(db_session, "get_session_factory", _fake_factory)

    generator = get_db_session()
    assert await anext(generator) is fake_session

    with pytest.raises(RuntimeError, match="caller failed"):
        await generator.athrow(RuntimeError("caller failed"))

    assert fake_session.rollbacks == 1
    assert fake_session.closes == 1
    assert fake_session.commits == 0
    assert fake_session.flushes == 0


async def test_cleanup_failures_do_not_mask_body_exception(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingCleanupSession(FakeAsyncSession):
        async def rollback(self) -> None:
            self.rollbacks += 1
            raise ValueError("rollback failed")

        async def close(self) -> None:
            self.closes += 1
            raise ValueError("close failed")

    fake_session = FailingCleanupSession()

    async def _fake_factory() -> Any:
        return lambda: fake_session

    monkeypatch.setattr(db_session, "get_session_factory", _fake_factory)

    generator = get_db_session()
    assert await anext(generator) is fake_session

    with caplog.at_level(logging.WARNING, logger=db_session.__name__):
        with pytest.raises(RuntimeError, match="caller failed"):
            await generator.athrow(RuntimeError("caller failed"))

    assert fake_session.rollbacks == 1
    assert fake_session.closes == 1
    assert db_session._SESSION_CLOSE_FAILED_MESSAGE in caplog.text
    assert db_session.active_database_work_count() == 0


async def test_close_failure_without_body_error_is_reported(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FailingCloseSession(FakeAsyncSession):
        async def close(self) -> None:
            self.closes += 1
            raise ValueError("close failed")

    fake_session = FailingCloseSession()

    async def _fake_factory() -> Any:
        return lambda: fake_session

    monkeypatch.setattr(db_session, "get_session_factory", _fake_factory)

    generator = get_db_session()
    await anext(generator)

    with caplog.at_level(logging.WARNING, logger=db_session.__name__):
        with pytest.raises(ValueError, match="close failed"):
            await anext(generator)

    assert fake_session.closes == 1
    assert db_session._SESSION_CLOSE_FAILED_MESSAGE in caplog.text
    assert db_session.active_database_work_count() == 0


async def test_db_session_closes_without_committing_when_closed_early(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = FakeAsyncSession()

    async def _fake_factory() -> Any:
        return lambda: fake_session

    monkeypatch.setattr(db_session, "get_session_factory", _fake_factory)

    generator = get_db_session()
    await anext(generator)
    await generator.aclose()

    assert fake_session.commits == 0
    assert fake_session.flushes == 0
    assert fake_session.closes == 1


async def test_app_import_and_health_do_not_initialize_engine(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "")

    assert db_session._engine is None

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert db_session._engine is None
