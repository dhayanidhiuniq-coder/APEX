"""ORM model registry for Alembic metadata discovery.

Import ORM model modules here so that ``Base.metadata`` is populated before
Alembic autogenerate runs. This package must remain free of engine creation and
database I/O.
"""

from __future__ import annotations

from .project import Project, Task

__all__ = ["Project", "Task"]
