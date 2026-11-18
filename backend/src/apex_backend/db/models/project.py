"""ORM models for Story 1.3 Projects and Tasks.

The database is the source of truth for ownership. Both tables carry a
``user_id`` that references the Supabase Auth user, and the Tasks row also
references the owning Project. Row Level Security policies are added by the
Alembic revision; these models only describe the table shape.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base


class Project(Base):
    """A user-owned project shown on the dashboard."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        server_default=text("auth.uid()"),
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(title) between 1 and 120",
            name="title_length",
        ),
    )


class Task(Base):
    """A task belonging to one Project and one user."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth.users.id", ondelete="CASCADE"),
        nullable=False,
        server_default=text("auth.uid()"),
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'medium'"),
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'todo'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="tasks")

    __table_args__ = (
        CheckConstraint(
            "priority in ('low', 'medium', 'high')",
            name="priority_values",
        ),
        CheckConstraint(
            "status in ('todo', 'in_progress', 'done')",
            name="status_values",
        ),
    )
