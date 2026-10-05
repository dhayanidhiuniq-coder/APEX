import Link from "next/link";

import { AuthForm } from "@/components/auth-form";
import { safeNextPath } from "@/lib/safe-redirect";

type SignInPageProps = {
  searchParams: Promise<{ next?: string | string[] }>;
};

export default async function SignInPage({ searchParams }: SignInPageProps) {
  const params = await searchParams;
  const redirectTo = safeNextPath(params.next);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          Use the email and password for your APEX account.
        </p>
      </div>

      <AuthForm redirectTo={redirectTo} />

      <p className="text-sm text-neutral-600 dark:text-neutral-300">
        No account yet?{" "}
        <Link href="/create-account" className="font-medium underline underline-offset-4">
          Create one
        </Link>
      </p>
    </div>
  );
}
