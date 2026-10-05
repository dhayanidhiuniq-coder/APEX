import Link from "next/link";

import { getUser } from "@/lib/auth";

/**
 * Public landing page.
 *
 * Shows where to go next based on whether a session exists. It deliberately
 * reveals nothing sensitive: only the user's own email.
 */
export default async function HomePage() {
  const user = await getUser();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col justify-center gap-8 px-6 py-16">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-semibold tracking-tight">APEX</h1>
        <p className="text-neutral-600 dark:text-neutral-300">
          Your private AI workspace. Sign in to continue.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {user ? (
          <>
            <span className="text-sm text-neutral-600 dark:text-neutral-300">
              Signed in as <span className="font-medium text-foreground">{user.email}</span>
            </span>
            <Link
              href="/dashboard"
              className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200"
            >
              Go to dashboard
            </Link>
          </>
        ) : (
          <>
            <Link
              href="/signin"
              className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200"
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-neutral-100 dark:border-neutral-700 dark:hover:bg-neutral-800"
            >
              Create an account
            </Link>
          </>
        )}
      </div>
    </main>
  );
}
