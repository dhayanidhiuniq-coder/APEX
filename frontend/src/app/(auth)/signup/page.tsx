import { redirect } from "next/navigation";

/**
 * The old sign-up address.
 *
 * Registration now collects profile details and requires email confirmation, so
 * it lives at `/create-account`. This redirect keeps existing links and bookmarks
 * working rather than leaving a dead route behind.
 */
export default function SignupPage() {
  redirect("/create-account");
}