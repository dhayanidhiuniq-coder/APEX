"""Reusable authentication dependencies for FastAPI routes.

Any protected route in APEX obtains the caller's identity through
:func:`get_current_identity`. The dependency extracts the bearer token from
the ``Authorization`` header and hands it to the Supabase token verifier. The
user id always comes from the *verified* token, never from a request
parameter, query string or body field.

Usage in a route::

    @router.get("/me")
    async def me(identity: CurrentIdentity) -> Identity:
        return identity
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..core.config import Settings, get_settings
from ..models.identity import Identity
from .supabase import (
    AuthConfigurationError,
    InvalidTokenError,
    SupabaseTokenVerifier,
)

logger = logging.getLogger(__name__)

# auto_error=False so a missing header produces our own 401 shape rather than
# FastAPI's default, keeping error responses consistent across the API.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Supabase access token issued to a signed-in user.",
)


def build_token_verifier(settings: Settings) -> SupabaseTokenVerifier:
    """Create a token verifier from application settings.

    Raises:
        AuthConfigurationError: Supabase settings are missing.
    """
    return SupabaseTokenVerifier(
        supabase_url=settings.supabase_url,
        supabase_anon_key=settings.supabase_anon_key,
        jwt_secret=settings.supabase_jwt_secret or None,
    )


async def get_current_identity(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Identity:
    """Resolve the authenticated caller from the bearer token.

    Raises:
        HTTPException: 401 when no valid access token was supplied, 503 when
            the backend has not been configured to verify tokens.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        verifier = build_token_verifier(settings)
    except AuthConfigurationError:
        logger.warning("Supabase Auth is not configured; cannot verify access token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server",
        ) from None

    try:
        user = await verifier.verify(credentials.credentials)
    except InvalidTokenError:
        # Intentionally vague: do not reveal whether the token was forged,
        # expired or simply unknown.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except AuthConfigurationError:
        logger.warning("Supabase Auth could not be reached to verify the access token")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is temporarily unavailable",
        ) from None

    return Identity(id=user.id, email=user.email)


CurrentIdentity = Annotated[Identity, Depends(get_current_identity)]
"""Convenience alias: ``identity: CurrentIdentity`` in a route signature."""