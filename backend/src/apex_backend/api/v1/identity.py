"""Routes that describe the authenticated caller."""

from __future__ import annotations

from fastapi import APIRouter

from ...auth.dependencies import CurrentIdentity
from ...models.identity import Identity

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get(
    "/me",
    response_model=Identity,
    summary="Return the authenticated user",
    description=(
        "Returns the identity resolved from the verified Supabase access token "
        "in the Authorization header. Responds with 401 when the token is "
        "missing, invalid or expired."
    ),
)
async def read_current_identity(identity: CurrentIdentity) -> Identity:
    return identity