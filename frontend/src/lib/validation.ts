/**
 * Shared field validation for the Create Account form.
 *
 * Kept out of the components so the rules have one definition and the same
 * messages are used wherever a value is accepted.
 *
 * These checks exist for fast, specific feedback in the browser. They are not a
 * security boundary: every value is re-validated where it is actually used, and
 * Supabase Auth remains the only authority on credentials.
 */

export const MIN_AGE = 0;
export const MAX_AGE = 120;

/**
 * Supabase's hosted projects require at least 8 characters by default. The
 * existing sign-in form already declares `minLength={8}`, so this matches what
 * APEX has always told users.
 */
export const MIN_PASSWORD_LENGTH = 8;

/** Supabase email confirmation OTPs are 6 digits. */
export const OTP_LENGTH = 6;

/** A field name used as the key of a per-field error map. */
export type FieldName = "name" | "age" | "email" | "password" | "confirmPassword" | "otp";

export type FieldErrors = Partial<Record<FieldName, string>>;

export type ValidationResult<T> =
  | { ok: true; value: T }
  | { ok: false; errors: FieldErrors };

/** Length bounds for a person's name. Deliberately generous. */
const MAX_NAME_LENGTH = 120;
const MAX_EMAIL_LENGTH = 254;

/**
 * Deliberately permissive. The aim is to catch typos, not to out-parse RFC 5322.
 * A false rejection here would lock a real user out of their own account, which
 * is far worse than accepting a malformed address that Supabase will reject
 * with a clearer message.
 */
const EMAIL_PATTERN = /^[^\s@]+@[^\s@.]+(\.[^\s@.]+)+$/;

export function validateName(raw: string): ValidationResult<string> {
  const value = raw.trim();

  if (value.length === 0) {
    return { ok: false, errors: { name: "Enter your full name." } };
  }

  if (value.length > MAX_NAME_LENGTH) {
    return {
      ok: false,
      errors: { name: `Name must be ${MAX_NAME_LENGTH} characters or fewer.` },
    };
  }

  return { ok: true, value };
}

export function validateAge(raw: string): ValidationResult<number> {
  const value = raw.trim();

  if (value.length === 0) {
    return { ok: false, errors: { age: "Enter your age." } };
  }

  // Reject decimals, exponents and padding before parsing: `Number()` would
  // silently accept "0x10", "1e2" and " 12 ".
  //
  // A leading minus is allowed through this check on purpose, so a negative age
  // is reported against the allowed range rather than as a malformed number.
  if (!/^-?\d{1,3}$/.test(value)) {
    return { ok: false, errors: { age: "Age must be a whole number." } };
  }

  const age = Number(value);

  if (age < MIN_AGE || age > MAX_AGE) {
    return { ok: false, errors: { age: `Age must be between ${MIN_AGE} and ${MAX_AGE}.` } };
  }

  return { ok: true, value: age };
}

export function validateEmail(raw: string): ValidationResult<string> {
  const value = raw.trim();

  if (value.length === 0) {
    return { ok: false, errors: { email: "Enter your email address." } };
  }

  if (value.length > MAX_EMAIL_LENGTH || !EMAIL_PATTERN.test(value)) {
    return { ok: false, errors: { email: "Enter a valid email address." } };
  }

  return { ok: true, value: value.toLowerCase() };
}

export function validatePassword(raw: string): ValidationResult<string> {
  if (raw.length === 0) {
    return { ok: false, errors: { password: "Choose a password." } };
  }

  if (raw.length < MIN_PASSWORD_LENGTH) {
    return {
      ok: false,
      errors: {
        password: `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`,
      },
    };
  }

  return { ok: true, value: raw };
}

export function validatePasswordConfirmation(
  password: string,
  confirmation: string,
): ValidationResult<string> {
  if (confirmation.length === 0) {
    return { ok: false, errors: { confirmPassword: "Re-enter your password." } };
  }

  if (confirmation !== password) {
    return { ok: false, errors: { confirmPassword: "Passwords do not match." } };
  }

  return { ok: true, value: confirmation };
}

/**
 * OTP codes are numeric and fixed length.
 *
 * The value is only ever length-checked and handed straight to Supabase. It is
 * never logged, never echoed into a message and never stored.
 */
export function validateOtp(raw: string): ValidationResult<string> {
  const value = raw.trim();

  if (value.length === 0) {
    return { ok: false, errors: { otp: "Enter the code from your email." } };
  }

  if (!/^\d+$/.test(value)) {
    return { ok: false, errors: { otp: "The code must contain only digits." } };
  }

  if (value.length !== OTP_LENGTH) {
    return {
      ok: false,
      errors: { otp: `The code is ${OTP_LENGTH} digits.` },
    };
  }

  return { ok: true, value };
}