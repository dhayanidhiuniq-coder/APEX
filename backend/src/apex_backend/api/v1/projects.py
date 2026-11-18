"""Authenticated Projects CRUD endpoints.

The caller's identity always comes from :data:`CurrentIdentity`, which is
resolved from the verified bearer token. Ownership is never read from a path,
query parameter or request body. The repository repeats the ownership filter
for deletes so a guessed project id cannot remove another user's row.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.dependencies import CurrentIdentity
from ...db.config import DatabaseConfigurationError
from ...db.rls import bind_request_identity, build_rls_identity
from ...db.session import (
    DatabaseLifecycleError,
    DatabaseNotConfiguredError,
    get_db_session,
)
from ...models.identity import Identity
from ...models.projects import ProjectCreate, ProjectRead
from ...repositories.projects import ProjectRepository, SqlAlchemyProjectRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

T = TypeVar("T")


async def get_project_repository(
    identity: CurrentIdentity,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProjectRepository:
    """Build the repository after binding the verified identity to SQL.

    The hook is installed before the repository can issue a statement, so the
    first Projects query in every transaction runs as ``authenticated`` with the
    verified subject in ``request.jwt.claims``.
    """
    user_id = _authenticated_user_id(identity)
    bind_request_identity(session, build_rls_identity(user_id))
    return SqlAlchemyProjectRepository(session)


ProjectRepo = Annotated[ProjectRepository, Depends(get_project_repository)]


def _authenticated_user_id(identity: Identity) -> uuid.UUID:
    """Convert the verified token subject into a UUID without trusting input."""
    try:
        return uuid.UUID(identity.id)
    except (AttributeError, ValueError):
        logger.warning("Authenticated identity did not contain a UUID subject")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authenticated user.",
        ) from None


async def _run(operation: Callable[[], Awaitable[T]]) -> T:
    """Run a repository operation and translate persistence failures.

    Error responses are intentionally generic. Driver text and connection
    details must never reach the client or a log line.
    """
    try:
        return await operation()
    except (
        DatabaseConfigurationError,
        DatabaseNotConfiguredError,
        DatabaseLifecycleError,
    ):
        logger.warning("Projects operation rejected by database lifecycle")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Projects are temporarily unavailable.",
        ) from None
    except SQLAlchemyError:
        # Do not attach the exception: driver text can include SQL and values.
        logger.warning("Project database operation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Projects are temporarily unavailable.",
        ) from None


@router.get(
    "",
    response_model=list[ProjectRead],
    summary="List the caller's projects",
)
async def list_projects(
    identity: CurrentIdentity,
    repository: ProjectRepo,
) -> list[ProjectRead]:
    user_id = _authenticated_user_id(identity)
    projects = await _run(lambda: repository.list_for_user(user_id))
    return [ProjectRead.model_validate(project) for project in projects]


@router.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project owned by the caller",
)
async def create_project(
    payload: ProjectCreate,
    identity: CurrentIdentity,
    repository: ProjectRepo,
) -> ProjectRead:
    user_id = _authenticated_user_id(identity)
    project = await _run(
        lambda: repository.create_for_user(
            user_id,
            payload.title,
            payload.description,
        )
    )
    return ProjectRead.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the caller's projects",
)
async def delete_project(
    project_id: uuid.UUID,
    identity: CurrentIdentity,
    repository: ProjectRepo,
) -> Response:
    user_id = _authenticated_user_id(identity)
    deleted = await _run(lambda: repository.delete_for_user(user_id, project_id))
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
