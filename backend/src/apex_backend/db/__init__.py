"""Database foundation for the APEX backend.

Importing this package must not create an engine or open a connection. The
engine and session factory are created lazily on first use.
"""

from .config import (
    DatabaseConfig,
    DatabaseConfigurationError,
    get_database_config,
)
from .session import (
    DatabaseNotConfiguredError,
    get_db_session,
)

__all__ = [
    "DatabaseConfig",
    "DatabaseConfigurationError",
    "DatabaseNotConfiguredError",
    "get_database_config",
    "get_db_session",
]
