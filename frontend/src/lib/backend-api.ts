import "server-only";

/**
 * Server-side bridge to the APEX FastAPI service.
 *
 * The Supabase access token is read from the request cookies and attached to
 * the outgoing request on the server. It is never returned to the browser or
 * logged. Callers receive a small result union so pages and Server Actions can
 * render friendly errors without exposing backend implementation details.
 */

import { getApiBaseUrl, isSupabaseConfigured } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export type BackendResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string; status?: number };

const SESSION_EXPIRED =
  "Your session has expired. Sign in again to continue.";
const UNAVAILABLE =
  "Projects are temporarily unavailable. Try again shortly.";
const UNREACHABLE =
  "The APEX backend could not be reached. Try again shortly.";
const INVALID_REQUEST = "Please check the form and try again.";

function friendlyError(status: number): string {
  if (status === 401 || status === 403) {
    return SESSION_EXPIRED;
  }
  if (status === 404) {
    return "That project could not be found.";
  }
  if (status === 422) {
    return INVALID_REQUEST;
  }
  if (status >= 500) {
    return UNAVAILABLE;
  }
  return "The request could not be completed. Try again.";
}

export async function backendRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<BackendResult<T>> {
  if (!isSupabaseConfigured()) {
    return {
      ok: false,
      error: "Supabase is not configured, so projects cannot be loaded.",
    };
  }

  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.access_token) {
    return { ok: false, error: SESSION_EXPIRED };
  }

  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${session.access_token}`);
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      headers,
      cache: "no-store",
    });
  } catch {
    return { ok: false, error: UNREACHABLE };
  }

  if (response.status === 204) {
    return { ok: true, data: undefined as T };
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    return {
      ok: false,
      error: response.ok ? "The backend returned an invalid response." : friendlyError(response.status),
      status: response.status,
    };
  }

  if (!response.ok) {
    return {
      ok: false,
      error: friendlyError(response.status),
      status: response.status,
    };
  }

  return { ok: true, data: payload as T };
}
