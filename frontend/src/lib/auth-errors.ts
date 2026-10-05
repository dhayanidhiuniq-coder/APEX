/**
 * Presentation helpers for authentication errors.
 *
 * Kept separate from the components so both the sign-in form and the sign-out
 * button normalise messages the same way.
 */

/**
 * Shown when the browser cannot reach the auth server at all. The raw
 * `Failed to fetch` string tells the user nothing actionable.
 */
export const NETWORK_FAILURE_MESSAGE =
  "Could not reach the authentication service. Check your connection and that Supabase is configured.";

/**
 * Transport failures that the browser or the Supabase SDK surface verbatim.
 * These are meaningless to a user, so they are replaced with something
 * actionable.
 */
const NETWORK_FAILURE_PATTERNS = [
  "failed to fetch",
  "fetch failed",
  "load failed",
  "networkerror",
  "network request failed",
];

/**
 * Turn a Supabase auth error into a message safe and useful to display.
 *
 * Genuine auth failures ("Invalid login credentials") are already written for
 * users, so they pass through unchanged. Transport failures are replaced.
 *
 * Note this only rewrites wording. It never discloses anything about the
 * account, and no raw token or credential is ever interpolated into a message.
 */
export function toDisplayableAuthError(message: string): string {
  const normalized = message.trim().toLowerCase();

  if (NETWORK_FAILURE_PATTERNS.some((pattern) => normalized.includes(pattern))) {
    return NETWORK_FAILURE_MESSAGE;
  }

  return message;
}

/** Shown for any auth failure with no recognised, user-safe explanation. */
export const GENERIC_AUTH_ERROR =
  "Something went wrong on our side. Please try again in a moment.";

type MessageRule = {
  /** Fragments that identify this failure. Matched case-insensitively. */
  matches: string[];
  message: string;
};

/**
 * Account creation failures, mapped to wording APEX controls.
 *
 * Supabase's own strings are user-facing and worth keeping, but they are
 * translated and reworded between releases. Matching on an allowlist means an
 * unrecognised or newly-localised response can never leak raw upstream text
 * into the UI — it falls through to {@link GENERIC_AUTH_ERROR} instead.
 */
const SIGNUP_RULES: MessageRule[] = [
  {
    matches: ["already registered", "already been registered", "user_already_exists"],
    message: "An account with that email already exists. Try signing in instead.",
  },
  {
    matches: ["password should be at least", "weak_password"],
    message: "Choose a longer password.",
  },
  {
    matches: ["email not confirmed", "not confirmed"],
    message: "That email address has not been confirmed yet.",
  },
  {
    matches: ["email address", "invalid email", "unable to validate email"],
    message: "Enter a valid email address.",
  },
  {
    matches: ["password"],
    message: "That password was not accepted.",
  },
  {
    matches: ["rate limit", "too many requests", "security purposes"],
    message: "Too many attempts. Wait a minute and try again.",
  },
  {
    matches: ["email address not allowed", "not allowed"],
    message: "That email address cannot be used to register.",
  },
];

/**
 * OTP failures, mapped to wording APEX controls.
 *
 * Deliberately stricter than {@link SIGNUP_RULES}: nothing is passed through
 * unrecognised. The submitted code must never reach the screen, and this is the
 * single place that decides what a code failure looks like.
 *
 * Note there is no separate "wrong code" and "expired code" wording. Supabase
 * answers a mistyped code and an elapsed one with the same `otp_expired`
 * response and does not distinguish them, so claiming a specific cause would be
 * a guess. The message covers both and points at Resend, which is the action that
 * actually rescues either situation.
 */
const OTP_RULES: MessageRule[] = [
  {
    matches: ["expired", "invalid", "token", "otp", "verification"],
    message: "That code is not correct or has expired. Check it, or request a new one.",
  },
  {
    matches: ["rate limit", "too many requests", "security purposes"],
    message: "Too many attempts. Wait a minute and request a new code.",
  },
  {
    matches: ["already confirmed", "not found", "no user"],
    message: "We could not find a pending registration for that address.",
  },
];

function isNetworkFailure(message: string): boolean {
  const normalized = message.trim().toLowerCase();

  return NETWORK_FAILURE_PATTERNS.some((pattern) => normalized.includes(pattern));
}

function applyRules(message: string, rules: MessageRule[], fallback: string): string {
  if (isNetworkFailure(message)) {
    return NETWORK_FAILURE_MESSAGE;
  }

  const normalized = message.trim().toLowerCase();
  const rule = rules.find((candidate) =>
    candidate.matches.some((pattern) => normalized.includes(pattern)),
  );

  return rule ? rule.message : fallback;
}

/** Map a `signUp` failure to a message APEX is happy to display. */
export function toDisplayableSignupError(message: string): string {
  return applyRules(message, SIGNUP_RULES, GENERIC_AUTH_ERROR);
}

/**
 * Map a `verifyOtp` / `resend` failure to a message APEX is happy to display.
 *
 * Never interpolates the submitted code, and never passes upstream text
 * through unrecognised.
 */
export function toDisplayableOtpError(message: string): string {
  return applyRules(message, OTP_RULES, GENERIC_AUTH_ERROR);
}
