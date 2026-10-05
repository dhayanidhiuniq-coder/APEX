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

| Method | Path            | Access  | Description                       |
| ------ | --------------- | ------- | --------------------------------- |
| GET    | `/health`       | Public  | `{"status":"ok"}`                 |
| GET    | `/api/v1/me`    | Private | Verified identity of the caller   |

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

## Layout

```
src/apex_backend/
├── main.py         # app factory, CORS, /health
├── core/config.py  # settings from the environment
├── auth/
│   ├── supabase.py      # token verification (remote + offline)
│   └── dependencies.py  # get_current_identity / CurrentIdentity
├── models/         # Pydantic schemas
└── api/v1/         # versioned routes
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

- The suite runs entirely offline. No test contacts a real Supabase project.
- `httpx` is a dev dependency used by the test client.
