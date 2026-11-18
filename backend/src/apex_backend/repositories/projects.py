"""Project persistence boundary.

Routes depend on the :class:`ProjectRepository` protocol, not directly on
SQLAlchemy. That keeps ownership checks in one place and lets the API tests use
an in-memory repository without opening a database connection.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.project import Project


class ProjectRepository(Protocol):
    """Operations the Projects API needs from persistence."""

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Project]:
        """Return the user's projects, newest first."""

    async def create_for_user(
        self,
        user_id: uuid.UUID,
        title: str,
        description: str | None,
    ) -> Project:
        """Create a project owned by ``user_id``."""

    async def delete_for_user(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        """Delete the project only when ``user_id`` owns it."""


class SqlAlchemyProjectRepository:
    """SQLAlchemy implementation used by the running application."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Project]:
        result = await self._session.execute(
            select(Project)
            .where(Project.user_id == user_id)
            .order_by(Project.created_at.desc(), Project.id.desc())
        )
        return result.scalars().all()

    async def create_for_user(
        self,
        user_id: uuid.UUID,
        title: str,
        description: str | None,
    ) -> Project:
        project = Project(
            user_id=user_id,
            title=title,
            description=description,
        )
        self._session.add(project)
        await self._session.commit()
        await self._session.refresh(project)
        return project

    async def delete_for_user(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> bool:
        result = await self._session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.user_id == user_id,
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            return False

        await self._session.delete(project)
        await self._session.commit()
        return True
