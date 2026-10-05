/**
 * Public Supabase configuration.
 *
 * Only `NEXT_PUBLIC_*` values live here, so everything in this module is
 * safe to ship to the browser. These values are public by design: the anon key
 * is not a secret, it is protected by Row Level Security on the Supabase side.
 *
 * The service-role key is deliberately NOT read here. It must never reach the
 * browser bundle.
 */

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export type SupabasePublicConfig = {
  supabaseUrl: string;
  supabaseAnonKey: string;
};

/**
 * Whether the public Supabase values are present.
 *
 * The app must still build and render without them, so every caller checks
 * this instead of assuming a configured project.
 */
export function isSupabaseConfigured(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
}

/**
 * Read the public Supabase configuration.
 *
 * @throws when the environment variables are missing. Callers that must keep
 * working without configuration should use {@link isSupabaseConfigured}.
 */
export function getSupabasePublicConfig(): SupabasePublicConfig {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY in frontend/.env.local (see .env.example).",
    );
  }

  return { supabaseUrl: SUPABASE_URL, supabaseAnonKey: SUPABASE_ANON_KEY };
}

/**
 * Base URL of the APEX backend, used for server-side fetches.
 *
 * Falls back to the local development backend so the app is usable out of the
 * box without extra configuration.
 */
export function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}
