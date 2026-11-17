"""Database lifecycle hooks for application startup and shutdown.

Startup only inspects configuration. It never creates an engine or opens a
connection. Shutdown disposes any lazily-created engine and suppresses only
ordinary cleanup failures, using static messages that contain no connection
details.
"""

from __future__ import annotations

import logging

from .config import DatabaseConfigurationError, get_database_config
from .session import (
    begin_database_shutdown,
    dispose_engine,
    mark_database_shutdown_complete,
    reset_database_shutdown_state,
    wait_for_database_work,
)

logger = logging.getLogger(__name__)

DATABASE_DISABLED_MESSAGE = (
    "Database features are disabled; DATABASE_URL is not configured."
)
DATABASE_ENABLED_MESSAGE = "Database features are configured."
DATABASE_CONFIGURATION_UNAVAILABLE_MESSAGE = (
    "Database configuration is unavailable; database features cannot be used."
)
DATABASE_SHUTDOWN_FAILED_MESSAGE = "Database shutdown did not complete cleanly."
DATABASE_DRAIN_TIMEOUT_SECONDS = 30.0
DATABASE_DRAIN_TIMEOUT_MESSAGE = (
    "Database shutdown drain timed out; engine disposal was skipped."
)


async def database_startup() -> None:
    """Report configuration state without creating an engine or connecting."""
    reset_database_shutdown_state()
    try:
        config = get_database_config()
    except DatabaseConfigurationError:
        logger.warning(DATABASE_CONFIGURATION_UNAVAILABLE_MESSAGE)
        return

    if config.is_configured:
        logger.info(DATABASE_ENABLED_MESSAGE)
    else:
        logger.info(DATABASE_DISABLED_MESSAGE)


async def database_shutdown() -> None:
    """Drain DB work before disposal, without masking control-flow exceptions."""
    permit = begin_database_shutdown()
    try:
        drained = await wait_for_database_work(DATABASE_DRAIN_TIMEOUT_SECONDS)
    except BaseException:
        mark_database_shutdown_complete()
        raise

    if not drained:
        logger.warning(DATABASE_DRAIN_TIMEOUT_MESSAGE)
        mark_database_shutdown_complete()
        return

    try:
        await dispose_engine(_permit=permit)
    except Exception:
        logger.warning(DATABASE_SHUTDOWN_FAILED_MESSAGE)
