import { fetchBackendIdentity, requireVerifiedUser } from "@/lib/auth";

/**
 * Protected application area.
 *
 * Two identities are shown on purpose:
 *
 * - `user` comes from the Supabase session on the Next.js server.
 * - `backendIdentity` comes from `GET /api/v1/me` on the FastAPI backend,
 *   which verifies the same access token independently.
 *
 * Having both proves the token the browser holds is the token the backend
 * trusts, which is the contract Stories 1.3+ will build on.
 */
export default async function DashboardPage() {
  const user = await requireVerifiedUser("/dashboard");
  const backendIdentity = await fetchBackendIdentity();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          You are signed in and your email is confirmed. This area is only reachable
          with a valid session.
        </p>
      </div>

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
          <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            Identity from Supabase session
          </h2>
          <p className="font-mono text-sm break-all">id: {user.id}</p>
          <p className="text-sm break-all">email: {user.email ?? "—"}</p>
          <p className="text-xs text-neutral-500 dark:text-neutral-400">
            email confirmed: {user.emailVerified ? "yes" : "no"}
          </p>
        </article>

        <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
          <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            Profile
          </h2>
          {user.profile ? (
            <>
              <p className="text-sm break-all">name: {user.profile.name}</p>
              <p className="text-sm">age: {user.profile.age}</p>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Supplied on the Create Account form. Held by Supabase Auth, not by APEX.
              </p>
            </>
          ) : (
            <p className="text-sm text-neutral-600 dark:text-neutral-300">
              No name and age on this account. Accounts created before the Create
              Account flow have no profile data.
            </p>
          )}
        </article>

        <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
          <h2 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
            Identity verified by backend
          </h2>

          {backendIdentity ? (
            <>
              <p className="font-mono text-sm break-all">id: {backendIdentity.id}</p>
              <p className="text-sm break-all">email: {backendIdentity.email ?? "—"}</p>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                GET /api/v1/me accepted the access token.
              </p>
            </>
          ) : (
            <p className="text-sm text-neutral-600 dark:text-neutral-300">
              The backend did not return an identity. It may not be running on{" "}
              <code className="font-mono">localhost:8000</code>, or{" "}
              <code className="font-mono">SUPABASE_URL</code> /{" "}
              <code className="font-mono">SUPABASE_ANON_KEY</code> may be unset on the backend.
            </p>
          )}
        </article>
      </section>

      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        Projects and tasks arrive in a later story. Nothing else is implemented yet.
      </p>
    </div>
  );
}
