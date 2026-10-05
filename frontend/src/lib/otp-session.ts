import "server-only";

/**
 * Remembers which email address is awaiting confirmation.
 *
 * The Create Account Server Action sets this httpOnly cookie before redirecting
 * to `/verify`, and the verification and resend actions read it back.
 *
 * Why a cookie and not `?email=` in the URL:
 *
 * - An email address in the query string lands in browser history, and in any
 *   server, proxy or analytics access log on the way there. This keeps it out
 *   of all of them.
 * - The cookie is httpOnly, so client-side script cannot read or alter it, which
 *   keeps the "which account am I verifying" decision off the client entirely.
 */

import { cookies } from "next/headers";

import { validateEmail } from "./validation";

const PENDING_VERIFICATION_COOKIE = "apex-pending-verification";

/**
 * How long the address stays remembered. A confirmation code is valid for a few
 * minutes; half an hour is enough headroom for a slow typist without leaving a
 * stale address around indefinitely.
 */
const PENDING_VERIFICATION_MAX_AGE_SECONDS = 30 * 60;

/** Store the address awaiting confirmation and return it. */
export async function rememberPendingVerification(email: string): Promise<void> {
  const cookieStore = await cookies();

  cookieStore.set(PENDING_VERIFICATION_COOKIE, email, {
    httpOnly: true,
    // Deliberately not `secure`: the local stand-in is plain HTTP, and a
    // secure cookie would be dropped entirely over `http://localhost`.
    secure: false,
    sameSite: "lax",
    path: "/",
    maxAge: PENDING_VERIFICATION_MAX_AGE_SECONDS,
  });
}

/**
 * Read the address awaiting confirmation.
 *
 * The cookie is client-supplied data, so the value is re-validated as an email
 * before it is trusted. Anything unparseable is treated as "nothing pending"
 * rather than passed through to Supabase.
 */
export async function readPendingVerification(): Promise<string | null> {
  const cookieStore = await cookies();
  const raw = cookieStore.get(PENDING_VERIFICATION_COOKIE)?.value;

  if (!raw) {
    return null;
  }

  const result = validateEmail(raw);

  return result.ok ? result.value : null;
}

/**
 * Forget the pending address.
 *
 * Called after a successful verification so a later visit to `/verify` cannot be
 * pointed at an already-confirmed account.
 */
export async function forgetPendingVerification(): Promise<void> {
  const cookieStore = await cookies();

  cookieStore.delete(PENDING_VERIFICATION_COOKIE);
}