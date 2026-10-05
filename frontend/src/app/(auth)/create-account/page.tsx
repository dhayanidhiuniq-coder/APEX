import Link from "next/link";

import { CreateAccountForm } from "@/components/create-account-form";
import { safeNextPath } from "@/lib/safe-redirect";

type CreateAccountPageProps = {
  searchParams: Promise<{ next?: string | string[] }>;
};

/**
 * Registration.
 *
 * Collects profile details, hands the credentials to Supabase Auth, and then
 * redirects to `/verify` for email confirmation. Name and age are profile data
 * and travel as user metadata; the password goes to Supabase and is never
 * stored by APEX.
 */
export default async function CreateAccountPage({ searchParams }: CreateAccountPageProps) {
  const params = await searchParams;
  const next = safeNextPath(params.next);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Create account</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          We will email you a code to confirm your address before you can use APEX.
        </p>
      </div>

      <CreateAccountForm next={next} />

      <p className="text-sm text-neutral-600 dark:text-neutral-300">
        Already have an account?{" "}
        <Link
          href="/signin"
          className="font-medium underline underline-offset-4"
        >
          Sign in
        </Link>
      </p>
    </div>
  );
}