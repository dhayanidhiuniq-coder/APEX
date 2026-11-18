"""Alembic environment for APEX database migrations."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from apex_backend.db import models  # noqa: F401  # Registers future ORM models.
from apex_backend.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Offline mode only renders SQL. This descriptor is deliberately fixed,
# credential-free, and never read from DATABASE_URL.
OFFLINE_DATABASE_URL = "postgresql+psycopg://"


def run_migrations_offline() -> None:
    """Render migrations as SQL without reading configuration or connecting."""
    context.configure(
        url=OFFLINE_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the configured database."""
    from apex_backend.db.config import (
        DatabaseConfigurationError,
        get_database_config,
    )

    database_config = get_database_config()
    if not database_config.is_configured:
        raise DatabaseConfigurationError(
            "DATABASE_URL is required for online migrations."
        )

    connectable = None
    failed = False

    try:
        connectable = create_engine(
            database_config.url,
            poolclass=pool.NullPool,
        )
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception:
        failed = True
    finally:
        if connectable is not None:
            try:
                connectable.dispose()
            except Exception:
                failed = True

    if failed:
        raise DatabaseConfigurationError(
            "Online database migration failed; check DATABASE_URL "
            "and database availability."
        )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
