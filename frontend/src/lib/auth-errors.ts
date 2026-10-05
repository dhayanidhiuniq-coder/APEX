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
