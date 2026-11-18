"use client";

/**
 * Sign-out action.
 *
 * Clears the Supabase session and its cookies, then returns the user to the
 * sign-in page.
 */

import { useState } from "react";

import { createClient } from "@/lib/supabase/client";
import { toDisplayableAuthError } from "@/lib/auth-errors";

export function SignOutButton() {
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSignOut() {
    setIsPending(true);
    setError(null);

    try {
      const supabase = createClient();
      const { error: signOutError } = await supabase.auth.signOut();

      if (signOutError) {
        setError(toDisplayableAuthError(signOutError.message));
        setIsPending(false);
        return;
      }
    } catch {
      // A transport failure must not leave the button stuck in its pending
      // state with no way to retry.
      setError(toDisplayableAuthError("Failed to fetch"));
      setIsPending(false);
      return;
    }

    // A full navigation guarantees no server component keeps rendering the
    // signed-in view out of a cached router state.
    window.location.assign("/signin");
  }

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        type="button"
        onClick={handleSignOut}
        disabled={isPending}
        className="rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-neutral-700 dark:hover:bg-neutral-800 dark:focus-visible:ring-neutral-400"
      >
        {isPending ? "Signing out…" : "Sign out"}
      </button>

      {error ? (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
