"""Lazy asynchronous database engine and session lifecycle.

No engine is created at import time. The first call to :func:`get_engine`
inside a registered :func:`get_db_session` creates the singleton engine, and
nothing here connects until SQLAlchemy is actually asked to execute a
statement.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

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
_DB_WORK_NOT_REGISTERED_MESSAGE = (
    "Database helpers require an active get_db_session() registration."
)
_DISPOSAL_NOT_AUTHORIZED_MESSAGE = (
    "Engine disposal is only allowed during application shutdown."
)
_DISPOSAL_ACTIVE_WORK_MESSAGE = (
    "Engine disposal cannot run while database work is active."
)
_DISPOSAL_PHASE_MESSAGE = "Engine disposal is not allowed in the current lifecycle phase."
_LOOP_MISMATCH_MESSAGE = "Database lifecycle calls must use the owning event loop."
_NO_RUNNING_LOOP_MESSAGE = "Database lifecycle calls require a running event loop."
_NO_TASK_MESSAGE = "Database work must run inside an asyncio task."
_LIFECYCLE_BUSY_MESSAGE = (
    "Cannot start database lifecycle while shutdown is still in progress."
)
_LIFECYCLE_CLOSED_MESSAGE = "Database lifecycle is already closed."

_PHASE_OPEN = "OPEN"
_PHASE_DRAINING = "DRAINING"
_PHASE_DISPOSING = "DISPOSING"
_PHASE_CLOSED = "CLOSED"

logger = logging.getLogger(__name__)


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a database feature is requested without ``DATABASE_URL``."""


class DatabaseLifecycleError(RuntimeError):
    """Raised when the database lifecycle state forbids an operation."""


class DatabaseWorkNotRegisteredError(DatabaseLifecycleError):
    """Raised when a DB helper is used outside tracked ``get_db_session`` work."""


class DatabaseLoopMismatchError(DatabaseLifecycleError):
    """Raised when a DB lifecycle operation uses a non-owning event loop."""


class DatabaseShuttingDownError(DatabaseLifecycleError):
    """Raised when new database work is requested during application shutdown."""


@dataclass(frozen=True)
class _WorkRegistration:
    token: object
    task: asyncio.Task[Any]


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

# The lock protects cached state and prevents duplicate engine construction.
# Configuration and .env/file reads happen before the lock. Engine construction
# is synchronous and performs no database or network I/O.
_state_lock = threading.Lock()
_shutting_down = False
_active_db_work = 0
_lifecycle_phase = _PHASE_OPEN
_owner_loop: asyncio.AbstractEventLoop | None = None
_disposal_token: object | None = None
_work_registration: ContextVar[_WorkRegistration | None] = ContextVar(
    "apex_db_work_registration", default=None
)


def _running_loop() -> asyncio.AbstractEventLoop:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        raise DatabaseLifecycleError(_NO_RUNNING_LOOP_MESSAGE) from None


def _check_owner_loop() -> None:
    loop = _running_loop()
    with _state_lock:
        owner = _owner_loop
    if owner is None or owner is not loop:
        raise DatabaseLoopMismatchError(_LOOP_MISMATCH_MESSAGE)


def _check_registration_unlocked() -> None:
    task = asyncio.current_task()
    registration = _work_registration.get()
    if task is None or registration is None or registration.task is not task:
        raise DatabaseWorkNotRegisteredError(_DB_WORK_NOT_REGISTERED_MESSAGE)
    if _lifecycle_phase not in (_PHASE_OPEN, _PHASE_DRAINING):
        raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)


def _require_registered_work() -> None:
    _check_owner_loop()
    with _state_lock:
        _check_registration_unlocked()


def begin_database_shutdown() -> object:
    """Atomically close admission and return the one disposal permit."""
    global _shutting_down, _lifecycle_phase, _disposal_token

    _check_owner_loop()
    with _state_lock:
        if _lifecycle_phase == _PHASE_OPEN:
            _shutting_down = True
            _lifecycle_phase = _PHASE_DRAINING
            _disposal_token = object()
            return _disposal_token
        if _disposal_token is not None:
            return _disposal_token
        raise DatabaseLifecycleError(_LIFECYCLE_CLOSED_MESSAGE)


def mark_database_shutdown_complete() -> None:
    """Close the lifecycle after a drain timeout or a completed disposal."""
    global _lifecycle_phase, _disposal_token

    _check_owner_loop()
    with _state_lock:
        if _lifecycle_phase in (_PHASE_DRAINING, _PHASE_DISPOSING):
            _lifecycle_phase = _PHASE_CLOSED
            _disposal_token = None


