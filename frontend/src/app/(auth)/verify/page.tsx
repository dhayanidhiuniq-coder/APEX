import Link from "next/link";
import { redirect } from "next/navigation";

import { OtpForm } from "@/components/otp-form";
import { SignOutButton } from "@/components/sign-out-button";
import { getUser } from "@/lib/auth";
import { readPendingVerification } from "@/lib/otp-session";
import { safeNextPath } from "@/lib/safe-redirect";
import { OTP_LENGTH } from "@/lib/validation";

type VerifyPageProps = {
  searchParams: Promise<{ next?: string | string[] }>;
};

/**
 * Email confirmation.
 *
 * Reached after Create Account. The address being confirmed comes from an
 * httpOnly cookie set by the Server Action, not from the query string, so it
 * does not leak into browser history or request logs.
 *
 * Three states are handled deliberately, because the obvious implementation of
 * the third one loops forever:
 *
 * 1. A confirmed session -> straight to the app.
 * 2. No session and no pending registration -> back to Create Account.
 * 3. A session but no pending registration. The visitor is already known to
 *    `proxy.ts`, which sends unconfirmed sessions here from every auth page. If
 *    this page also redirected to `/create-account` the two rules would bounce
 *    the request between those routes indefinitely. So it offers a way out
 *    instead of redirecting.
 */
export default async function VerifyPage({ searchParams }: VerifyPageProps) {
  const params = await searchParams;
  const next = safeNextPath(params.next);

  // Reading the cookie also marks this route dynamic, which it must be.
  const pendingEmail = await readPendingVerification();
  const user = await getUser();

  if (user?.emailVerified) {
    redirect(next);
  }

  if (pendingEmail === null) {
    if (!user) {
      // Nothing pending and nobody signed in: there is no verification to do.
      redirect("/create-account");
    }

    return <VerificationRecovery />;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Confirm your email</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          We sent a {OTP_LENGTH}-digit code to{" "}
          <span className="font-medium text-neutral-900 dark:text-neutral-100">
            {pendingEmail}
          </span>
          . Enter it below to finish creating your account. APEX stays locked until
          your address is confirmed.
        </p>
      </div>

      <OtpForm next={next} />

      <p className="text-sm text-neutral-600 dark:text-neutral-300">
        Wrong address?{" "}
        <Link href="/create-account" className="font-medium underline underline-offset-4">
          Create the account again
        </Link>{" "}
        or{" "}
        <Link href="/signin" className="font-medium underline underline-offset-4">
          sign in
        </Link>
        .
      </p>
    </div>
  );
}

/**
 * Shown when APEX has a session but no pending registration to verify.
 *
 * Reachable if the confirmation cookie expired (it lasts 30 minutes) or was
 * cleared, while a session is still open. Signing out is the only honest way out:
 * the code cannot be resent without knowing which address to send it to.
 */
function VerificationRecovery() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Confirm your email</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          There is no registration waiting to be confirmed. It may have been
          completed already, or the request may have been more than 30 minutes ago.
        </p>
      </div>

      <div className="flex items-center gap-4">
        <SignOutButton />
        <Link
          href="/create-account"
          className="text-sm font-medium underline underline-offset-4"
        >
          Create an account
        </Link>
      </div>
    </div>
  );
}