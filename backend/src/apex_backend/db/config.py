"""Database configuration and validation.

The configuration is intentionally disabled by default: an empty
``DATABASE_URL`` means database-backed features are not available. This module
never creates an engine and never attempts a connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from ..core.config import get_settings

SUPPORTED_DATABASE_SCHEME = "postgresql+psycopg"
"""The only database URL scheme accepted by the application."""

DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT = 30
DEFAULT_POOL_RECYCLE = 1800


class DatabaseConfigurationError(RuntimeError):
    """Raised when ``DATABASE_URL`` is invalid or cannot be used.

    Messages are deliberately generic. They never include the URL or any of
    its credential-bearing components.
    """


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    """Validated database configuration.

    ``url`` is excluded from ``repr`` so accidental logging cannot disclose
    credentials.
    """

    url: str = field(default="", repr=False)

    @property
    def is_configured(self) -> bool:
        """True when a database URL has been provided."""
        return bool(self.url)


def get_database_config() -> DatabaseConfig:
    """Return validated database configuration from the environment.

    An empty or whitespace-only URL produces a disabled configuration. A
    non-empty URL must be a structurally valid PostgreSQL URL using the
    ``postgresql+psycopg`` scheme. No connection is attempted.
    """
    raw_url = get_settings().database_url
    url = raw_url.strip()
    if not url:
        return DatabaseConfig()

    parse_error: str | None = None
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError):
        parse_error = "DATABASE_URL is not a valid database URL."
    except Exception:
        parse_error = "DATABASE_URL could not be parsed."

    if parse_error is not None:
        raise DatabaseConfigurationError(parse_error)

    if parsed.drivername != SUPPORTED_DATABASE_SCHEME:
        raise DatabaseConfigurationError(
            f"DATABASE_URL must use the {SUPPORTED_DATABASE_SCHEME}:// scheme."
        )
    if not parsed.host or not parsed.database:
        raise DatabaseConfigurationError(
            "DATABASE_URL must include a host and database name."
        )

    return DatabaseConfig(url=url)
