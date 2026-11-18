import Link from "next/link";

import { SignOutButton } from "@/components/sign-out-button";
import { ThemeToggle } from "@/components/theme-toggle";
import { requireVerifiedUser } from "@/lib/auth";

/**
 * Layout for every signed-in page.
 *
 * `requireVerifiedUser()` runs on the server during render and redirects to
 * `/signin` when there is no valid session, or to `/verify` when the session's
 * email address has not been confirmed. This is the authoritative gate:
 * bypassing `proxy.ts` still lands on a redirect, because the page body never
 * executes.
 */
export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const user = await requireVerifiedUser("/dashboard");

  return (
    <div className="flex min-h-full flex-1 flex-col">
      <header className="flex items-center justify-between gap-4 border-b border-neutral-200 px-6 py-4 dark:border-neutral-800">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-sm font-semibold">
            APEX
          </Link>
          <Link href="/dashboard" className="text-sm text-neutral-600 hover:underline dark:text-neutral-300">
            Dashboard
          </Link>
        </div>

        <div className="flex items-center gap-4">
          <span className="hidden text-sm text-neutral-600 sm:inline dark:text-neutral-300">
            {user.email}
          </span>
          <ThemeToggle />
          <SignOutButton />
        </div>
      </header>

      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">{children}</main>
    </div>
  );
}
