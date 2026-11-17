"""Lazy asynchronous database engine and session lifecycle.

No engine is created at import time. The first call to :func:`get_engine`
creates the singleton engine, and nothing here connects until SQLAlchemy is
actually asked to execute a statement.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import (
    DEFAULT_MAX_OVERFLOW,
    DEFAULT_POOL_RECYCLE,
    DEFAULT_POOL_SIZE,
    DEFAULT_POOL_TIMEOUT,
    DatabaseConfigurationError,
    get_database_config,
)

_ENGINE_CREATION_ERROR = "Unable to create the database engine; check DATABASE_URL."
_DATABASE_SHUTTING_DOWN_MESSAGE = (
    "Database shutdown is in progress; retry the request later."
)
_SESSION_CLOSE_FAILED_MESSAGE = "Database session close failed during cleanup."

logger = logging.getLogger(__name__)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database feature is requested without ``DATABASE_URL``."""


class DatabaseShuttingDownError(RuntimeError):
    """Raised when new database work is requested during application shutdown."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# The lock protects cached state and prevents duplicate engine construction.
# Configuration and .env/file reads happen before the lock. Engine construction
# is synchronous and performs no database or network I/O.
_state_lock = threading.Lock()
_shutting_down = False
_active_db_work = 0
_registered_db_work: ContextVar[bool] = ContextVar(
    "apex_registered_db_work", default=False
)


def begin_database_shutdown() -> None:
    """Atomically prevent new DB work from registering."""
    global _shutting_down

    with _state_lock:
        _shutting_down = True


def reset_database_shutdown_state() -> None:
    """Reopen DB work when a new application lifespan starts."""
    global _shutting_down

    with _state_lock:
        if _active_db_work:
            raise RuntimeError("Cannot start database lifecycle with active work.")
        _shutting_down = False


def _ensure_database_available() -> None:
    with _state_lock:
        if _shutting_down and not _registered_db_work.get():
            raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)


@asynccontextmanager
async def _register_db_work() -> AsyncIterator[None]:
    """Register DB-capable work before its first await and release it last."""
    global _active_db_work

    with _state_lock:
        if _shutting_down:
            raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)
        _active_db_work += 1

    token = _registered_db_work.set(True)
    try:
        yield
    finally:
        _registered_db_work.reset(token)
        with _state_lock:
            _active_db_work -= 1


def active_database_work_count() -> int:
    """Return the number of registered DB-capable operations."""
    with _state_lock:
        return _active_db_work


async def wait_for_database_work(timeout: float) -> bool:
    """Wait up to ``timeout`` seconds; return whether all DB work drained."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while active_database_work_count():
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(0.05, remaining))
    return True


async def get_engine() -> AsyncEngine:
    """Return the lazy singleton asynchronous engine.

    Raises:
        DatabaseNotConfiguredError: ``DATABASE_URL`` is empty.
        DatabaseConfigurationError: the URL is invalid or engine creation fails.
    """
    global _engine

    _ensure_database_available()
    engine = _engine
    if engine is not None:
        return engine

    config = get_database_config()
    if not config.is_configured:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not configured; database features are disabled."
        )

    with _state_lock:
        if _shutting_down and not _registered_db_work.get():
            raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)
        if _engine is not None:
            return _engine

        creation_failed = False
        try:
            engine = create_async_engine(
                config.url,
                echo=False,
                pool_pre_ping=True,
                pool_size=DEFAULT_POOL_SIZE,
                max_overflow=DEFAULT_MAX_OVERFLOW,
                pool_timeout=DEFAULT_POOL_TIMEOUT,
                pool_recycle=DEFAULT_POOL_RECYCLE,
            )
        except Exception:
            creation_failed = True

        if creation_failed:
            raise DatabaseConfigurationError(_ENGINE_CREATION_ERROR)

        _engine = engine
        return engine


async def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the lazy singleton session factory.

    The factory never commits or flushes automatically. Callers own their
    transactions.
    """
    global _session_factory

    _ensure_database_available()
    factory = _session_factory
    if factory is not None:
        return factory

    while True:
        engine = await get_engine()

        with _state_lock:
            if _shutting_down and not _registered_db_work.get():
                raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)
            if _session_factory is not None:
                return _session_factory
            if _engine is not engine:
                # The engine was disposed while this call was waiting. Retry
                # against the current engine.
                continue

            _session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session with explicit cleanup.

    The caller owns the transaction. Nothing is committed or flushed here; an
    exception rolls the transaction back, and the session is always closed.
    Cleanup failures are logged with static messages and never replace a
    primary error raised by the request body.
    """
    async with _register_db_work():
        factory = await get_session_factory()
        session = factory()
        primary_exc: BaseException | None = None

        try:
            try:
                yield session
            except BaseException as exc:
                primary_exc = exc
                with suppress(Exception):
                    await session.rollback()
        finally:
            try:
                await session.close()
            except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                logger.warning(_SESSION_CLOSE_FAILED_MESSAGE)
                if primary_exc is None:
                    raise

        if primary_exc is not None:
            raise primary_exc


async def dispose_engine() -> None:
    """Dispose the cached engine and clear all lazy state.

    Safe to call when no engine has been created. Primarily intended for
    application shutdown and tests. This function is not safe to call while
    sessions or requests are actively using the engine; callers must quiesce
    active work first.
    """
    global _engine, _session_factory

    with _state_lock:
        engine = _engine
        _engine = None
        _session_factory = None

    if engine is not None:
        await engine.dispose()
