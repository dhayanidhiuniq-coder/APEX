"""Shared pytest fixtures.

Tests must never talk to a real Supabase project, so the verifier is always
either stubbed or pointed at a local fake key.
"""

from __future__ import annotations

import os

import pytest

# Set before any application module reads settings.
os.environ.setdefault("SUPABASE_URL", "https://test-project.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

from fastapi.testclient import TestClient  # noqa: E402

from apex_backend import create_app  # noqa: E402
from apex_backend.core.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure each test starts from a freshly parsed environment."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    """Test client for the real application instance."""
    return TestClient(create_app())


@pytest.fixture
def jwt_secret() -> str:
    """Symmetric secret used to sign test tokens."""
    return "unit-test-jwt-secret-not-a-real-secret"


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio-based async tests on asyncio."""
    return "asyncio"