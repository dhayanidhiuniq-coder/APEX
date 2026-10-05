"use client";

/**
 * Shared email/password form used by both the sign-in and sign-up pages.
 *
 * Talks to Supabase Auth directly. The resulting session is written to cookies
 * by `@supabase/ssr`, so the token is never placed in application state.
 */

import { useState, useTransition, type FormEvent } from "react";

import { NETWORK_FAILURE_MESSAGE, toDisplayableAuthError } from "@/lib/auth-errors";
import { createClient } from "@/lib/supabase/client";

type AuthMode = "signin" | "signup";

type AuthFormProps = {
  mode: AuthMode;
  /** Path to navigate to once authenticated. */
  redirectTo: string;
};

type FormState = {
  error: string | null;
  notice: string | null;
};

const COPY: Record<AuthMode, { title: string; submit: string; pending: string }> = {
  signin: { title: "Sign in", submit: "Sign in", pending: "Signing in…" },
  signup: { title: "Create your account", submit: "Sign up", pending: "Creating account…" },
};


export function AuthForm({ mode, redirectTo }: AuthFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formState, setFormState] = useState<FormState>({ error: null, notice: null });
  // Covers the network round trip to Supabase Auth...
  const [isSubmitting, setIsSubmitting] = useState(false);
  // ...and the navigation that follows a successful sign-in.
  const [isNavigating, startTransition] = useTransition();

  const isSignUp = mode === "signup";
  const copy = COPY[mode];
  const isBusy = isSubmitting || isNavigating;
  const isDisabled = isBusy || email.trim() === "" || password === "";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (isBusy) {
      return;
    }

    setFormState({ error: null, notice: null });
    setIsSubmitting(true);

    let succeeded = false;
    let notice: string | null = null;
    let failure: string | null = null;

    try {
      const supabase = createClient();

      const result = isSignUp
        ? await supabase.auth.signUp({
            email: email.trim(),
            password,
            // Send the new user straight back into the app once confirmed.
            options: { emailRedirectTo: `${window.location.origin}${redirectTo}` },
          })
        : await supabase.auth.signInWithPassword({ email: email.trim(), password });

      if (result.error) {
        failure = toDisplayableAuthError(result.error.message);
      } else if (isSignUp && !result.data.session) {
        notice = "Account created. Check your inbox to confirm the address, then sign in.";
      } else {
        succeeded = true;
      }
    } catch {
      // `signIn`/`signUp` resolve with an error object for auth problems, but a
      // transport failure can reject. Never leave the form stuck submitting.
      failure = NETWORK_FAILURE_MESSAGE;
    }

    setIsSubmitting(false);

    if (failure !== null) {
      setFormState({ error: failure, notice: null });
      return;
    }

    if (notice !== null) {
      setFormState({ error: null, notice });
      return;
    }

    if (succeeded) {
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
          aria-describedby={formState.error ? "auth-error" : undefined}
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-600 disabled:opacity-60 dark:border-neutral-700"
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
          autoComplete={isSignUp ? "new-password" : "current-password"}
          required
          minLength={8}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="At least 8 characters"
          disabled={isBusy}
          className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none focus:border-neutral-600 disabled:opacity-60 dark:border-neutral-700"
        />
      </div>

      {formState.error ? (
        <p id="auth-error" role="alert" className="text-sm text-red-600 dark:text-red-400">
          {formState.error}
        </p>
      ) : null}

      {formState.notice ? (
        <p role="status" className="text-sm text-neutral-600 dark:text-neutral-300">
          {formState.notice}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={isDisabled}
        className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200"
      >
        {isBusy ? copy.pending : copy.submit}
      </button>

      <p className="sr-only" aria-live="polite">
        {copy.title} form status: {isBusy ? "submitting" : "idle"}
      </p>
    </form>
  );
}
