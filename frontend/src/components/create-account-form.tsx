"use client";

/**
 * Create Account form.
 *
 * Five fields, submitted to a Server Action rather than handled in the browser.
 * That keeps the confirmation handshake on the server and gives React's
 * `useActionState` a typed result to render per-field errors from — the pattern
 * Next 16 documents for forms with validation feedback.
 *
 * Name, age and email are controlled locally so a rejected submission does not
 * clear them. The password fields are left uncontrolled and are never returned
 * from the action, so a password cannot survive in the DOM after a failure.
 */

import { useActionState, useState } from "react";

import { FormField } from "@/components/form-field";
import { startAccountCreation } from "@/lib/account-actions";
import { INITIAL_CREATE_ACCOUNT_STATE } from "@/lib/account-state";
import { MAX_AGE, MIN_AGE, MIN_PASSWORD_LENGTH } from "@/lib/validation";

type CreateAccountFormProps = {
  /** Path to continue to once the account is usable. */
  next: string;
};

export function CreateAccountForm({ next }: CreateAccountFormProps) {
  const [state, formAction, pending] = useActionState(
    startAccountCreation,
    INITIAL_CREATE_ACCOUNT_STATE,
  );

  // Controlled so the browser preserves them; the Server Action never sees or
  // returns their previous values.
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [email, setEmail] = useState("");

  const { errors, formError } = state;

  return (
    <form action={formAction} className="flex flex-col gap-4" noValidate>
      <FormField
        name="name"
        label="Full name"
        autoComplete="name"
        required
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Ada Lovelace"
        disabled={pending}
        error={errors.name}
      />

      <FormField
        name="age"
        label="Age"
        // Numeric keypad on mobile, but `text` rather than `number` so the
        // Server Action receives exactly what was typed. `type="number"` silently
        // discards input that is not a valid number, which would hide the reason
        // the value was rejected.
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        maxLength={3}
        required
        value={age}
        onChange={(event) => setAge(event.target.value)}
        placeholder="36"
        disabled={pending}
        error={errors.age}
        hint={`Between ${MIN_AGE} and ${MAX_AGE}.`}
      />

      <FormField
        name="email"
        label="Email"
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@example.com"
        disabled={pending}
        error={errors.email}
      />

      <FormField
        name="password"
        label="Password"
        type="password"
        autoComplete="new-password"
        required
        minLength={MIN_PASSWORD_LENGTH}
        placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
        disabled={pending}
        error={errors.password}
      />

      <FormField
        name="confirmPassword"
        label="Confirm password"
        type="password"
        autoComplete="new-password"
        required
        disabled={pending}
        error={errors.confirmPassword}
      />

      {/* Carries the post-verification destination through the Server Action.
          `safeNextPath` validates it server-side before it is ever redirected to. */}
      <input type="hidden" name="next" value={next} />

      {formError ? (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {formError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 dark:focus-visible:ring-neutral-400"
      >
        {pending ? "Creating account…" : "Create account"}
      </button>

      <p className="sr-only" aria-live="polite">
        Create account form status: {pending ? "submitting" : "idle"}
      </p>
    </form>
  );
}
