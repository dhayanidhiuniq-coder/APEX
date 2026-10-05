/**
 * Shared types and initial state for the account-creation Server Actions.
 *
 * These live outside `account-actions.ts` on purpose. A `"use server"` module may
 * only export async functions, so exporting the initial-state constants from
 * there makes them `undefined` at runtime — the action's state comes back as
 * `undefined` and any `state.errors` access throws. TypeScript and
 * `next build` both stay silent about it.
 */

import type { FieldErrors } from "./validation";

/**
 * State returned to the Create Account form after a submission.
 *
 * `errors` is keyed by field so each message can be rendered beside its input;
 * `formError` is for failures that belong to the submission as a whole.
 *
 * Deliberately carries no field values back. The form keeps the non-secret
 * fields under its own control, and echoing the password back into the DOM —
 * even once — would put it somewhere it was never meant to be.
 */
export type CreateAccountState = {
  errors: FieldErrors;
  formError: string | null;
};

export const INITIAL_CREATE_ACCOUNT_STATE: CreateAccountState = {
  errors: {},
  formError: null,
};

/** State for the code-entry and resend forms. */
export type OtpState = {
  /** Message for the code itself. */
  error: string | null;
  /** Success or guidance text, shown without stealing focus. */
  notice: string | null;
};

export const INITIAL_OTP_STATE: OtpState = { error: null, notice: null };