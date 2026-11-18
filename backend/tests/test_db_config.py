"""Tests for database configuration and credential-safe validation."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import ArgumentError

from apex_backend.core.config import Settings, get_settings
from apex_backend.db import config as db_config
from apex_backend.db.config import (
    SUPPORTED_DATABASE_SCHEME,
    DatabaseConfig,
    DatabaseConfigurationError,
    get_database_config,
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


def test_settings_default_database_url_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == ""


def test_missing_database_url_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "")

    config = get_database_config()

    assert config == DatabaseConfig()
    assert config.is_configured is False


def test_whitespace_database_url_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, "   \t  ")

    assert get_database_config().is_configured is False


def test_supported_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, VALID_URL)

    config = get_database_config()

    assert config.is_configured is True
    assert config.url == VALID_URL


@pytest.mark.parametrize(
    "url",
    [
        f"postgresql://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex",
        f"mysql+psycopg://{DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}:5432/apex",
        f"sqlite+aiosqlite:///{DUMMY_PASSWORD}.db",
    ],
)
def test_unsupported_url_schemes_are_rejected(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    _configure(monkeypatch, url)

    with pytest.raises(DatabaseConfigurationError) as error:
        get_database_config()

    message = str(error.value)
    assert SUPPORTED_DATABASE_SCHEME in message
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg:///apex",
        f"postgresql+psycopg://{DUMMY_USER}:{DUMMY_PASSWORD}@localhost",
    ],
)
def test_url_must_include_host_and_database(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    _configure(monkeypatch, url)

    with pytest.raises(DatabaseConfigurationError) as error:
        get_database_config()

    message = str(error.value)
    assert "host and database" in message
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message


@pytest.mark.parametrize("exception_type", [ArgumentError, RuntimeError])
def test_parse_errors_are_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[Exception],
) -> None:
    _configure(monkeypatch, VALID_URL)

    def _raise_parse_error(_: str) -> None:
        raise exception_type(
            f"could not parse {VALID_URL} for {DUMMY_USER}:{DUMMY_PASSWORD}@{DUMMY_HOST}"
        )

    monkeypatch.setattr(db_config, "make_url", _raise_parse_error)

    with pytest.raises(DatabaseConfigurationError) as error:
        get_database_config()

    message = str(error.value)
    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in message
    assert error.value.__cause__ is None
    assert error.value.__context__ is None


def test_database_config_repr_hides_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    config = get_database_config()
    rendered = repr(config)

    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in rendered


def test_settings_repr_hides_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, VALID_URL)

    rendered = repr(get_settings())

    for sensitive in SENSITIVE_PARTS:
        assert sensitive not in rendered


def test_configuration_module_does_not_create_an_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reading configuration must never create an engine."""
    from apex_backend.db import session as db_session

    _configure(monkeypatch, VALID_URL)
    monkeypatch.setattr(
        db_session,
        "create_async_engine",
        lambda *_, **__: (_ for _ in ()).throw(
            AssertionError("configuration must not create an engine")
        ),
    )

    config = get_database_config()

    assert config.is_configured is True
    assert db_session._engine is None
