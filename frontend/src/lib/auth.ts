import "server-only";

/**
 * Authentication data access layer.
 *
 * This is the authoritative gate for protected pages. Every protected page
 * calls {@link requireUser} during render, so an unauthenticated request never
 * reaches the page body regardless of what happened in `proxy.ts`.
 *
 * Rules enforced here:
 * - The identity always comes from Supabase Auth, never from client input.
 * - `getUser()` is used rather than `getSession()` because it revalidates the
 *   token with the auth server instead of trusting the cookie contents.
 * - Tokens are never returned to, or logged on, the client.
 */

import { cache } from "react";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { getApiBaseUrl, isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export type CurrentUser = {
  id: string;
  email: string | null;
};

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

  return { id: user.id, email: user.email ?? null };
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
 * Fetch the verified identity for the current user from the APEX backend.
 *
 * The access token stays on the server: the browser never handles it, and the
 * backend independently verifies it before answering.
 *
 * Returns `null` when there is no session, the backend is unreachable, or the
 * backend rejects the token. Callers must treat that as "unverified", never as
 * an authenticated identity.
 */
export async function fetchBackendIdentity(): Promise<CurrentUser | null> {
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

    const payload = (await response.json()) as CurrentUser;

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
