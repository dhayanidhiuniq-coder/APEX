"""Supabase access-token verification.

The backend never trusts an identity supplied by the client. Instead it takes
the bearer access token, sends it to Supabase Auth, and uses the user object
that Supabase returns as the authoritative identity.

Two verification strategies are supported:

1. **Authoritative (default).** The token is sent to Supabase's
   ``/auth/v1/user`` endpoint with the project's anon key. Supabase validates
   the signature and expiry, then returns the user record. This works for
   every signing scheme Supabase supports (legacy HS256 and the newer
   asymmetric keys), so it is the default.

2. **Offline.** When ``SUPABASE_JWT_SECRET`` is configured, the JWT signature
   is verified locally. This avoids a network round trip per request.

Both strategies raise :class:`InvalidTokenError` rather than returning a
partially trusted identity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Guard against pathological inputs (e.g. an accidentally huge header).
MAX_TOKEN_LENGTH = 8192
VERIFY_TIMEOUT_SECONDS = 5.0


class AuthConfigurationError(RuntimeError):
    """Raised when the backend is not configured to verify tokens."""


class InvalidTokenError(Exception):
    """Raised when a token is missing, malformed, expired or rejected."""


@dataclass(frozen=True, slots=True)
class SupabaseUser:
    """The subset of the Supabase user record that APEX needs."""

    id: str
    email: str | None


class SupabaseTokenVerifier:
    """Verifies Supabase access tokens and returns the owning user."""

    def __init__(
        self,
        supabase_url: str,
        supabase_anon_key: str,
        jwt_secret: str | None = None,
    ) -> None:
        if not supabase_url or not supabase_anon_key:
            raise AuthConfigurationError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be configured to verify access tokens."
            )
        self._supabase_url = supabase_url.rstrip("/")
        self._anon_key = supabase_anon_key
        self._jwt_secret = jwt_secret or None

    @property
    def uses_offline_verification(self) -> bool:
        return self._jwt_secret is not None

    async def verify(self, access_token: str) -> SupabaseUser:
        """Verify ``access_token`` and return its owning user.

        Raises:
            InvalidTokenError: the token is missing, malformed or rejected.
            AuthConfigurationError: verification is not possible.
        """
        if not access_token:
            raise InvalidTokenError("Missing access token")
        if len(access_token) > MAX_TOKEN_LENGTH:
            raise InvalidTokenError("Access token is unexpectedly large")

        if self._jwt_secret is not None:
            return self._verify_offline(access_token)
        return await self._verify_remotely(access_token)

    # --- Offline verification -------------------------------------------------

    def _verify_offline(self, access_token: str) -> SupabaseUser:
        try:
            from jose import jwt
        except ImportError as exc:  # pragma: no cover - dependency is optional
            raise AuthConfigurationError(
                "python-jose is required for offline token verification. "
                "Install it or unset SUPABASE_JWT_SECRET."
            ) from exc

        try:
            claims = jwt.decode(
                access_token,
                self._jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": False},
            )
        except Exception as exc:
            # The exception type depends on jose/pyjwt internals; never leak
            # details about the token itself.
            raise InvalidTokenError("Access token could not be verified") from exc

        user_id = claims.get("sub")
        if not user_id:
            raise InvalidTokenError("Access token does not contain a subject")

        return SupabaseUser(id=str(user_id), email=claims.get("email"))

    # --- Remote (authoritative) verification ---------------------------------

    async def _verify_remotely(self, access_token: str) -> SupabaseUser:
        url = f"{self._supabase_url}/auth/v1/user"
        headers = {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=VERIFY_TIMEOUT_SECONDS) as client:
                response = await client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            # Network / TLS failures are not proof of a bad token, so surface
            # this as a configuration problem rather than a 401.
            logger.warning("Could not reach Supabase Auth to verify token: %s", type(exc).__name__)
            raise AuthConfigurationError("Unable to reach Supabase Auth") from exc

        if response.status_code in (401, 403):
            raise InvalidTokenError("Access token is invalid or expired")

        if response.status_code != 200:
            logger.warning(
                "Unexpected status %s from Supabase Auth while verifying token",
                response.status_code,
            )
            raise AuthConfigurationError("Unable to verify access token")

        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthConfigurationError("Malformed response from Supabase Auth") from exc

        user_id = payload.get("id")
        if not user_id:
            raise InvalidTokenError("Access token does not resolve to a user")

        return SupabaseUser(id=str(user_id), email=payload.get("email"))