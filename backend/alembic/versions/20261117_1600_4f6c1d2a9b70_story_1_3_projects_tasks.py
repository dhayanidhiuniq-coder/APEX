"""Story 1.3: Projects and Tasks schema with ownership and RLS.

Revision ID: 4f6c1d2a9b70
Revises:
Create Date: 2026-11-17 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f6c1d2a9b70"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            server_default=sa.text("auth.uid()"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(title) between 1 and 120",
            name="ck_projects_title_length",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth.users.id"],
            name="fk_projects_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_projects"),
        schema="public",
    )
    op.create_index(
        "ix_projects_user_id",
        "projects",
        ["user_id"],
        unique=False,
        schema="public",
    )

    op.create_table(
        "tasks",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            server_default=sa.text("auth.uid()"),
            nullable=False,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "priority",
            sa.Text(),
            server_default=sa.text("'medium'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            server_default=sa.text("'todo'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority in ('low', 'medium', 'high')",
            name="ck_tasks_priority_values",
        ),
        sa.CheckConstraint(
            "status in ('todo', 'in_progress', 'done')",
            name="ck_tasks_status_values",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["public.projects.id"],
            name="fk_tasks_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["auth.users.id"],
            name="fk_tasks_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tasks"),
        schema="public",
    )
    op.create_index(
        "ix_tasks_project_id",
        "tasks",
        ["project_id"],
        unique=False,
        schema="public",
    )

    op.execute("ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY "Users manage own projects"
        ON public.projects
        FOR ALL
        TO authenticated
        USING (auth.uid() = user_id)
        WITH CHECK (auth.uid() = user_id)
        """
    )
    op.execute(
        """
        CREATE POLICY "Users manage own tasks"
        ON public.tasks
        FOR ALL
        TO authenticated
        USING (
            auth.uid() = user_id
            AND EXISTS (
                SELECT 1
                FROM public.projects p
                WHERE p.id = project_id
                  AND p.user_id = auth.uid()
            )
        )
        WITH CHECK (
            auth.uid() = user_id
            AND EXISTS (
                SELECT 1
                FROM public.projects p
                WHERE p.id = project_id
                  AND p.user_id = auth.uid()
            )
        )
        """
    )

    # The application executes statements after ``SET LOCAL ROLE authenticated``.
    # Grant exactly the DML the API needs; RLS still restricts every row.
    # The runtime login role must be a member of ``authenticated`` (database
    # owner prerequisite) and must not own these tables or bypass RLS.
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects TO authenticated"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tasks TO authenticated"
    )


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS "Users manage own tasks" ON public.tasks')
    op.execute('DROP POLICY IF EXISTS "Users manage own projects" ON public.projects')
    op.execute("ALTER TABLE public.tasks DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.projects DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_tasks_project_id", table_name="tasks", schema="public")
    op.drop_table("tasks", schema="public")
    op.drop_index("ix_projects_user_id", table_name="projects", schema="public")
    op.drop_table("projects", schema="public")
