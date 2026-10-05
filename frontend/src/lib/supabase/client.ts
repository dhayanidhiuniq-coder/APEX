"use client";

/**
 * Browser Supabase client.
 *
 * The session is persisted in cookies (via `@supabase/ssr`) rather than
 * `localStorage`, which keeps the access token out of reach of ordinary
 * client-side JavaScript and lets the Next.js server read the same session.
 *
 * Only ever import this from a Client Component.
 */

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

import { getSupabasePublicConfig, isSupabaseConfigured } from "./config";

let cachedClient: SupabaseClient | null = null;

/**
 * Return the shared browser Supabase client.
 *
 * @throws when Supabase environment variables are missing. Guard with
 * {@link isSupabaseConfigured} if the page must render without configuration.
 */
export function createClient(): SupabaseClient {
  if (cachedClient) {
    return cachedClient;
  }

  const { supabaseUrl, supabaseAnonKey } = getSupabasePublicConfig();
  cachedClient = createBrowserClient(supabaseUrl, supabaseAnonKey);

  return cachedClient;
}
