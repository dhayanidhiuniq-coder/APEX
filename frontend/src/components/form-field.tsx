"use client";

/**
 * Labelled input with inline validation feedback.
 *
 * Extracted so the Create Account form renders all five fields identically and
 * an error is always wired to its input through `aria-describedby` and
 * `aria-invalid`. The class names match the existing `AuthForm` inputs exactly,
 * so the two forms read as one design.
 *
 * `name` is the field's identity, not `id`: it is the key the Server Action
 * reads out of `FormData`. The DOM `id` defaults to it so the label and the input
 * stay connected without the two being able to drift apart.
 */

import type { InputHTMLAttributes } from "react";

type FormFieldProps = {
  /** FormData key read by the Server Action. Also the default DOM id. */
  name: string;
  label: string;
  /** Override the DOM id when it must differ from the field name. */
  id?: string;
  /** Validation message for this field, if any. */
  error?: string;
  hint?: string;
} & Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "name" | "className">;

export function FormField({
  name,
  label,
  id = name,
  error,
  hint,
  ...inputProps
}: FormFieldProps) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;

  // An error takes precedence over a hint: only one element should be announced.
  const describedBy = error ? errorId : hint ? hintId : undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium" htmlFor={id}>
        {label}
      </label>

      <input
        {...inputProps}
        id={id}
        name={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className="rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 disabled:opacity-60 aria-invalid:border-red-500 aria-invalid:focus-visible:ring-red-500 dark:border-neutral-700 dark:focus-visible:ring-neutral-400 dark:aria-invalid:border-red-500 dark:aria-invalid:focus-visible:ring-red-500"
      />

      {error ? (
        <p id={errorId} className="text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-neutral-500 dark:text-neutral-400">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
