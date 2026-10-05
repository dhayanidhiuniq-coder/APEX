# APEX

Private, per-user AI workspace.

**Status:** Story 1.1 (monorepo) and Story 1.2 (identity & authentication,
including account creation and email verification) are complete. Projects and
tasks are not implemented yet.

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

1. The user creates an account on `/create-account` or signs in on `/signin`.
2. Registration is a Server Action (`src/lib/account-actions.ts`). It validates
   name, age, email, password and confirmation, then hands the credentials to
   Supabase Auth. Name and age are **profile data**, sent as Supabase user
   metadata; the password goes to Supabase and is never stored by APEX.
3. Because "Confirm email" is on, Supabase returns no session. The user is sent
   to `/verify` and Supabase emails a 6-digit code.
4. `/verify` submits the code back to Supabase. **Verifying the code is what
   signs the user in** — Supabase returns a session with the verification
   response, and the user lands on `/dashboard`.
5. `@supabase/ssr` stores the session in **cookies**, not `localStorage`. The
   access token is therefore never placed in application state or exposed to
   arbitrary client-side JavaScript.
6. `src/proxy.ts` refreshes the session before each render and routes callers:
   signed-out to `/signin`, signed-in-but-unconfirmed to `/verify`.
7. `src/lib/auth.ts` performs the **authoritative** check on the server during
   render via `requireVerifiedUser()`. `proxy.ts` alone is not trusted: the
   protected page body never executes without a valid, confirmed session.
8. For backend calls, the Next.js server reads the session and sends the
   access token as a bearer token. The FastAPI backend **verifies the token
   itself** and derives the user identity from the verified claims. The user id
   is never accepted from a request parameter, query string or body.

### Account creation and email verification

| Field              | Rule                                                  |
| ------------------ | ----------------------------------------------------- |
| Name               | Required, non-blank, ≤ 120 characters                 |
| Age                | Required, whole number, 0–120                         |
| Email              | Required, valid format                                |
| Password           | Required, at least 8 characters                       |
| Confirm password   | Required, must match exactly                          |

Validation runs on the server before any network call, so an invalid submission
never reaches Supabase. Errors are returned per field and rendered beside the
input, wired up with `aria-invalid` and `aria-describedby`.

Security properties worth stating explicitly:

- **No password is persisted by APEX**, and none is returned to the browser. The
  Create Account action deliberately does not echo field values back through its
  state, so a rejected submission cannot round-trip a password into the DOM.
- **The one-time code never enters client state.** It goes straight from the
  form to a Server Action to Supabase. It is never logged, never stored, and
  never interpolated into an error message.
- **The address awaiting confirmation lives in an httpOnly cookie**, not in
  `?email=`, so it stays out of browser history and request logs.
- **Upstream error text is never passed through unrecognised.** Sign-up and OTP
  failures are matched against an allowlist of known cases; anything unknown
  falls back to a generic message. No stack traces reach the user.
- Supabase answers a mistyped code and an expired one identically, so APEX does
  not claim to distinguish them — one message covers both and points at Resend.

The service-role key is not needed anywhere in this flow, and is never used by
the frontend.

### Where name and age are stored

The Create Account form sends name and age to Supabase as **user metadata**
(`options.data`). That is enough for everything in this story: it travels with
the user record, needs no database table, and needs no service-role key.

`supabase/migrations/0001_create_profiles.sql` additionally defines a
`public.profiles` table (`user_id`, `name`, `age`, `created_at`, `updated_at`)
keyed on the Supabase Auth user id, with RLS and a trigger that copies the
metadata into it on sign-up. **APEX does not read or write that table yet.**
It exists so the profile has a first-class, queryable home before Story 1.3
needs one, and so RLS is settled while the table has a single shape. The app
runs correctly whether or not you apply it.

Only public values (`NEXT_PUBLIC_*`) are exposed to the browser. The Supabase
service-role key and JWT secret are server-only and must never be placed in a
`NEXT_PUBLIC_` variable.

### Frontend routes

| Route             | Access  | Description                                     |
| ----------------- | ------- | ----------------------------------------------- |
| `/`               | Public  | Landing page                                    |
| `/signin`         | Public  | Sign in (honours `?next=`)                      |
| `/create-account` | Public  | Create an account (name, age, email, password)  |
| `/verify`         | Public  | Email code entry; needs a pending registration  |
| `/signup`         | Public  | Redirects to `/create-account`                 |
| `/dashboard`      | Private | Protected area; requires a confirmed session   |

Protected-area routing:

| Caller                    | Result                     |
| ------------------------- | -------------------------- |
| Not authenticated         | `/signin`                  |
| Authenticated, unconfirmed| `/verify`                  |
| Authenticated, confirmed  | Allowed                    |

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

2. **Authentication → Sign In / Providers → Email.** Leave **"Confirm email"
   enabled**. This is what makes `/verify` reachable and stops an unconfirmed
   address obtaining a session by signing in directly.

3. **Authentication → Emails → Templates → Confirm signup.** Switch the template
   to the **"Email OTP"** variant. This is required: the default template sends a
   confirmation *link*, but APEX asks the user to type a 6-digit code. Without
   this change no code is ever sent and nobody can complete registration.

4. **Authentication → URL Configuration.** Add your local and deployed origins to
   the redirect allowlist so `emailRedirectTo` is honoured for the link flow.

5. Restart the dev servers after editing env files. `NEXT_PUBLIC_*` values are
   inlined at build time, so delete `frontend/.next` if a change appears not to
   take effect.

### Applying the profiles migration (optional)

```bash
# via the SQL editor
supabase/migrations/0001_create_profiles.sql
```

Nothing in Story 1.2 depends on it — see
[Where name and age are stored](#where-name-and-age-are-stored). Projects and
Tasks tables belong to Story 1.3.

Never commit `.env`, `.env.local`, the service-role key, or the JWT secret.
Only `.env.example` is tracked.

## Repository layout

```
APEX/
├── frontend/          # Next.js app
│   └── src/
│       ├── app/
│       │   ├── (auth)/       # /signin, /create-account, /verify
│       │   └── (protected)/  # /dashboard
│       ├── components/       # AuthForm, CreateAccountForm, OtpForm, SignOutButton
│       ├── lib/              # data access layer, Server Actions, Supabase clients
│       └── proxy.ts          # session refresh (Next 16 name for middleware)
├── backend/           # FastAPI app
│   ├── src/apex_backend/
│   │   ├── api/v1/    # versioned routes
│   │   ├── auth/      # token verification + dependencies
│   │   ├── core/      # settings
│   │   └── models/    # Pydantic schemas
│   └── tests/
├── supabase/
│   └── migrations/    # optional SQL, not yet read by the app
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
- Rate limiting and CAPTCHA on signup/verification are Supabase dashboard
  settings, not application code. Turn them on for any public deployment.
- A 6-digit code has limited entropy, so the "Confirm email" setting alone is
  the real control; APEX does not add a second factor.
- A "signed in but unconfirmed" session cannot arise with "Confirm email" on,
  because Supabase refuses to issue one. That routing still exists and is
  defensive; it was tested by hand using a stand-in that hands out such a
  session on request.
- The `profiles` table is defined but unused by the app. Projects and Tasks
  tables are Story 1.3.
