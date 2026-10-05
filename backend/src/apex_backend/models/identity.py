"""Pydantic models returned by the API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Identity(BaseModel):
    """The verified identity of the current caller.

    ``id`` is the Supabase Auth user id taken from the verified access token.
    It is never accepted from client input.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Supabase Auth user id (UUID).")
    email: str | None = Field(
        default=None,
        description="Email address associated with the authenticated user.",
    )


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str