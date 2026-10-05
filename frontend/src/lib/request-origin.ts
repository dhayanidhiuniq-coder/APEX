import "server-only";

/**
 * Derive this application's own origin from the incoming request.
 *
 * Needed for Supabase's `emailRedirectTo`, which must be an absolute URL. This
 * is only used to build that link — Supabase independently enforces its own
 * redirect-URL allowlist, so a spoofed `Host` header cannot widen it.
 */

import { headers } from "next/headers";

/**
 * Best-effort absolute origin for the current request.
 *
 * Returns `null` when no usable `Host` is present, in which case callers should
 * omit `emailRedirectTo` rather than send a malformed value.
 */
export async function resolveRequestOrigin(): Promise<string | null> {
  const headerList = await headers();
  const host = headerList.get("x-forwarded-host") ?? headerList.get("host");

  if (!host) {
    return null;
  }

  // A reverse proxy that terminates TLS sets this; otherwise the app is served
  // over the same connection, so assume HTTP.
  const forwardedProto = headerList.get("x-forwarded-proto");
  const protocol = forwardedProto?.split(",")[0]?.trim() || "http";

  return `${protocol}://${host}`;
}