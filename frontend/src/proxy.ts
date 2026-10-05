import { NextResponse, type NextRequest } from "next/server";

import { refreshSession } from "@/lib/supabase/proxy";

/**
 * Refresh the Supabase session ahead of rendering and route callers to where
 * they belong: signed-out visitors to `/signin`, signed-in users whose email is
 * unconfirmed to `/verify`, and confirmed users out of the auth pages.
 *
 * This is a fast first line of defence only. The authoritative check is the data
 * access layer in `@/lib/auth`, where `requireVerifiedUser()` runs during render
 * inside the protected layout. Proxy logic can be bypassed by hitting a route
 * handler directly, so it must never be the sole gate on protected data.
 */

/** Routes that require a signed-in, confirmed user. */
const PROTECTED_PREFIXES = ["/dashboard"];

/** Auth pages a fully signed-in user has no reason to see. */
const AUTH_ROUTES = ["/signin", "/signup", "/create-account"];

/** Where an unconfirmed session is sent to finish confirming. */
const VERIFY_ROUTE = "/verify";

function matches(pathname: string, routes: string[]): boolean {
  return routes.some((route) => pathname === route || pathname.startsWith(`${route}/`));
}

export async function proxy(request: NextRequest) {
  const { response, user } = await refreshSession(request);
  const { pathname } = request.nextUrl;

  const isProtected = matches(pathname, PROTECTED_PREFIXES);
  const isVerifyRoute = pathname === VERIFY_ROUTE || pathname.startsWith(`${VERIFY_ROUTE}/`);
  const isAuthRoute = matches(pathname, AUTH_ROUTES);

  // Nobody signed in: protected routes go to sign-in. `/verify` is not
  // protected here — it checks its own pending-registration cookie during
  // render and redirects onward, which keeps that decision server-side.
  if (isProtected && !user) {
    const signInUrl = request.nextUrl.clone();
    signInUrl.pathname = "/signin";
    signInUrl.search = "";

    // Preserve the destination so sign-in can return the user to it.
    signInUrl.searchParams.set("next", pathname);

    return NextResponse.redirect(signInUrl);
  }

  // Signed in but the address is unconfirmed: they have no business in the
  // protected area yet. This is the fast path; `requireVerifiedUser()` in the
  // protected layout is the one that actually holds.
  if (isProtected && user && !user.emailVerified) {
    const verifyUrl = request.nextUrl.clone();
    verifyUrl.pathname = VERIFY_ROUTE;
    verifyUrl.search = "";
    return NextResponse.redirect(verifyUrl);
  }

  // A confirmed user has nothing to do on the auth pages, including the code
  // entry screen.
  if ((isAuthRoute || isVerifyRoute) && user?.emailVerified) {
    const dashboardUrl = request.nextUrl.clone();
    dashboardUrl.pathname = "/dashboard";
    dashboardUrl.search = "";
    return NextResponse.redirect(dashboardUrl);
  }

  // An unconfirmed user has no useful session to offer on the sign-in page, and
  // signing in again will not confirm anything. Send them to the code screen.
  if (isAuthRoute && user && !user.emailVerified) {
    const verifyUrl = request.nextUrl.clone();
    verifyUrl.pathname = VERIFY_ROUTE;
    verifyUrl.search = "";
    return NextResponse.redirect(verifyUrl);
  }

  return response;
}

export const config = {
  // Skip static assets and the API surface; only guard navigable routes.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)"],
};
