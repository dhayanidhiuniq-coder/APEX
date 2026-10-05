# APEX

Private, per-user AI workspace.

**Status:** Story 1.1 (monorepo) and Story 1.2 (identity & authentication) are
complete. Projects and tasks are not implemented yet.

## Stack

| Layer    | Technology                              | Port |
| -------- | --------------------------------------- | ---- |
| Frontend | Next.js 16 (App Router), TypeScript, Tailwind CSS | 3000 |
| Backend  | FastAPI, Python, managed with `uv`       | 8000 |

## Requirements

Node.js 24, npm 11, Python 3.14, [`uv`](https://docs.astral.sh/uv/).

## Getting started

### 1. Configure the environment

```bash
cp .env.example .env
```

Fill in the Supabase values. See [Supabase setup](#supabase-setup) below.

The frontend reads its own env file, so also create one:

```bash
cp .env.example frontend/.env.local
```

### 2. Install dependencies

```bash
npm install                 # frontend + root tooling
cd backend && uv sync       # backend
```

### 3. Run both servers

```bash
npm run dev
```

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000> (docs at `/docs`, health at `/health`)

## Scripts

| Command                | Description                                    |
| ---------------------- | ---------------------------------------------- |
| `npm run dev`          | Start frontend and backend together            |
| `npm run dev:frontend` | Frontend only (`next dev -p 3000`)             |
| `npm run dev:backend`  | Backend only (`uvicorn ... --reload`)          |
| `npm run build`        | Production build of the frontend               |
| `npm start`            | Serve the production frontend build            |
| `cd backend && uv run pytest` | Run the backend test suite              |

## Authentication (Story 1.2)

Supabase Auth is the identity provider. Emails and passwords are handled
entirely by Supabase; APEX never stores credentials.

### How it works

1. The user signs up or signs in on `/signup` or `/signin`. The browser calls
   Supabase Auth through `@supabase/supabase-js`.
2. `@supabase/ssr` stores the session in **cookies**, not `localStorage`. The
   access token is therefore never placed in application state or exposed to
   arbitrary client-side JavaScript.
3. `src/proxy.ts` refreshes the session before each render and redirects
   signed-out users away from `/dashboard`.
4. `src/lib/auth.ts` performs the **authoritative** check on the server during
   render. `proxy.ts` alone is not trusted: the protected page body never
   executes without a valid session.
5. For backend calls, the Next.js server reads the session and sends the
   access token as a bearer token. The FastAPI backend **verifies the token
   itself** and derives the user identity from the verified claims. The user id
   is never accepted from a request parameter, query string or body.

Only public values (`NEXT_PUBLIC_*`) are exposed to the browser. The Supabase
service-role key and JWT secret are server-only and must never be placed in a
`NEXT_PUBLIC_` variable.

### Frontend routes

| Route       | Access  | Description                        |
| ----------- | ------- | ---------------------------------- |
| `/`         | Public  | Landing page                       |
| `/signin`   | Public  | Sign in (honours `?next=`)         |
| `/signup`   | Public  | Create an account                  |
| `/dashboard`| Private | Protected area; redirects to `/signin` |

### Backend routes

| Route            | Access  | Description                                  |
| ---------------- | ------- | -------------------------------------------- |
| `GET /health`    | Public  | Liveness probe, `{"status":"ok"}`            |
| `GET /api/v1/me` | Private | Verified identity of the caller              |

`GET /api/v1/me` returns:

```json
{ "id": "<supabase-user-id>", "email": "<user-email>" }
```

Responses:

- `401` — no token, or the token is invalid or expired.
- `503` — the backend has no Supabase credentials configured, so it cannot
  verify anything.

### How the backend verifies tokens

`backend/src/apex_backend/auth/supabase.py` supports two strategies:

- **Authoritative (default).** The token is sent to Supabase's
  `/auth/v1/user` endpoint, which validates the signature and expiry. This
  works for every signing scheme Supabase uses and needs no shared secret.
- **Offline (optional).** If `SUPABASE_JWT_SECRET` is set, the JWT is verified
  locally, avoiding a network hop. Only appropriate for self-hosted Supabase;
  leave it unset for hosted projects, which sign tokens with asymmetric keys.

## Supabase setup

Create a project at <https://supabase.com>, then:

1. **Project Settings → API.** Copy the **Project URL** and the **anon /
   publishable key** into `.env` and `frontend/.env.local`:

   ```bash
   NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
   SUPABASE_URL=https://<project-ref>.supabase.co
   SUPABASE_ANON_KEY=<anon-key>
   ```

2. **Authentication → Sign In / Providers → Email.** By default new accounts
   require email confirmation. For local testing you can disable "Confirm
   email"; the sign-up page then signs the user in immediately.

3. No database tables are needed for this story. The `profiles` table, Projects
   and Tasks belong to Story 1.3.

4. Restart the dev servers after editing env files. `NEXT_PUBLIC_*` values are
   inlined at build time, so delete `frontend/.next` if a change appears not to
   take effect.

Never commit `.env`, `.env.local`, the service-role key, or the JWT secret.
Only `.env.example` is tracked.

## Repository layout

```
APEX/
├── frontend/          # Next.js app
│   └── src/
│       ├── app/
│       │   ├── (auth)/       # /signin, /signup
│       │   └── (protected)/  # /dashboard
│       ├── components/       # AuthForm, SignOutButton
│       ├── lib/              # data access layer + Supabase clients
│       └── proxy.ts          # session refresh (Next 16 name for middleware)
├── backend/           # FastAPI app
│   ├── src/apex_backend/
│   │   ├── api/v1/    # versioned routes
│   │   ├── auth/      # token verification + dependencies
│   │   ├── core/      # settings
│   │   └── models/    # Pydantic schemas
│   └── tests/
├── .env.example
└── package.json       # root dev orchestration
```

## Testing

```bash
# Backend
cd backend
uv run pytest

# Frontend typecheck and production build
cd frontend
npx tsc --noEmit
npx next build
```

The backend suite covers token verification (valid, expired, forged,
wrong secret, unsigned `alg:none`, oversized, empty) and the protected
endpoint (unauthenticated rejection, verified identity, and that a
client-supplied `user_id` cannot influence the result).

## Notes and limitations

- `@supabase/ssr` splits large cookies into chunks; a local Supabase session
  produces around ten cookies. This is expected.
- The auth UI is functional, not final. Visual design arrives later.
- Row Level Security policies require database tables and are Story 1.3.
