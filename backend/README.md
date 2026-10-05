# APEX Backend

FastAPI backend for the APEX private per-user AI workspace.

## Requirements

- Python 3.14.7 (as configured)
- uv

## Setup

```bash
cd backend
uv venv
uv sync
```

## Run

```bash
# Using uv directly
uv run uvicorn apex_backend.main:app --host 0.0.0.0 --port 8000 --reload

# Or using npm script from root
npm run --prefix backend dev
```

## Health Check

GET http://localhost:8000/health returns `{"status": "ok"}`