def reset_database_shutdown_state() -> None:
    """Reopen DB work for a new application lifespan."""
    global _shutting_down, _owner_loop, _lifecycle_phase, _disposal_token

    loop = _running_loop()
    with _state_lock:
        if _lifecycle_phase in (_PHASE_DRAINING, _PHASE_DISPOSING):
            raise DatabaseLifecycleError(_LIFECYCLE_BUSY_MESSAGE)
        if _active_db_work:
            raise RuntimeError("Cannot start database lifecycle with active work.")
        _owner_loop = loop
        _shutting_down = False
        _lifecycle_phase = _PHASE_OPEN
        _disposal_token = None


async def _reset_database_for_testing() -> None:
    """Fail-loud full reset for test fixtures only; not part of the public API.

    It forcibly rebinds the owner loop to the calling loop so each test starts
    from an isolated lifecycle. It refuses to run while work is active.
    """
    global _engine, _session_factory, _owner_loop
    global _shutting_down, _lifecycle_phase, _disposal_token

    loop = _running_loop()
    with _state_lock:
        if _active_db_work:
            raise RuntimeError("Cannot reset database state with active work.")
        engine = _engine
        _engine = None
        _session_factory = None
        _owner_loop = loop
        _shutting_down = False
        _lifecycle_phase = _PHASE_OPEN
        _disposal_token = None

    if engine is not None:
        await engine.dispose()


@asynccontextmanager
async def _register_db_work() -> AsyncIterator[None]:
    """Register DB-capable work before its first await and release it last.

    Registration is bound to the current task. An inherited context in a child
    task cannot satisfy the registration check.
    """
    global _active_db_work

    _check_owner_loop()
    task = asyncio.current_task()
    if task is None:
        raise DatabaseLifecycleError(_NO_TASK_MESSAGE)

    with _state_lock:
        if _lifecycle_phase != _PHASE_OPEN:
            raise DatabaseShuttingDownError(_DATABASE_SHUTTING_DOWN_MESSAGE)
        registration = _WorkRegistration(token=object(), task=task)
        _active_db_work += 1

    token = _work_registration.set(registration)
    try:
        yield
    finally:
        _work_registration.reset(token)
        with _state_lock:
            _active_db_work -= 1


def active_database_work_count() -> int:
    """Return the number of registered DB-capable operations."""
    with _state_lock:
        return _active_db_work


async def wait_for_database_work(timeout: float) -> bool:
    """Wait up to ``timeout`` seconds; return whether all DB work drained."""
    _check_owner_loop()
    loop = _running_loop()
    deadline = loop.time() + timeout
    while active_database_work_count():
        remaining = deadline - loop.time()
        if remaining <= 0:
            return False
        await asyncio.sleep(min(0.05, remaining))
    return True


async def get_engine() -> AsyncEngine:
    """Return the lazy singleton asynchronous engine.

    Requires an active ``get_db_session()`` registration on the owning loop.

    Raises:
        DatabaseNotConfiguredError: ``DATABASE_URL`` is empty.
        DatabaseConfigurationError: the URL is invalid or engine creation fails.
        DatabaseWorkNotRegisteredError: called outside tracked session work.
        DatabaseLoopMismatchError: called from a non-owning event loop.
    """
    global _engine

    _require_registered_work()
    engine = _engine
    if engine is not None:
        return engine

    config = get_database_config()
    if not config.is_configured:
        raise DatabaseNotConfiguredError(
            "DATABASE_URL is not configured; database features are disabled."
        )

    with _state_lock:
        _check_registration_unlocked()
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
    """Return the lazy singleton session factory for registered work.

    The factory never commits or flushes automatically. Callers own their
    transactions.
    """
    global _session_factory

    _require_registered_work()
    factory = _session_factory
    if factory is not None:
        return factory

    while True:
        engine = await get_engine()

        with _state_lock:
            _check_registration_unlocked()
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


async def dispose_engine(*, _permit: object | None = None) -> None:
    """Dispose the cached engine during application shutdown only.

    The permit is returned by :func:`begin_database_shutdown` and is single-use.
    Direct calls without the permit are rejected so DB use cannot bypass the
    tracker. State is cleared before the awaited disposal and is never retried
    automatically.
    """
    global _engine, _session_factory, _lifecycle_phase, _disposal_token

    _check_owner_loop()
    with _state_lock:
        if _permit is None or _permit is not _disposal_token:
            raise DatabaseLifecycleError(_DISPOSAL_NOT_AUTHORIZED_MESSAGE)
        if _active_db_work:
            raise DatabaseLifecycleError(_DISPOSAL_ACTIVE_WORK_MESSAGE)
        if _lifecycle_phase != _PHASE_DRAINING:
            raise DatabaseLifecycleError(_DISPOSAL_PHASE_MESSAGE)
        engine = _engine
        _engine = None
        _session_factory = None
        _lifecycle_phase = _PHASE_DISPOSING

    try:
        if engine is not None:
            await engine.dispose()
    finally:
        with _state_lock:
            _lifecycle_phase = _PHASE_CLOSED
            _disposal_token = None
