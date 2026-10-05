/**
 * Session refresh for `proxy.ts`.
 *
 * Supabase access tokens are short lived. Every navigation needs to either
 * present a still-valid token or mint a fresh one before any protected page
 * renders. This helper runs ahead of rendering to do exactly that.
 *
 * This module must stay free of shared state: `proxy.ts` runs separately from
 * the render pass.
 */

import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { isEmailConfirmed } from "@/lib/email-confirmation";

import { isSupabaseConfigured, getSupabasePublicConfig } from "./config";

/** Minimal caller state, enough to route on without a second lookup. */
export type ProxyUser = {
  id: string;
  emailVerified: boolean;
};

/**
 * Refresh the Supabase session cookies on an incoming request.
 *
 * Returns a response whose cookies have been updated with the (possibly
 * refreshed) session. Callers that want to redirect should do so on the
 * returned response so the new cookies are preserved.
 *
 * The returned user comes from `getUser()`, which revalidates against Supabase
 * Auth, so `emailVerified` is the server's answer and not a cookie value the
 * browser could have edited.
 */
export async function refreshSession(
  request: NextRequest,
): Promise<{ response: NextResponse; user: ProxyUser | null }> {
  // Without configuration there is no session to refresh. Pass the request
  // through untouched rather than crashing the whole app.
  if (!isSupabaseConfigured()) {
    return { response: NextResponse.next({ request }), user: null };
  }

  let response = NextResponse.next({ request });

  const { supabaseUrl, supabaseAnonKey } = getSupabasePublicConfig();

  const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }

        // Recreate the response so the mutated request cookies are carried
        // forward, then apply the new session cookies onto it.
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // `getUser()` revalidates the token against Supabase Auth. It must not be
  // swapped for `getSession()`, which trusts unverified cookie contents.
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return { response, user: null };
  }

  return {
    response,
    user: {
      id: user.id,
      emailVerified: isEmailConfirmed(user.email_confirmed_at, user.confirmed_at),
    },
  };
}
