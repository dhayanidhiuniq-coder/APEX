/**
 * Email confirmation helpers.
 *
 * Shared by the Server Actions, the server-side data access layer and
 * `proxy.ts`, so the definition of "this address is confirmed" lives in exactly
 * one place.
 *
 * Deliberately not `server-only`: this is pure logic with no secrets in it.
 */

/**
 * Whether a Supabase user record counts as email-confirmed.
 *
 * Two timestamps are consulted because they are not interchangeable:
 *
 * - `email_confirmed_at` is set when this specific address is confirmed. It is
 *   the authoritative signal for APEX, which only ever authenticates by email.
 * - `confirmed_at` is set when the account is confirmed by any method, and
 *   remains null for accounts whose address arrived already verified through an
 *   identity provider.
 *
 * Accepting either means a legitimately confirmed user is never trapped on the
 * verification screen by an implementation detail of how they signed up.
 */
export function isEmailConfirmed(
  emailConfirmedAt: string | null | undefined,
  confirmedAt?: string | null,
): boolean {
  return Boolean(emailConfirmedAt) || Boolean(confirmedAt);
}