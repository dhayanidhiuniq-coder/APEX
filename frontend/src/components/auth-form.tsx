"use client";

/**
 * Email and password sign-in form.
 *
 * Talks to Supabase Auth directly. The resulting session is written to cookies
 * by `@supabase/ssr`, so the token is never placed in application state.
 *
 * Registration deliberately lives in its own form (`CreateAccountForm`): it needs
 * five fields plus an email confirmation step, and it runs as a Server Action so
 * the confirmation code never passes through the browser. This component stays
 * the simple sign-in path it has always been.
 */

import { useState, useTransition, type FormEvent } from "react";

import { NETWORK_FAILURE_MESSAGE, toDisplayableAuthError } from "@/lib/auth-errors";
import { createClient } from "@/lib/supabase/client";
import { MIN_PASSWORD_LENGTH } from "@/lib/validation";

type AuthFormProps = {
  /** Path to navigate to once authenticated. */
  redirectTo: string;
};

export function AuthForm({ redirectTo }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  // Covers the network round trip to Supabase Auth...
  const [isSubmitting, setIsSubmitting] = useState(false);
  // ...and the navigation that follows a successful sign-in.
  const [isNavigating, startTransition] = useTransition();

  const isBusy = isSubmitting || isNavigating;
  const isDisabled = isBusy || email.trim() === "" || password === "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isBusy) {
      return;
    }

    setError(null);
    setIsSubmitting(true);

    let failure: string | null = null;
    let succeeded = false;

    try {
      const supabase = createClient();

      const result = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password,
      });

      if (result.error) {
        failure = toDisplayableAuthError(result.error.message);
      } else {
        succeeded = true;
      }
    } catch {
      // `signInWithPassword` resolves with an error object for auth problems, but
      // a transport failure can reject. Never leave the form stuck submitting.
      failure = NETWORK_FAILURE_MESSAGE;
    }

    setIsSubmitting(false);

    if (failure !== null) {
      setError(failure);
      return;
    }

    if (succeeded) {
      // A full navigation guarantees no server component keeps rendering the
      // signed-out view out of a cached router state.
      startTransition(() => {
        window.location.assign(redirectTo);
      });
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          disabled={isBusy}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? "auth-error" : undefined}
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 disabled:opacity-60 aria-invalid:border-red-500 aria-invalid:focus-visible:ring-red-500 dark:border-neutral-700 dark:focus-visible:ring-neutral-400 dark:aria-invalid:border-red-500 dark:aria-invalid:focus-visible:ring-red-500"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium" htmlFor="password">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          minLength={MIN_PASSWORD_LENGTH}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
          disabled={isBusy}
          aria-describedby={error ? "auth-error" : undefined}
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 disabled:opacity-60 dark:border-neutral-700 dark:focus-visible:ring-neutral-400"
        />
      </div>

      {error ? (
        <p id="auth-error" role="alert" className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isDisabled}
        className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 dark:focus-visible:ring-neutral-400"
      >
        {isBusy ? "Signing in…" : "Sign in"}
      </button>

      <p className="sr-only" aria-live="polite">
        Sign in form status: {isBusy ? "submitting" : "idle"}
      </p>
    </form>
  );
}
