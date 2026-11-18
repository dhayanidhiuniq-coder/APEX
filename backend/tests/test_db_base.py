"""Tests for shared SQLAlchemy metadata naming conventions."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

from apex_backend.db.base import NAMING_CONVENTION, Base


def test_base_metadata_uses_naming_convention() -> None:
    assert dict(Base.metadata.naming_convention) == NAMING_CONVENTION


def test_naming_convention_names_constraints_and_indexes() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    users = Table(
        "users",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String(255), nullable=False, unique=True),
    )
    projects = Table(
        "projects",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("owner_id", ForeignKey("users.id"), nullable=False, index=True),
        CheckConstraint("id > 0", name="positive_id"),
    )

    assert users.primary_key.name == "pk_users"

    unique_constraint = next(
        constraint
        for constraint in users.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert unique_constraint.name == "uq_users_email"

    foreign_key = next(iter(projects.foreign_keys))
    assert foreign_key.constraint.name == "fk_projects_owner_id_users"

    check_constraint = next(
        constraint
        for constraint in projects.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert check_constraint.name == "ck_projects_positive_id"

    index = next(iter(projects.indexes))
    assert index.name == "ix_projects_owner_id"
