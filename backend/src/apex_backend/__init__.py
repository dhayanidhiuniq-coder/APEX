from .main import app

__all__ = ["app"]


def main() -> None:
    import uvicorn
    import os

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() in ("1", "true", "yes")
    uvicorn.run("apex_backend.main:app", host=host, port=port, reload=reload)
