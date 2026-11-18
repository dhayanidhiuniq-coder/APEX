"""Versioned API router.

New API groups are registered here so that future stories (tasks, MCP tools)
can be added without touching the application entrypoint.
"""

from __future__ import annotations

from fastapi import APIRouter

from .identity import router as identity_router
from .projects import router as projects_router

api_router = APIRouter()
api_router.include_router(identity_router)
api_router.include_router(projects_router)