"""Projects API tests using an in-memory repository.

No database connection is created. The tests override the repository dependency
so they exercise routing, authentication, validation, ownership filtering and
response shaping without SQLAlchemy I/O.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.exc import SQLAlchemyError

from apex_backend.api.v1.projects import get_project_repository
from apex_backend.db.models.project import Project

USER_ID = "11111111-2222-4333-8444-555555555555"
OTHER_USER_ID = "99999999-8888-4777-8666-555555555555"
USER_EMAIL = "apex.user@example.com"
JWT_SECRET = "story-1-3-test-secret-not-a-real-secret"


def _access_token(
    *,
    subject: str = USER_ID,
    secret: str = JWT_SECRET,
) -> str:
    claims = {
        "sub": subject,
        "email": USER_EMAIL,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _project(
    user_id: str,
    title: str,
    *,
    project_id: uuid.UUID | None = None,
) -> Project:
    return Project(
        id=project_id or uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        title=title,
        description=None,
        created_at=datetime.now(timezone.utc),
    )


class FakeProjectRepository:
    """Small in-memory stand-in for the SQLAlchemy repository."""

    def __init__(self) -> None:
        self.projects: dict[uuid.UUID, Project] = {}

    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        return [
            project
            for project in self.projects.values()
            if project.user_id == user_id
        ]

    async def create_for_user(
        self,
        user_id: uuid.UUID,
        title: str,
        description: str | None,
    ) -> Project:
        project = Project(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            description=description,
            created_at=datetime.now(timezone.utc),
        )
        self.projects[project.id] = project
        return project

    async def delete_for_user(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        project = self.projects.get(project_id)
        if project is None or project.user_id != user_id:
            return False
        del self.projects[project_id]
        return True


class FailingProjectRepository(FakeProjectRepository):
    async def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        raise SQLAlchemyError("driver detail that must not reach the client")


@pytest.fixture
def projects_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[TestClient, FakeProjectRepository]]:
    from apex_backend import create_app
    from apex_backend.core.config import get_settings

    monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
    get_settings.cache_clear()

    repository = FakeProjectRepository()
    app = create_app()
    app.dependency_overrides[get_project_repository] = lambda: repository

    yield TestClient(app), repository

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _headers(token: str | None = None) -> dict[str, str]:
    return {"Authorization": f"Bearer {token or _access_token()}"}


class TestAuthenticationAndValidation:
    def test_all_endpoints_require_a_token(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, _repository = projects_client

        assert client.get("/api/v1/projects").status_code == 401
        assert (
            client.post(
                "/api/v1/projects",
                json={"title": "No token"},
            ).status_code
            == 401
        )
        assert client.delete(f"/api/v1/projects/{uuid.uuid4()}").status_code == 401

    def test_invalid_subject_is_rejected(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, _repository = projects_client

        response = client.get(
            "/api/v1/projects",
            headers=_headers(_access_token(subject="not-a-uuid")),
        )

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authenticated user."}

    @pytest.mark.parametrize("title", ["", "   ", "x" * 121])
    def test_invalid_title_is_rejected(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
        title: str,
    ) -> None:
        client, _repository = projects_client

        response = client.post(
            "/api/v1/projects",
            headers=_headers(),
            json={"title": title},
        )

        assert response.status_code == 422

    def test_client_cannot_supply_owner_id(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client

        response = client.post(
            "/api/v1/projects",
            headers=_headers(),
            json={
                "title": "Spoofed owner",
                "user_id": OTHER_USER_ID,
                "owner_id": OTHER_USER_ID,
            },
        )

        assert response.status_code == 422
        assert repository.projects == {}

    def test_query_parameters_cannot_override_the_owner(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client

        response = client.post(
            "/api/v1/projects",
            params={"user_id": OTHER_USER_ID, "owner_id": OTHER_USER_ID},
            headers=_headers(),
            json={"title": "Query owner is ignored"},
        )

        assert response.status_code == 201
        stored = next(iter(repository.projects.values()))
        assert stored.user_id == uuid.UUID(USER_ID)

    def test_unverified_identity_headers_cannot_override_the_owner(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client
        headers = {
            **_headers(),
            "X-User-Id": OTHER_USER_ID,
            "X-Owner-Id": OTHER_USER_ID,
            "X-Supabase-User-Id": OTHER_USER_ID,
        }

        response = client.post(
            "/api/v1/projects",
            headers=headers,
            json={"title": "Header owner is ignored"},
        )

        assert response.status_code == 201
        stored = next(iter(repository.projects.values()))
        assert stored.user_id == uuid.UUID(USER_ID)


class TestProjectsCrud:
    def test_create_uses_verified_identity(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client

        response = client.post(
            "/api/v1/projects",
            headers=_headers(),
            json={
                "title": "  Review the API spec  ",
                "description": "  Include the ownership checks.  ",
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert set(payload) == {"id", "title", "description", "created_at"}
        assert payload["title"] == "Review the API spec"
        assert payload["description"] == "Include the ownership checks."

        stored = next(iter(repository.projects.values()))
        assert stored.user_id == uuid.UUID(USER_ID)

    def test_list_returns_only_the_callers_projects(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client
        own_project = _project(USER_ID, "Own project")
        other_project = _project(OTHER_USER_ID, "Other user's project")
        repository.projects[own_project.id] = own_project
        repository.projects[other_project.id] = other_project

        response = client.get("/api/v1/projects", headers=_headers())

        assert response.status_code == 200
        assert [project["id"] for project in response.json()] == [
            str(own_project.id)
        ]

    def test_delete_own_project(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client
        project = _project(USER_ID, "Delete me")
        repository.projects[project.id] = project

        response = client.delete(
            f"/api/v1/projects/{project.id}",
            headers=_headers(),
        )

        assert response.status_code == 204
        assert repository.projects == {}

    def test_delete_other_users_project_is_not_found_and_keeps_row(
        self,
        projects_client: tuple[TestClient, FakeProjectRepository],
    ) -> None:
        client, repository = projects_client
        project = _project(OTHER_USER_ID, "Not mine")
        repository.projects[project.id] = project

        response = client.delete(
            f"/api/v1/projects/{project.id}",
            headers=_headers(),
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Project not found."}
        assert project.id in repository.projects

    def test_persistence_failure_is_sanitized(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from apex_backend import create_app
        from apex_backend.api.v1 import projects as projects_routes
        from apex_backend.core.config import get_settings

        monkeypatch.setenv("SUPABASE_JWT_SECRET", JWT_SECRET)
        get_settings.cache_clear()

        repository = FailingProjectRepository()
        app = create_app()
        app.dependency_overrides[get_project_repository] = lambda: repository

        try:
            with caplog.at_level(
                logging.WARNING,
                logger=projects_routes.logger.name,
            ):
                response = TestClient(app).get(
                    "/api/v1/projects",
                    headers=_headers(),
                )
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

        assert response.status_code == 503
        assert response.json() == {
            "detail": "Projects are temporarily unavailable."
        }
        assert "driver detail" not in response.text
        assert "driver detail" not in caplog.text


def test_missing_database_configuration_is_a_sanitized_503(
    monkeypatch: pytest.MonkeyPatch,
    jwt_secret: str,
) -> None:
    from apex_backend import create_app
    from apex_backend.core.config import get_settings

    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    app = create_app()

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/projects",
                headers=_headers(_access_token(secret=jwt_secret)),
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database features are not configured."}


def test_invalid_database_configuration_is_a_sanitized_503(
    monkeypatch: pytest.MonkeyPatch,
    jwt_secret: str,
) -> None:
    from apex_backend import create_app
    from apex_backend.core.config import get_settings

    monkeypatch.setenv("SUPABASE_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unused.db")
    get_settings.cache_clear()
    app = create_app()

    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/v1/projects",
                headers=_headers(_access_token(secret=jwt_secret)),
            )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Database features are temporarily unavailable."
    }


def test_project_model_is_used_by_the_fake_repository() -> None:
    """Guard against accidentally testing a different object shape."""
    project = _project(USER_ID, "Shape")
    assert isinstance(project, Project)
    assert project.user_id == uuid.UUID(USER_ID)
