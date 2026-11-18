import Link from "next/link";
import type { ReactNode } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { isSupabaseConfigured } from "@/lib/supabase/config";

/**
 * Shared chrome for the sign-in and sign-up pages.
 *
 * Shows a setup notice when Supabase has not been configured yet, so a fresh
 * clone fails with actionable instructions rather than a blank error. Signed-in
 * users are redirected away by `proxy.ts`.
 */
export default async function AuthLayout({ children }: { children: ReactNode }) {
  const configured = isSupabaseConfigured();

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center gap-6 px-6 py-16">
      <div className="flex items-baseline justify-between">
        <Link href="/" className="text-sm font-medium hover:underline">
          &larr; APEX
        </Link>
        <ThemeToggle />
      </div>

      {configured ? (
        <div className="rounded-lg border border-neutral-200 p-6 shadow-sm dark:border-neutral-800">
          {children}
        </div>
      ) : (
        <div className="flex flex-col gap-4 rounded-lg border border-amber-300 bg-amber-50 p-6 dark:border-amber-700 dark:bg-amber-950">
          <h1 className="text-lg font-semibold">Supabase is not configured</h1>
          <p className="text-sm text-neutral-700 dark:text-neutral-200">
            Set <code className="font-mono">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
            <code className="font-mono">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in{" "}
            <code className="font-mono">frontend/.env.local</code>, then restart the dev server.
            See <code className="font-mono">.env.example</code> for the full list.
          </p>
        </div>
      )}
    </main>
  );
}
