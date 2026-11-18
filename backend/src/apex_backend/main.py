"""ASGI application factory for the APEX backend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1.router import api_router
from .core.config import get_settings
from .db.config import DatabaseConfigurationError
from .db.lifecycle import database_shutdown, database_startup
from .db.session import DatabaseNotConfiguredError, DatabaseShuttingDownError
from .models.identity import HealthResponse

logger = logging.getLogger(__name__)

DESCRIPTION = """
APEX backend API.

Authentication is handled by Supabase Auth. Clients send the Supabase access
token as a bearer token:

```
Authorization: Bearer <supabase-access-token>
```

Protected routes resolve the caller's identity from the verified token. The
backend never trusts a user id supplied by the client.
"""


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate startup configuration and release database resources on exit."""
    if not get_settings().supabase_is_configured:
        logger.warning(
            "SUPABASE_URL / SUPABASE_ANON_KEY are not set. "
            "Protected routes will respond with HTTP 503 until they are configured."
        )

    try:
        await database_startup()
        yield
    finally:
        await database_shutdown()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="APEX Backend",
        version="0.2.0",
        description=DESCRIPTION,
        lifespan=_lifespan,
    )

    @app.exception_handler(DatabaseShuttingDownError)
    async def database_shutting_down(
        _request: Request, exc: DatabaseShuttingDownError
    ) -> JSONResponse:
        """Return a sanitized retryable response when shutdown gates DB work."""
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(DatabaseNotConfiguredError)
    async def database_not_configured(
        _request: Request, _exc: DatabaseNotConfiguredError
    ) -> JSONResponse:
        """Return a sanitized response when database features are disabled."""
        return JSONResponse(
            status_code=503,
            content={"detail": "Database features are not configured."},
        )

    @app.exception_handler(DatabaseConfigurationError)
    async def database_configuration_unavailable(
        _request: Request, _exc: DatabaseConfigurationError
    ) -> JSONResponse:
        """Return a sanitized response when the configured database is unusable."""
        return JSONResponse(
            status_code=503,
            content={"detail": "Database features are temporarily unavailable."},
        )

    # Origins are configuration driven, so no production domain is hard-coded.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["health"],
        summary="Liveness probe",
    )
    async def health() -> HealthResponse:
        """Report that the service is running."""
        return HealthResponse(status="ok")

    app.include_router(api_router)

    return app


app = create_app()
