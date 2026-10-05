"""Tests for the protected GET /api/v1/me endpoint."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from apex_backend.models.identity import Identity

USER_ID = "11111111-2222-4333-8444-555555555555"
USER_EMAIL = "apex.user@example.com"


def _access_token(secret: str, **overrides: object) -> str:
    claims: dict[str, object] = {
        "sub": USER_ID,
        "email": USER_EMAIL,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def offline_client(monkeypatch: pytest.MonkeyPatch, jwt_secret: str) -> TestClient:
    """App configured for offline JWT verification."""
    from apex_backend import create_app
    from apex_backend.core.config import get_settings

    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    get_settings.cache_clear()
    return TestClient(create_app())


class TestUnauthenticatedRequests:
    """Without a usable token the endpoint must refuse the request."""

    def test_missing_token_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/me")

        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}
        assert response.headers["www-authenticate"] == "Bearer"

    def test_malformed_authorization_header_returns_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/me", headers={"Authorization": "not-a-scheme"})

        assert response.status_code == 401

    def test_forged_token_returns_401(self, offline_client: TestClient) -> None:
        forged = _access_token("attacker-secret")

        response = offline_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {forged}"}
        )

        assert response.status_code == 401
        assert "Invalid or expired access token" in response.json()["detail"]

    def test_expired_token_returns_401(self, offline_client: TestClient, jwt_secret: str) -> None:
        expired = _access_token(jwt_secret, exp=int(time.time()) - 60)

        response = offline_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {expired}"}
        )

        assert response.status_code == 401

    def test_unconfigured_server_returns_503(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A token cannot be verified without Supabase settings."""
        from apex_backend.core.config import get_settings

        monkeypatch.setenv("SUPABASE_JWT_SECRET", "")
        get_settings.cache_clear()

        response = client.get("/api/v1/me", headers={"Authorization": "Bearer something"})

        assert response.status_code == 503


class TestAuthenticatedRequests:
    """A valid token yields the verified identity."""

    def test_returns_identity_from_token(
        self, offline_client: TestClient, jwt_secret: str
    ) -> None:
        token = _access_token(jwt_secret)

        response = offline_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"id": USER_ID, "email": USER_EMAIL}

    def test_response_matches_identity_model(
        self, offline_client: TestClient, jwt_secret: str
    ) -> None:
        token = _access_token(jwt_secret)

        response = offline_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert Identity.model_validate(response.json()).id == USER_ID

    def test_missing_email_is_allowed(
        self, offline_client: TestClient, jwt_secret: str
    ) -> None:
        token = _access_token(jwt_secret, email=None)

        response = offline_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        assert response.json() == {"id": USER_ID, "email": None}


class TestIdentityIsNotClientControlled:
    """The identity must come from the token, never from request input."""

    def test_query_param_user_id_is_ignored(
        self, offline_client: TestClient, jwt_secret: str
    ) -> None:
        token = _access_token(jwt_secret)

        response = offline_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            params={"user_id": "someone-elses-id", "id": "spoofed"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == USER_ID

    def test_body_user_id_cannot_override_identity(
        self, offline_client: TestClient, jwt_secret: str
    ) -> None:
        token = _access_token(jwt_secret)

        response = offline_client.post(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"id": "spoofed", "user_id": "spoofed"},
        )

        # The route only accepts GET, so a POST cannot reach the handler.
        assert response.status_code == 405