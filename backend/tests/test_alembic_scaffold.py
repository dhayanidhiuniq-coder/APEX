"""Tests for the independent Alembic scaffold and offline SQL generation."""

from __future__ import annotations

import logging
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy
from alembic import command
from alembic import context as alembic_context
from alembic.config import Config

from apex_backend.core.config import get_settings
from apex_backend.db import session as db_session
from apex_backend.db.config import DatabaseConfigurationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"
ALEMBIC_DIR = BACKEND_ROOT / "alembic"
VERSIONS_DIR = ALEMBIC_DIR / "versions"

DUMMY_USER = "phase1b-user"
DUMMY_PASSWORD = "phase1b-dummy-password"
DUMMY_HOST = "db.phase1b.invalid"
VALID_URL = (
    f"postgresql+psycopg://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex"
)
SENSITIVE_PARTS = (DUMMY_USER, DUMMY_PASSWORD, DUMMY_HOST)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

    # ``fileConfig`` in alembic/env.py disables loggers that are not named in
    # alembic.ini. Re-enable application loggers so a later caplog assertion is
    # not silently affected by test order.
    for logger in logging.Logger.manager.loggerDict.values():
        if isinstance(logger, logging.Logger) and logger.name.startswith(
            "apex_backend"
        ):
            logger.disabled = False


def _configure(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()


def _config() -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    return config


def test_alembic_scaffold_exists() -> None:
    assert ALEMBIC_INI.is_file()
    assert ALEMBIC_DIR.is_dir()
    assert (ALEMBIC_DIR / "env.py").is_file()
    assert (ALEMBIC_DIR / "script.py.mako").is_file()
    assert VERSIONS_DIR.is_dir()
    assert (VERSIONS_DIR / ".gitkeep").is_file()


def test_alembic_script_location_points_at_backend_scaffold() -> None:
    config = _config()

    script_location = config.get_main_option("script_location")

    assert script_location is not None
    assert Path(script_location).resolve() == ALEMBIC_DIR.resolve()


def test_alembic_ini_has_no_database_url() -> None:
    config = _config()

    assert config.get_main_option("sqlalchemy.url") in (None, "")


def test_alembic_ini_has_deterministic_revision_file_template() -> None:
    file_template = _config().get_main_option("file_template")

    assert file_template is not None
    assert "%(rev)s" in file_template
    assert "%(slug)s" in file_template


def test_versions_directory_contains_story_revisions() -> None:
    entries = {path.name for path in VERSIONS_DIR.iterdir()}

    assert ".gitkeep" in entries
    assert any(name.endswith(".py") for name in entries)


def test_offline_upgrade_does_not_require_a_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline SQL generation must work with DATABASE_URL absent."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    def _unexpected_config() -> None:
        raise AssertionError("offline mode must not read database configuration")

    def _unexpected_engine(*_: Any, **__: Any) -> None:
        raise AssertionError("offline mode must not create an async engine")

    def _unexpected_sync_engine(*_: Any, **__: Any) -> None:
        raise AssertionError("offline mode must not create a synchronous engine")

    def _unexpected_connect(*_: Any, **__: Any) -> None:
        raise AssertionError("offline mode must not open a network connection")

    monkeypatch.setattr(
        "apex_backend.db.config.get_database_config", _unexpected_config
    )
    monkeypatch.setattr(db_session, "create_async_engine", _unexpected_engine)
    monkeypatch.setattr(sqlalchemy, "create_engine", _unexpected_sync_engine)
    monkeypatch.setattr(socket.socket, "connect", _unexpected_connect)

    command.upgrade(_config(), "head", sql=True)


def test_online_connection_failure_is_sanitized_and_disposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FakeEngine:
        def __init__(self) -> None:
            self.dispose_calls = 0

        def connect(self) -> None:
            raise RuntimeError(f"connection failed for {VALID_URL}")

        def dispose(self) -> None:
            self.dispose_calls += 1

    fake_engine = FakeEngine()

    def _unexpected_connect(*_: Any, **__: Any) -> None:
        raise AssertionError("test must not open a network connection")

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_, **__: fake_engine)
    monkeypatch.setattr(socket.socket, "connect", _unexpected_connect)

    with pytest.raises(DatabaseConfigurationError) as error:
        command.current(_config())

    message = str(error.value)
    assert message == (
        "Online database migration failed; check DATABASE_URL "
        "and database availability."
    )
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert fake_engine.dispose_calls == 1


def test_online_configuration_failure_is_sanitized_and_disposed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FakeConnection:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, *_: object) -> bool:
            return False

    class FakeEngine:
        def __init__(self) -> None:
            self.dispose_calls = 0

        def connect(self) -> FakeConnection:
            return FakeConnection()

        def dispose(self) -> None:
            self.dispose_calls += 1

    fake_engine = FakeEngine()

    def _fail_configure(*_: Any, **__: Any) -> None:
        raise RuntimeError(f"configuration failed for {VALID_URL}")

    def _unexpected_connect(*_: Any, **__: Any) -> None:
        raise AssertionError("test must not open a network connection")

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_, **__: fake_engine)
    monkeypatch.setattr(alembic_context, "configure", _fail_configure)
    monkeypatch.setattr(socket.socket, "connect", _unexpected_connect)

    with pytest.raises(DatabaseConfigurationError) as error:
        command.current(_config())

    message = str(error.value)
    assert message == (
        "Online database migration failed; check DATABASE_URL "
        "and database availability."
    )
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message
    assert error.value.__cause__ is None
    assert error.value.__context__ is None
    assert fake_engine.dispose_calls == 1


@pytest.mark.parametrize("control_exception", [KeyboardInterrupt, SystemExit])
def test_cleanup_errors_do_not_mask_control_exceptions(
    monkeypatch: pytest.MonkeyPatch,
    control_exception: type[BaseException],
) -> None:
    _configure(monkeypatch, VALID_URL)

    class FakeEngine:
        def __init__(self) -> None:
            self.dispose_calls = 0

        def connect(self) -> None:
            raise control_exception("control flow stop")

        def dispose(self) -> None:
            self.dispose_calls += 1
            raise RuntimeError(f"cleanup failed for {VALID_URL}")

    fake_engine = FakeEngine()

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_, **__: fake_engine)

    with pytest.raises(control_exception):
        command.current(_config())

    assert fake_engine.dispose_calls == 1
