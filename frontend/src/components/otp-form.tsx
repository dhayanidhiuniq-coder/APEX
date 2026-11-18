"use client";

/**
 * Email confirmation code form.
 *
 * Two sibling forms rather than one form with two submit buttons, because each
 * submit is a different Server Action with a different result shape: verifying
 * may sign the user in and redirect, while resending can only ever report back.
 *
 * The code is submitted to the server and never held here. This component shows
 * the error and the "we sent you something" message, nothing more.
 */

import { useActionState } from "react";

import { resendEmailOtp, verifyEmailOtp } from "@/lib/account-actions";
import { INITIAL_OTP_STATE } from "@/lib/account-state";
import { OTP_LENGTH } from "@/lib/validation";

type OtpFormProps = {
  /** Path to continue to once the code is accepted. */
  next: string;
};

export function OtpForm({ next }: OtpFormProps) {
  const [verifyState, verifyAction, verifying] = useActionState(
    verifyEmailOtp,
    INITIAL_OTP_STATE,
  );

  const [resendState, resendAction, resending] = useActionState(
    resendEmailOtp,
    INITIAL_OTP_STATE,
  );

  // Either request in flight disables both controls, so a user cannot trigger
  // both at once and race the resend against the verification.
  const busy = verifying || resending;

  return (
    <div className="flex flex-col gap-4">
      <form action={verifyAction} className="flex flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium" htmlFor="otp">
            Confirmation code
          </label>
          <input
            id="otp"
            name="otp"
            type="text"
            // `one-time-code` lets platform autofill fill it from the mail.
            autoComplete="one-time-code"
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={OTP_LENGTH}
            required
            disabled={busy}
            placeholder="000000"
            aria-invalid={verifyState.error ? true : undefined}
            aria-describedby={verifyState.error ? "otp-error" : "otp-hint"}
            className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 font-mono text-lg tracking-[0.4em] outline-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 disabled:opacity-60 aria-invalid:border-red-500 aria-invalid:focus-visible:ring-red-500 dark:border-neutral-700 dark:focus-visible:ring-neutral-400 dark:aria-invalid:border-red-500 dark:aria-invalid:focus-visible:ring-red-500"
          />

          {verifyState.error ? (
            <p id="otp-error" role="alert" className="text-sm text-red-600 dark:text-red-400">
              {verifyState.error}
            </p>
          ) : (
            <p id="otp-hint" className="text-xs text-neutral-500 dark:text-neutral-400">
              {OTP_LENGTH} digits, from the email we just sent.
            </p>
          )}
        </div>

        <input type="hidden" name="next" value={next} />

        <button
          type="submit"
          disabled={busy}
          className="rounded-md border border-black bg-black px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-white dark:bg-white dark:text-black dark:hover:bg-neutral-200 dark:focus-visible:ring-neutral-400"
        >
          {verifying ? "Verifying…" : "Verify email"}
        </button>
      </form>

      <form action={resendAction} className="flex flex-col gap-2">
        <button
          type="submit"
          disabled={busy}
          className="self-start rounded-md border border-neutral-300 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-neutral-700 dark:hover:bg-neutral-800 dark:focus-visible:ring-neutral-400"
        >
          {resending ? "Sending…" : "Resend code"}
        </button>

        {resendState.error ? (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {resendState.error}
          </p>
        ) : null}

        {resendState.notice ? (
          <p role="status" className="text-sm text-neutral-600 dark:text-neutral-300">
            {resendState.notice}
          </p>
        ) : null}
      </form>

      <p className="sr-only" aria-live="polite">
        Verification form status: {busy ? "submitting" : "idle"}
      </p>
    </div>
  );
}
