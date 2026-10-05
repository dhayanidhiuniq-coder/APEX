"""ASGI application factory for the APEX backend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .core.config import get_settings
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
    """Warn at startup when Supabase settings are missing."""
    if not get_settings().supabase_is_configured:
        logger.warning(
            "SUPABASE_URL / SUPABASE_ANON_KEY are not set. "
            "Protected routes will respond with HTTP 503 until they are configured."
        )
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="APEX Backend",
        version="0.2.0",
        description=DESCRIPTION,
        lifespan=_lifespan,
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