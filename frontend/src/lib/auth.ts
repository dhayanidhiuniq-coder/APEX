import "server-only";

/**
 * Authentication data access layer.
 *
 * This is the authoritative gate for protected pages. Every protected page
 * calls {@link requireVerifiedUser} during render, so an unauthenticated or
 * unconfirmed request never reaches the page body regardless of what happened in
 * `proxy.ts`.
 *
 * Rules enforced here:
 * - The identity always comes from Supabase Auth, never from client input.
 * - `getUser()` is used rather than `getSession()` because it revalidates the
 *   token with the auth server instead of trusting the cookie contents.
 * - Tokens are never returned to, or logged on, the client.
 * - A signed-in user whose email is unconfirmed is not a valid caller: they are
 *   sent back to email confirmation rather than admitted to the app.
 */

import { cache } from "react";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { getApiBaseUrl, isSupabaseConfigured } from "@/lib/supabase/config";
import { isEmailConfirmed } from "@/lib/email-confirmation";
import { createClient } from "@/lib/supabase/server";

export type CurrentUser = {
  id: string;
  email: string | null;
  /**
   * Whether Supabase has confirmed this user's email address.
   *
   * Comes from the revalidated user record, never from client input, so it
   * cannot be asserted by the browser.
   */
  emailVerified: boolean;
  /**
   * Application profile data, as supplied on the Create Account form.
   *
   * `null` when absent or not the expected shape — the user record's metadata is
   * client-supplied at sign-up, so it is treated as untrusted and checked rather
   * than cast.
   */
  profile: UserProfile | null;
};

export type UserProfile = {
  name: string;
  age: number;
};

/**
 * Read name and age out of Supabase user metadata.
 *
 * Defensive on purpose. `raw_user_meta_data` is whatever the browser sent during
 * sign-up, so it can hold any JSON at all. Anything that is not a non-empty
 * string name plus a whole number in the expected range is discarded, and the
 * caller renders a placeholder instead.
 */
function readProfile(metadata: Record<string, unknown> | undefined): UserProfile | null {
  if (!metadata) {
    return null;
  }

  const { name, age } = metadata;

  if (typeof name !== "string" || name.trim() === "") {
    return null;
  }

  if (typeof age !== "number" || !Number.isInteger(age)) {
    return null;
  }

  return { name: name.trim(), age };
}

/**
 * `@supabase/ssr` names its session cookies `sb-<project-ref>-auth-token`.
 */
const SUPABASE_COOKIE_PREFIX = "sb-";
const SUPABASE_COOKIE_MARKER = "auth-token";

/**
 * Cheap check for whether a session cookie exists at all.
 *
 * Two purposes:
 *
 * 1. Correctness. Reading `cookies()` marks this route as *dynamic*. Next.js 16
 *    removed `export const dynamic`, so the only way to guarantee an auth-gated
 *    page is never prerendered at build time is to touch a dynamic API during
 *    render. Without this, a build with Supabase unset would bake the
 *    build-time redirect into a static artifact and lock signed-in users out.
 * 2. It avoids a pointless network round trip to Supabase Auth for the common
 *    case of a visitor with no session cookie.
 */
async function hasSessionCookie(): Promise<boolean> {
  const cookieStore = await cookies();

  return cookieStore
    .getAll()
    .some(
      (cookie) =>
        cookie.name.startsWith(SUPABASE_COOKIE_PREFIX) &&
        cookie.name.includes(SUPABASE_COOKIE_MARKER),
    );
}

/**
 * Return the signed-in user, or `null` when there is no valid session.
 *
 * An unconfigured environment is treated as "nobody is signed in" rather than
 * an error, so a fresh clone still renders and can show setup instructions.
 *
 * Deduplicated per request so a layout and its page do not each trigger a
 * round trip to Supabase Auth.
 */
export const getUser = cache(async (): Promise<CurrentUser | null> => {
  // Always evaluated first, before any early return, so the route stays
  // dynamic. See `hasSessionCookie`.
  const maybeHasSession = await hasSessionCookie();

  if (!maybeHasSession || !isSupabaseConfigured()) {
    return null;
  }

  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return null;
  }

  return {
    id: user.id,
    email: user.email ?? null,
    emailVerified: isEmailConfirmed(user.email_confirmed_at, user.confirmed_at),
    profile: readProfile(user.user_metadata),
  };
});

/**
 * Require a signed-in user, redirecting to the sign-in page otherwise.
 *
 * @param next - path to return to after a successful sign-in.
 */
export async function requireUser(next = "/dashboard"): Promise<CurrentUser> {
  const user = await getUser();

  if (!user) {
    redirect(`/signin?next=${encodeURIComponent(next)}`);
  }

  return user;
}

/**
 * Require a signed-in user whose email is confirmed.
 *
 * This is the gate every protected page should use. It produces one of two
 * outcomes:
 *
 * - no session at all -> `/signin`
 * - session but unconfirmed email -> `/verify`
 *
 * `next` is deliberately dropped on the unconfirmed branch. Sending an
 * unconfirmed user to a deep link inside the protected area would have them
 * bounced back through here again, and the `?next=` round trip buys nothing
 * while the address is still unconfirmed.
 */
export async function requireVerifiedUser(next = "/dashboard"): Promise<CurrentUser> {
  const user = await requireUser(next);

  if (!user.emailVerified) {
    redirect("/verify");
  }

  return user;
}

/**
 * Identity as the APEX backend sees it.
 *
 * Deliberately a separate type from {@link CurrentUser}: this describes what the
 * FastAPI service resolved from the access token, which is a different question
 * from whether Supabase has confirmed the user's email address. Conflating them
 * would imply the backend checks email confirmation, and it does not.
 */
export type BackendIdentity = {
  id: string;
  email: string | null;
};

/**
 * Fetch the verified identity for the current user from the APEX backend.
 *
 * The access token stays on the server: the browser never handles it, and the
 * backend independently verifies it before answering.
 *
 * Returns `null` when there is no session, the backend is unreachable, or the
 * backend rejects the token. Callers must treat that as "unverified", never as
 * an authenticated identity.
 */
export async function fetchBackendIdentity(): Promise<BackendIdentity | null> {
  if (!isSupabaseConfigured()) {
    return null;
  }

  const supabase = await createClient();

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    return null;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    const payload = (await response.json()) as BackendIdentity;

    // The backend echoes only verified fields; guard against a proxy or a
    // misconfigured base URL returning something unexpected.
    if (typeof payload?.id !== "string") {
      return null;
    }

    return { id: payload.id, email: payload.email ?? null };
  } catch {
    // Backend down or unreachable. The user is still signed in with Supabase.
    return null;
  }
}
