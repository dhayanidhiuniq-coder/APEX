import Link from "next/link";

import { AuthForm } from "@/components/auth-form";

type SignUpPageProps = {
  searchParams: Promise<{ next?: string | string[] }>;
};

export default async function SignUpPage({ searchParams }: SignUpPageProps) {
  await searchParams;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-300">
          APEX accounts are private to you. Passwords are handled by Supabase Auth and are never
          stored by APEX itself.
        </p>
      </div>

      <AuthForm mode="signup" redirectTo="/dashboard" />

      <p className="text-sm text-neutral-600 dark:text-neutral-300">
        Already have an account?{" "}
        <Link href="/signin" className="font-medium underline underline-offset-4">
          Sign in
        </Link>
      </p>
    </div>
  );
}
