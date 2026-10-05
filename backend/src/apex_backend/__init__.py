"""APEX backend package.

Exports the ASGI ``app`` so that ``uvicorn apex_backend.main:app`` works.
"""

from .main import app, create_app

__all__ = ["app", "create_app"]