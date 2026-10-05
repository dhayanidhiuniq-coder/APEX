"use server";

/**
 * Server Actions for account creation and email confirmation.
 *
 * These run on the Next.js server. Keeping them server-side means the one-time
 * confirmation code is submitted straight to Supabase and never passes through
 * client-side state, application state or a log line.
 *
 * Credentials are never persisted by APEX. Only the name and age supplied on the
 * form are forwarded, as Supabase user metadata; the password goes to Supabase
 * Auth and nowhere else.
 */

import { redirect } from "next/navigation";

import {
  GENERIC_AUTH_ERROR,
  toDisplayableOtpError,
  toDisplayableSignupError,
} from "@/lib/auth-errors";
import { isEmailConfirmed } from "@/lib/email-confirmation";
import {
  forgetPendingVerification,
  readPendingVerification,
  rememberPendingVerification,
} from "@/lib/otp-session";
import { resolveRequestOrigin } from "@/lib/request-origin";
import { safeNextPath } from "@/lib/safe-redirect";
import { isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import {
  validateAge,
  validateEmail,
  validateName,
  validateOtp,
  validatePassword,
  validatePasswordConfirmation,
  type FieldErrors,
} from "@/lib/validation";

import type { CreateAccountState, OtpState } from "./account-state";

/**
 * Message shown when `/verify` is reached without a pending registration.
 *
 * Reached by opening the URL directly, or by returning after the cookie expired.
 */
const NO_PENDING_VERIFICATION_MESSAGE =
  "Start by creating an account, or sign in if you already have one.";

/**
 * Create the account with Supabase Auth and start email confirmation.
 *
 * On success the user is sent to `/verify`. When Supabase issues a session
 * immediately — which it does if the project has "Confirm email" switched off —
 * the existing session is preserved and the user continues straight into the
 * app rather than being asked for a code that was never sent.
 */
export async function startAccountCreation(
  _previousState: CreateAccountState,
  formData: FormData,
): Promise<CreateAccountState> {
  const name = validateName(readField(formData, "name"));
  const age = validateAge(readField(formData, "age"));
  const email = validateEmail(readField(formData, "email"));
  const password = validatePassword(readField(formData, "password"));
  const confirmation = validatePasswordConfirmation(
    readField(formData, "password"),
    readField(formData, "confirmPassword"),
  );

  // Every field is validated before any network call, so an obviously invalid
  // submission never reaches Supabase.
  const errors: FieldErrors = {
    ...(name.ok ? {} : name.errors),
    ...(age.ok ? {} : age.errors),
    ...(email.ok ? {} : email.errors),
    ...(password.ok ? {} : password.errors),
    ...(confirmation.ok ? {} : confirmation.errors),
  };

  if (!name.ok || !age.ok || !email.ok || !password.ok || !confirmation.ok) {
    return { errors, formError: null };
  }

  if (!isSupabaseConfigured()) {
    return {
      errors: {},
      formError:
        "Sign-up is not available because Supabase has not been configured on this server.",
    };
  }

  const next = safeNextPath(readField(formData, "next"));
  const origin = await resolveRequestOrigin();

  // `redirect()` throws to unwind the render, so it must never be called from
  // inside the try block below.
  let destination: string | null = null;
  let formError: string | null = null;

  try {
    const supabase = await createClient();

    const { data, error } = await supabase.auth.signUp({
      email: email.value,
      password: password.value,
      options: {
        // Profile data, not credentials. Supabase stores this on the user
        // record as user metadata, and `supabase/migrations` mirrors it into
        // `public.profiles` with a database trigger.
        data: { name: name.value, age: age.value },
        ...(origin ? { emailRedirectTo: `${origin}${next}` } : {}),
      },
    });

    if (error) {
      formError = toDisplayableSignupError(error.message);
    } else if (data.session) {
      // Email confirmation is disabled on this project: the user is already
      // verified and signed in.
      destination = next;
    } else {
      // A session is expected to be absent, so confirmation is required.
      await rememberPendingVerification(email.value);
      destination = "/verify";
    }
  } catch {
    formError = GENERIC_AUTH_ERROR;
  }

  if (destination !== null) {
    redirect(destination);
  }

  return { errors: {}, formError };
}

/**
 * Verify the confirmation code and establish the session.
 *
 * Supabase returns a session on success, so verifying the code is what signs
 * the user in. The pending-address cookie is cleared afterwards.
 */
export async function verifyEmailOtp(
  _previousState: OtpState,
  formData: FormData,
): Promise<OtpState> {
  const email = await readPendingVerification();

  if (email === null) {
    return { error: NO_PENDING_VERIFICATION_MESSAGE, notice: null };
  }

  const otp = validateOtp(readField(formData, "otp"));

  if (!otp.ok) {
    return { error: otp.errors.otp ?? "Enter the code from your email.", notice: null };
  }

  // Someone who is already signed in and confirmed does not need to verify
  // again; let them through rather than reporting a bogus failure.
  if (await isAlreadyConfirmed()) {
    await forgetPendingVerification();
    redirect("/dashboard");
  }

  const next = safeNextPath(readField(formData, "next"));

  let error: string | null = null;
  let destination: string | null = null;

  try {
    const supabase = await createClient();

    const { error: verifyError } = await supabase.auth.verifyOtp({
      email,
      // The code is forwarded to Supabase and nowhere else. It is never logged
      // and never interpolated into a returned message.
      token: otp.value,
      type: "email",
    });

    if (verifyError) {
      error = toDisplayableOtpError(verifyError.message);
    } else {
      // Supabase established the session as part of verification.
      await forgetPendingVerification();
      destination = next;
    }
  } catch {
    error = GENERIC_AUTH_ERROR;
  }

  if (destination !== null) {
    redirect(destination);
  }

  return { error, notice: null };
}

/**
 * Send a fresh confirmation code to the pending address.
 *
 * The address comes from the cookie, so this form submits no fields of its own;
 * the parameters exist only to satisfy the `useActionState` action signature.
 */
export async function resendEmailOtp(
  _previousState: OtpState,
  _formData: FormData,
): Promise<OtpState> {
  const email = await readPendingVerification();

  if (email === null) {
    return { error: NO_PENDING_VERIFICATION_MESSAGE, notice: null };
  }

  try {
    const supabase = await createClient();

    // `resend` only accepts a signup or email_change type.
    const { error } = await supabase.auth.resend({ type: "signup", email });

    if (error) {
      return { error: toDisplayableOtpError(error.message), notice: null };
    }
  } catch {
    return { error: GENERIC_AUTH_ERROR, notice: null };
  }

  return {
    error: null,
    notice: "A new code is on its way. It replaces any code you already had.",
  };
}

/** Whether there is a signed-in user whose email is already confirmed. */
async function isAlreadyConfirmed(): Promise<boolean> {
  if (!isSupabaseConfigured()) {
    return false;
  }

  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    return Boolean(
      user && isEmailConfirmed(user.email_confirmed_at, user.confirmed_at),
    );
  } catch {
    return false;
  }
}

/**
 * Read a string field from form data.
 *
 * Everything arriving here is untrusted. The `typeof` guard keeps a malformed
 * `FormData` value from becoming `undefined` and crashing a validator.
 */
function readField(formData: FormData, name: string): string {
  const value = formData.get(name);

  return typeof value === "string" ? value : "";
}