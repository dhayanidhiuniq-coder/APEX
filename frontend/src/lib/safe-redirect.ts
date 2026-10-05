/**
 * Redirect target validation.
 *
 * `?next=` is attacker-controllable, so it must never be passed to a redirect
 * verbatim. Only same-origin, absolute paths are accepted.
 */

const DEFAULT_AUTH_LANDING = "/dashboard";

/**
 * Return a safe in-app redirect target.
 *
 * Anything that is not a single-slash-prefixed path (protocol-relative
 * `//evil.com`, absolute URLs, backslash tricks) falls back to the dashboard.
 */
export function safeNextPath(value: string | string[] | undefined): string {
  const candidate = Array.isArray(value) ? value[0] : value;

  if (!candidate) {
    return DEFAULT_AUTH_LANDING;
  }

  if (!candidate.startsWith("/")) {
    return DEFAULT_AUTH_LANDING;
  }

  // `//host` and `/\host` are protocol-relative and would leave the app.
  if (candidate.startsWith("//") || candidate.startsWith("/\\")) {
    return DEFAULT_AUTH_LANDING;
  }

  return candidate;
}
