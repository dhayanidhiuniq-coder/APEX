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

The sign-in and sign-up pages show setup instructions if these are missing, so
the app still builds and renders without them.

## Run

```bash
npm run dev
```

From the repository root, `npm run dev` starts this and the backend together.

## Routes

| Route        | Access  | Description                               |
| ------------ | ------- | ----------------------------------------- |
| `/`          | Public  | Landing page                              |
| `/signin`    | Public  | Sign in; honours `?next=`                 |
| `/signup`    | Public  | Create an account                         |
| `/dashboard` | Private | Protected area; redirects to `/signin`    |

## Authentication design

Supabase Auth is the identity provider. `@supabase/ssr` keeps the session in
**cookies** rather than `localStorage`, so the access token is not exposed to
client-side JavaScript and the Next.js server can read the same session.

There are two layers, and both matter:

1. **`src/proxy.ts`** (Next 16's name for `middleware.ts`) refreshes the session
   before rendering and redirects signed-out users away from `/dashboard`. This
   is a fast first line of defence, not a guarantee: proxy logic can be bypassed
   by requesting a route handler directly.
2. **`src/lib/auth.ts`** is the authoritative gate. `requireUser()` runs on the
   server during render and calls `redirect()`, so a protected page body never
   executes for an unauthenticated request, regardless of what happened in
   `proxy.ts`.

`getUser()` is used rather than `getSession()` because it revalidates the token
with the auth server instead of trusting the cookie contents.

### Calling the backend

`fetchBackendIdentity()` in `src/lib/auth.ts` reads the session on the server
and sends the access token to the FastAPI backend as a bearer token. The token
never reaches the browser, and the backend verifies it independently before
returning an identity.

### Structure

```
src/
├── app/
│   ├── (auth)/        # signin, signup + shared layout
│   ├── (protected)/   # dashboard + layout that calls requireUser()
│   └── page.tsx
├── components/        # AuthForm, SignOutButton
├── lib/
│   ├── auth.ts        # data access layer (server-only)
│   ├── auth-errors.ts # error message normalisation
│   ├── safe-redirect.ts # validates the ?next= parameter
│   └── supabase/      # config, browser client, server client, proxy helper
└── proxy.ts
```

### Redirect safety

`?next=` is attacker-controlled, so `safeNextPath()` rejects anything that is not
a single-slash-prefixed in-app path. Protocol-relative targets such as
`//evil.com` are refused to prevent an open redirect.

## Verify

```bash
npx tsc --noEmit      # typecheck
npx next build        # production build
```

## Notes

- `NEXT_PUBLIC_*` values are inlined at build time. After editing `.env.local`,
  restart the dev server; if a change appears not to apply, delete `.next`.
- Only public Supabase values may be used in a `NEXT_PUBLIC_` variable. The
  service-role key and JWT secret must never reach the browser.
- This UI is functional, not final.
