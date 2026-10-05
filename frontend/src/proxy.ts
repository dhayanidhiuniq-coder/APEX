import { NextResponse, type NextRequest } from "next/server";

import { refreshSession } from "@/lib/supabase/proxy";

/**
 * Refresh the Supabase session ahead of rendering and bounce signed-out users
 * away from protected routes.
 *
 * This is a fast first line of defence only. The authoritative check is the
 * data access layer in `@/lib/auth`, which every protected page calls during
 * render. Proxy logic can be bypassed by hitting a route handler directly, so
 * it must never be the sole gate on protected data.
 */

/** Routes that require a signed-in user. */
const PROTECTED_PREFIXES = ["/dashboard"];

/** Auth pages that a signed-in user has no reason to see. */
const AUTH_ROUTES = ["/signin", "/signup"];

export async function proxy(request: NextRequest) {
  const { response, userId } = await refreshSession(request);
  const { pathname } = request.nextUrl;

  const needsAuth = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );

  if (needsAuth && !userId) {
    const signInUrl = request.nextUrl.clone();
    signInUrl.pathname = "/signin";
    signInUrl.search = "";

    // Preserve the destination so sign-in can return the user to it.
    signInUrl.searchParams.set("next", pathname);

    return NextResponse.redirect(signInUrl);
  }

  const isAuthRoute = AUTH_ROUTES.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`),
  );

  if (isAuthRoute && userId) {
    const dashboardUrl = request.nextUrl.clone();
    dashboardUrl.pathname = "/dashboard";
    dashboardUrl.search = "";
    return NextResponse.redirect(dashboardUrl);
  }

  return response;
}

export const config = {
  // Skip static assets and the API surface; only guard navigable routes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
