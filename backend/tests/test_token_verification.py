"""Tests for Supabase access-token verification."""

from __future__ import annotations

import base64
import json
import time

import pytest
from jose import jwt

from apex_backend.auth.supabase import (
    AuthConfigurationError,
    InvalidTokenError,
    SupabaseTokenVerifier,
    SupabaseUser,
)

pytestmark = pytest.mark.anyio


def _b64url(raw: bytes) -> str:
    """Base64url-encode without padding, as required by JWT."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unsigned_token(claims: dict[str, object]) -> str:
    """Hand-build an ``alg: none`` JWT that no library will sign for us."""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps(claims).encode())
    return f"{header}.{payload}."


def _make_token(secret: str, **overrides: object) -> str:
    """Build a signed Supabase-style access token."""
    claims: dict[str, object] = {
        "sub": "3f1a2b4c-0000-4000-8000-abcdefabcdef",
        "email": "user@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def _verifier(secret: str | None) -> SupabaseTokenVerifier:
    return SupabaseTokenVerifier(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        jwt_secret=secret,
    )


class TestOfflineVerification:
    """Verification against a locally configured shared secret."""

    async def test_valid_token_returns_identity(self, jwt_secret: str) -> None:
        user = await _verifier(jwt_secret).verify(_make_token(jwt_secret))

        assert user == SupabaseUser(
            id="3f1a2b4c-0000-4000-8000-abcdefabcdef",
            email="user@example.com",
        )

    async def test_token_signed_with_wrong_secret_is_rejected(self, jwt_secret: str) -> None:
        forged = _make_token("a-different-secret")

        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify(forged)

    async def test_expired_token_is_rejected(self, jwt_secret: str) -> None:
        expired = _make_token(jwt_secret, exp=int(time.time()) - 60)

        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify(expired)

    async def test_token_without_subject_is_rejected(self, jwt_secret: str) -> None:
        anonymous = _make_token(jwt_secret, sub=None)

        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify(anonymous)

    async def test_garbage_token_is_rejected(self, jwt_secret: str) -> None:
        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify("not-a-jwt")

    @pytest.mark.parametrize("token", ["", "   "])
    async def test_empty_token_is_rejected(self, jwt_secret: str, token: str) -> None:
        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify(token)

    async def test_oversized_token_is_rejected(self, jwt_secret: str) -> None:
        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify("a" * 10_000)

    async def test_alg_none_token_is_rejected(self, jwt_secret: str) -> None:
        """An unsigned "alg: none" token must never be accepted."""
        unsigned = _unsigned_token(
            {
                "sub": "attacker",
                "aud": "authenticated",
                "exp": int(time.time()) + 3600,
            }
        )

        with pytest.raises(InvalidTokenError):
            await _verifier(jwt_secret).verify(unsigned)


class TestConfiguration:
    """A verifier cannot exist without Supabase settings."""

    @pytest.mark.parametrize(
        ("url", "key"),
        [("", "anon"), ("https://test.supabase.co", "")],
    )
    def test_missing_settings_raise(self, url: str, key: str) -> None:
        with pytest.raises(AuthConfigurationError):
            SupabaseTokenVerifier(supabase_url=url, supabase_anon_key=key)

    def test_offline_flag_reflects_configuration(self, jwt_secret: str) -> None:
        assert _verifier(jwt_secret).uses_offline_verification is True
        assert _verifier(None).uses_offline_verification is False