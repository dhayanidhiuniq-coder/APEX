# APEX Backend

FastAPI service for APEX. Managed with [`uv`](https://docs.astral.sh/uv/).

Listens on <http://localhost:8000> by default.

## Setup

```bash
uv sync
```

Configuration comes from the environment. Copy `../.env.example` to `../.env`
(or `.env` in this folder) and fill in the Supabase values:

```bash
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_ANON_KEY=<anon-key>
CORS_ORIGINS=http://localhost:3000
```

`SUPABASE_JWT_SECRET` is optional. Set it only for self-hosted Supabase, where
it enables offline token verification. Leave it unset for hosted projects.

## Run

```bash
uv run uvicorn apex_backend.main:app --reload
```

From the repository root: `npm run dev:backend`.

## Test

```bash
uv run pytest
```

## Endpoints

| Method | Path                         | Access  | Description                       |
| ------ | ---------------------------- | ------- | --------------------------------- |
| GET    | `/health`                    | Public  | `{"status":"ok"}`                 |
| GET    | `/api/v1/me`                 | Private | Verified identity of the caller   |
| GET    | `/api/v1/projects`           | Private | List the caller's projects        |
| POST   | `/api/v1/projects`           | Private | Create a project for the caller   |
| DELETE | `/api/v1/projects/{project_id}` | Private | Delete one of the caller's projects |

Interactive docs: <http://localhost:8000/docs>

### `GET /api/v1/me`

Send the Supabase access token as a bearer token:

```bash
curl http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer <access-token>"
```

Returns the identity taken from the verified token:

```json
{ "id": "<supabase-user-id>", "email": "<user-email>" }
```

Status codes:

| Code | Meaning                                                       |
| ---- | ------------------------------------------------------------- |
| 200  | Token verified; identity returned                              |
| 401  | Missing, invalid or expired token                              |
| 503  | Backend has no Supabase credentials, so it cannot verify tokens |

The user id is never read from a request parameter, query string or body. The
only accepted input is the bearer token, and the response identity is derived
solely from verified claims.

### Projects

`GET /api/v1/projects` returns the caller's projects. `POST` accepts:

```json
{ "title": "Ship the first milestone", "description": "Optional notes" }
```

Ownership is taken from the verified token. Extra body fields such as
`user_id` or `owner_id` are rejected. `DELETE /api/v1/projects/{project_id}`
returns `404` when the project does not exist or belongs to another user.

| Code | Meaning |
| ---- | ------- |
| 200 | Projects listed |
| 201 | Project created |
| 204 | Project deleted |
| 401 | Missing, invalid or expired token |
| 404 | Project not found for this caller |
| 422 | Invalid title, description or request body |
| 503 | Database features are not configured or temporarily unavailable |

The Projects and Tasks tables are created by the Alembic revision
`alembic/versions/20261117_1600_4f6c1d2a9b70_story_1_3_projects_tasks.py`.
Alembic is the approved schema-change path. The revision was applied to the
APEX Supabase staging project on 2026-11-17; it has not been applied to
production. See [`docs/database.md`](docs/database.md) for verification status.

## Layout

```
src/apex_backend/
├── main.py         # app factory, CORS, /health, database error handlers
├── core/config.py  # settings from the environment
├── auth/
│   ├── supabase.py      # token verification (remote + offline)
│   └── dependencies.py  # get_current_identity / CurrentIdentity
├── db/
│   ├── models/          # ORM models registered for Alembic
│   ├── session.py       # lazy engine/session lifecycle
│   └── lifecycle.py     # startup/shutdown draining
├── repositories/        # persistence boundaries (Projects)
├── models/              # Pydantic schemas
└── api/v1/              # versioned routes
```

## Adding a protected route

Use the `CurrentIdentity` alias. It returns the verified caller or raises
`401`:

```python
from fastapi import APIRouter
from apex_backend.auth import CurrentIdentity
from apex_backend.models import Identity

router = APIRouter(prefix="/api/v1", tags=["example"])

@router.get("/example")
async def read_example(identity: CurrentIdentity) -> Identity:
    return identity
```

Never accept a `user_id` parameter for identity.

## Notes

- The suite runs entirely offline. No test contacts a real Supabase project or
  PostgreSQL database.
- Projects API tests use an in-memory repository. Alembic tests only render
  offline SQL.
- `httpx` is a dev dependency used by the test client.
