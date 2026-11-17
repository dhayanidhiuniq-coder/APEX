"""Tests for the lazy asynchronous engine and session lifecycle."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
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
    DatabaseNotConfiguredError,
    dispose_engine,
    get_db_session,
    get_engine,
    get_session_factory,
    reset_database_shutdown_state,
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


@pytest.fixture(autouse=True)
async def _clean_engine_state() -> AsyncIterator[None]:
    reset_database_shutdown_state()
    await dispose_engine()
    yield
    await dispose_engine()
    reset_database_shutdown_state()


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

    engines = await asyncio.gather(*(get_engine() for _ in range(20)))
    factories = await asyncio.gather(*(get_session_factory() for _ in range(20)))

    assert all(engine is engines[0] for engine in engines)
    assert all(factory is factories[0] for factory in factories)


async def test_threaded_lazy_initialization_creates_one_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FakeEngine:
        async def dispose(self) -> None:
            pass

    fake_engine = FakeEngine()
    factory_calls = 0
    factory_lock = threading.Lock()

    def _create_engine(*_: Any, **__: Any) -> Any:
        nonlocal factory_calls
        with factory_lock:
            factory_calls += 1
        time.sleep(0.05)
        return fake_engine

    monkeypatch.setattr(db_session, "create_async_engine", _create_engine)

    worker_count = 12
    barrier = threading.Barrier(worker_count)

    def _worker() -> Any:
        barrier.wait(timeout=5)
        return asyncio.run(get_engine())

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        engines = list(executor.map(lambda _: _worker(), range(worker_count)))

    assert factory_calls == 1
    assert all(engine is fake_engine for engine in engines)
    assert db_session._engine is fake_engine


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
    engine = await get_engine()
    factory = await get_session_factory()

    await dispose_engine()

    assert engine is fake_engine
    assert factory.kw["bind"] is engine
    assert fake_engine.dispose_calls == 1
    assert db_session._engine is None
    assert db_session._session_factory is None

    await dispose_engine()
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
    engine = await get_engine()
    factory = await get_session_factory()

    with pytest.raises(RuntimeError, match="disposal failed"):
        await dispose_engine()

    assert engine is fake_engine
    assert factory.kw["bind"] is engine
    assert db_session._engine is None
    assert db_session._session_factory is None


async def test_real_engine_is_disposed_and_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)
    engine = await get_engine()

    await dispose_engine()

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
