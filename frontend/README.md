# APEX Frontend

Next.js 16 (App Router), TypeScript and Tailwind CSS. Runs on
<http://localhost:3000>.

## Setup

```bash
npm install
cp .env.example .env.local
```

Then fill in the Supabase values:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The auth pages show setup instructions if these are missing, so the app still
builds and renders without them.

Account creation also needs the Supabase project configured to send a **6-digit
code** rather than a link — see the root README, "Supabase setup".

## Run

```bash
npm run dev
```

From the repository root, `npm run dev` starts this and the backend together.

## Routes

| Route             | Access  | Description                                     |
| ----------------- | ------- | ----------------------------------------------- |
| `/`               | Public  | Landing page                                    |
| `/signin`         | Public  | Sign in; honours `?next=`                       |
| `/create-account` | Public  | Create an account (name, age, email, password)  |
| `/verify`         | Public  | Email code entry; requires a pending registration |
| `/signup`         | Public  | Redirects to `/create-account`                  |
| `/dashboard`      | Private | Projects list, create/delete UI, and account details |

## Authentication design

Supabase Auth is the identity provider. `@supabase/ssr` keeps the session in
**cookies** rather than `localStorage`, so the access token is not exposed to
client-side JavaScript and the Next.js server can read the same session.

There are two layers, and both matter:

1. **`src/proxy.ts`** (Next 16's name for `middleware.ts`) refreshes the session
   before rendering and routes callers: signed-out visitors away from
   `/dashboard`, signed-in-but-unconfirmed users to `/verify`. This is a fast
   first line of defence, not a guarantee: proxy logic can be bypassed by
   requesting a route handler directly.
2. **`src/lib/auth.ts`** is the authoritative gate. `requireVerifiedUser()` runs
   on the server during render and calls `redirect()`, so a protected page body
   never executes without a valid, confirmed session, regardless of what
   happened in `proxy.ts`.

`getUser()` is used rather than `getSession()` because it revalidates the token
with the auth server instead of trusting the cookie contents.

### Account creation and verification

Registration and code entry are **Server Actions** (`src/lib/account-actions.ts`),
not client-side handlers. That keeps the confirmation handshake on the server:
the one-time code is submitted straight to Supabase and never passes through
client state, application state or a log line.

`useActionState` carries a typed result back so each validation message can be
rendered beside its own input.

Two details that are easy to get wrong and are worth knowing before editing:

- **A `"use server"` module may only export async functions.** Exporting a state
  constant from one makes it silently `undefined` at runtime; `tsc` and
  `next build` both pass, and the page then throws on `state.errors`. The
  initial-state constants live in `src/lib/account-state.ts` for this reason.
- **`redirect()` must be called outside `try`/`catch` in a Server Action**, or
  the redirect is swallowed as a failure.

### Structure

```
src/
├── app/
│   ├── (auth)/        # signin, create-account, verify + shared layout
│   ├── (protected)/   # dashboard + layout calling requireVerifiedUser()
│   └── page.tsx
├── components/        # AuthForm, CreateAccountForm, OtpForm, FormField, SignOutButton
├── lib/
│   ├── auth.ts            # data access layer (server-only)
│   ├── auth-errors.ts     # allowlisted error message normalisation
│   ├── account-actions.ts # Server Actions: signup, verify, resend
│   ├── account-state.ts   # action state types + initial values
│   ├── backend-api.ts     # server-only authenticated fetch bridge
│   ├── projects.ts        # Projects data access + response validation
│   ├── project-state.ts   # Projects action state and field limits
│   ├── email-confirmation.ts  # what counts as a confirmed address
│   ├── otp-session.ts     # httpOnly cookie holding the pending address
│   ├── request-origin.ts  # origin for Supabase's emailRedirectTo
│   ├── safe-redirect.ts   # validates the ?next= parameter
│   ├── supabase/          # config, browser client, server client, proxy helper
│   └── validation.ts      # shared field rules
└── proxy.ts
```

### Calling the backend

`fetchBackendIdentity()` in `src/lib/auth.ts` reads the session on the server
and sends the access token to the FastAPI backend as a bearer token. The token
never reaches the browser, and the backend verifies it independently before
returning an identity.

`src/lib/backend-api.ts` is the same server-only pattern for Projects. It reads
the session, attaches the bearer token, and returns a small result union so the
dashboard can show a friendly error instead of backend internals.

### Projects UI

`/dashboard` lists the signed-in user's projects and supports create and delete.
Reads use the server-side bridge above. Mutations are Server Actions in
`src/app/(protected)/dashboard/actions.ts`; each one calls
`requireVerifiedUser()` again before forwarding the request. The browser never
supplies an owner id.

The page has responsive empty, loading, and error states. Native `<dialog>`
handles the create form, and delete asks for confirmation before calling the
action.

### Redirect safety

`?next=` is attacker-controlled, so `safeNextPath()` rejects anything that is not
a single-slash-prefixed in-app path. Protocol-relative targets such as
`//evil.com` are refused to prevent an open redirect.

## Verify

```bash
npx tsc --noEmit --incremental false
npx eslint "src/app/(protected)/dashboard" src/lib/backend-api.ts src/lib/project-state.ts src/lib/projects.ts
npx next build        # production build
```

## Notes

- `NEXT_PUBLIC_*` values are inlined at build time. After editing `.env.local`,
  restart the dev server; if a change appears not to apply, delete `.next`.
- Only public Supabase values may be used in a `NEXT_PUBLIC_` variable. The
  service-role key and JWT secret must never reach the browser.
- The Projects dashboard needs `DATABASE_URL` on the backend and the Story 1.3
  Alembic revision applied. Until then it shows a friendly unavailable message;
  RLS isolation and production verification remain outstanding.
- This UI is functional, not final.
