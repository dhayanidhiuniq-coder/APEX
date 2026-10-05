import "server-only";

/**
 * Server-side Supabase client bound to the request's cookies.
 *
 * Use this from Server Components, Server Actions and Route Handlers to read
 * the caller's session without ever handling the access token in client-side
 * JavaScript.
 */

import { createServerClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";

import { getSupabasePublicConfig } from "./config";

/**
 * Create a Supabase client for the current request.
 *
 * Supabase may refresh the access token while the request is being handled.
 * The `setAll` callback below is the documented hook for writing those
 * refreshed cookies back onto the outgoing response.
 *
 * @throws when Supabase environment variables are missing.
 */
export async function createClient(): Promise<SupabaseClient> {
  const cookieStore = await cookies();
  const { supabaseUrl, supabaseAnonKey } = getSupabasePublicConfig();

  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Components cannot mutate cookies. `proxy.ts` refreshes the
          // session before rendering, so this is safe to ignore here.
        }
      },
    },
  });
}
