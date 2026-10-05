"""Tests for GET /health."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_authentication(client: TestClient) -> None:
    """The liveness probe must stay reachable without credentials."""
    response = client.get("/health", headers={"Authorization": ""})

    assert response.status_code == 200