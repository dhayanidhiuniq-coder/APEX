"use client";

import { useState, useTransition } from "react";

import { deleteProjectAction } from "./actions";

type DeleteProjectButtonProps = {
  projectId: string;
  projectTitle: string;
};

export function DeleteProjectButton({
  projectId,
  projectTitle,
}: DeleteProjectButtonProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  function handleDelete() {
    const confirmed = window.confirm(
      `Delete “${projectTitle}”? This cannot be undone.`,
    );
    if (!confirmed) {
      return;
    }

    setError(null);
    startTransition(async () => {
      const result = await deleteProjectAction(projectId);
      if (result.status === "error") {
        setError(result.error);
      }
    });
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={handleDelete}
        disabled={isPending}
        aria-label={`Delete ${projectTitle}`}
        className="rounded-md px-2 py-1 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50 dark:text-red-400 dark:hover:bg-red-950/40"
      >
        {isPending ? "Deleting…" : "Delete"}
      </button>
      {error ? (
        <p role="alert" className="max-w-48 text-right text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      ) : null}
    </div>
  );
}
