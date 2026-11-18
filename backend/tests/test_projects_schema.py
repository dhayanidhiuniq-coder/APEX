"""Story 1.3 schema metadata and Alembic revision checks.

These tests inspect SQLAlchemy metadata and the revision source only. They never
create a database, open a connection, or apply a migration.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import CheckConstraint, Column, MetaData, Table, Uuid
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from apex_backend.db import models  # noqa: F401  # Populates Base.metadata.
from apex_backend.db.base import Base
from apex_backend.db.models.project import Project, Task

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REVISION = (
    BACKEND_ROOT
    / "alembic"
    / "versions"
    / "20261117_1600_4f6c1d2a9b70_story_1_3_projects_tasks.py"
)


def _check_sql(table_name: str, constraint_name: str) -> str:
    table = Base.metadata.tables[table_name]
    constraint = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
        and constraint.name == constraint_name
    )
    return str(constraint.sqltext)


def test_projects_table_shape_and_indexes() -> None:
    table = Project.__table__

    assert set(table.columns.keys()) == {
        "id",
        "user_id",
        "title",
        "description",
        "created_at",
    }
    assert table.primary_key.name == "pk_projects"
    assert "ix_projects_user_id" in {index.name for index in table.indexes}

    foreign_key = next(iter(table.foreign_keys))
    assert foreign_key.target_fullname == "auth.users.id"
    assert foreign_key.ondelete == "CASCADE"

    assert "char_length(title) between 1 and 120" in _check_sql(
        "projects", "ck_projects_title_length"
    )
    assert table.c.created_at.type.timezone is True


def test_tasks_table_shape_checks_and_foreign_keys() -> None:
    table = Task.__table__

    assert set(table.columns.keys()) == {
        "id",
        "project_id",
        "user_id",
        "title",
        "priority",
        "status",
        "created_at",
    }
    assert table.primary_key.name == "pk_tasks"
    assert "ix_tasks_project_id" in {index.name for index in table.indexes}

    foreign_keys = {
        foreign_key.target_fullname: foreign_key for foreign_key in table.foreign_keys
    }
    assert set(foreign_keys) == {"projects.id", "auth.users.id"}
    assert all(foreign_key.ondelete == "CASCADE" for foreign_key in foreign_keys.values())

    assert "priority in ('low', 'medium', 'high')" in _check_sql(
        "tasks", "ck_tasks_priority_values"
    )
    assert "status in ('todo', 'in_progress', 'done')" in _check_sql(
        "tasks", "ck_tasks_status_values"
    )


def test_revision_is_discoverable_by_alembic() -> None:
    assert REVISION.is_file()

    source = REVISION.read_text(encoding="utf-8")
    assert 'revision: str = "4f6c1d2a9b70"' in source
    assert "down_revision: str | Sequence[str] | None = None" in source


def test_revision_enables_rls_and_user_ownership_policies() -> None:
    source = REVISION.read_text(encoding="utf-8")

    assert "ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY" in source
    assert "ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY" in source
    assert 'CREATE POLICY "Users manage own projects"' in source
    assert 'CREATE POLICY "Users manage own tasks"' in source
    assert "auth.uid() = user_id" in source
    assert "WITH CHECK" in source
    assert "TO authenticated" in source
    assert "FROM public.projects p" in source
    assert "p.user_id = auth.uid()" in source
    assert "auth.users.id" in source
    assert 'ondelete="CASCADE"' in source


def test_revision_grants_only_the_dml_the_authenticated_role_needs() -> None:
    source = REVISION.read_text(encoding="utf-8")

    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects "
        "TO authenticated" in source
    )
    assert (
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tasks "
        "TO authenticated" in source
    )
    assert "BYPASSRLS" not in source


def test_revision_downgrade_removes_policies_indexes_and_tables() -> None:
    source = REVISION.read_text(encoding="utf-8")

    assert 'DROP POLICY IF EXISTS "Users manage own tasks"' in source
    assert 'DROP POLICY IF EXISTS "Users manage own projects"' in source
    assert 'op.drop_index("ix_tasks_project_id"' in source
    assert 'op.drop_table("tasks"' in source
    assert 'op.drop_index("ix_projects_user_id"' in source
    assert 'op.drop_table("projects"' in source


def test_models_can_be_rendered_by_the_postgresql_dialect() -> None:
    """Compile the metadata as PostgreSQL DDL without connecting anywhere."""
    dialect = postgresql.dialect()

    # The application database owns ``public.projects`` and ``public.tasks``;
    # ``auth.users`` is supplied by Supabase Auth. Add a test-only placeholder
    # for the auth table so SQLAlchemy can resolve the foreign key while
    # compiling DDL. This is metadata only and never connects anywhere.
    metadata = MetaData()
    Table(
        "users",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True),
        schema="auth",
    )
    projects = Project.__table__.to_metadata(metadata)
    tasks = Task.__table__.to_metadata(metadata)

    project_ddl = str(CreateTable(projects).compile(dialect=dialect))
    task_ddl = str(CreateTable(tasks).compile(dialect=dialect))

    assert "CREATE TABLE projects" in project_ddl
    assert "REFERENCES auth.users (id) ON DELETE CASCADE" in project_ddl
    assert "CREATE TABLE tasks" in task_ddl
    assert "REFERENCES projects (id) ON DELETE CASCADE" in task_ddl
