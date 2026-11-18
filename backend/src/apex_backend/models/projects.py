"""HTTP schemas for the Projects API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectCreate(BaseModel):
    """Fields accepted when creating a project.

    ``user_id`` is deliberately absent. Ownership comes from the verified
    bearer token; extra fields are rejected so a client cannot try to supply an
    owner through the request body.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ProjectRead(BaseModel):
    """A project as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    created_at: datetime
