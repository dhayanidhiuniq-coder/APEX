"use client";

import { useActionState, useCallback, useEffect, useRef, useState } from "react";

import { FormField } from "@/components/form-field";
import {
  INITIAL_PROJECT_ACTION_STATE,
  PROJECT_DESCRIPTION_MAX_LENGTH,
  PROJECT_TITLE_MAX_LENGTH,
} from "@/lib/project-state";

import { createProjectAction } from "./actions";

type ProjectFormProps = {
  onSuccess: () => void;
};

function ProjectForm({ onSuccess }: ProjectFormProps) {
  const [state, formAction, pending] = useActionState(
    createProjectAction,
    INITIAL_PROJECT_ACTION_STATE,
  );
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (state.status === "success") {
      onSuccess();
    }
  }, [onSuccess, state]);

  return (
    <form action={formAction} className="flex flex-col gap-5 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="new-project-title" className="text-lg font-semibold">
            New project
          </h2>
          <p className="text-sm text-neutral-600 dark:text-neutral-300">
            Projects are private to your account.
          </p>
        </div>
        <button
          type="button"
          onClick={onSuccess}
          disabled={pending}
          aria-label="Close new project dialog"
          className="rounded-md px-2 py-1 text-xl leading-none text-neutral-500 transition-colors hover:bg-neutral-100 hover:text-neutral-900 disabled:opacity-50 dark:text-neutral-400 dark:hover:bg-neutral-800 dark:hover:text-neutral-100"
        >
          ×
        </button>
      </div>

      <FormField
        name="title"
        label="Title"
        placeholder="Ship the first milestone"
        required
        autoFocus
        maxLength={PROJECT_TITLE_MAX_LENGTH}
        value={title}
        onChange={(event) => setTitle(event.target.value)}
      />

      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium" htmlFor="project-description">
          Description <span className="font-normal text-neutral-500">(optional)</span>
        </label>
        <textarea
          id="project-description"
          name="description"
          rows={4}
          maxLength={PROJECT_DESCRIPTION_MAX_LENGTH}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="What is this project for?"
          className="resize-y rounded-md border border-neutral-300 bg-transparent px-3 py-2 text-sm outline-none transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-500 dark:border-neutral-700 dark:focus-visible:ring-neutral-400"
        />
      </div>

      {state.status === "error" ? (
        <p
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-300"
        >
          {state.error}
        </p>
      ) : null}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onSuccess}
          disabled={pending}
          className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-medium transition-colors hover:bg-neutral-100 disabled:opacity-50 dark:border-neutral-700 dark:hover:bg-neutral-800"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
        >
          {pending ? "Creating…" : "Create project"}
        </button>
      </div>
    </form>
  );
}

export function NewProjectDialog() {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [formKey, setFormKey] = useState(0);

  const closeDialog = useCallback(() => {
    dialogRef.current?.close();
    setIsOpen(false);
  }, []);

  function openDialog() {
    const dialog = dialogRef.current;
    if (!dialog || dialog.open) {
      return;
    }

    setFormKey((key) => key + 1);
    setIsOpen(true);
    dialog.showModal();
  }

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="inline-flex items-center justify-center rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-neutral-700 dark:bg-neutral-100 dark:text-neutral-900 dark:hover:bg-neutral-300"
      >
        New project
      </button>

      <dialog
        ref={dialogRef}
        aria-labelledby="new-project-title"
        onClose={() => setIsOpen(false)}
        className="m-auto max-h-[90vh] w-[min(92vw,34rem)] overflow-y-auto rounded-xl border border-neutral-200 bg-white p-0 text-neutral-900 shadow-xl [&::backdrop]:bg-black/40 dark:border-neutral-800 dark:bg-neutral-950 dark:text-neutral-100"
      >
        {isOpen ? <ProjectForm key={formKey} onSuccess={closeDialog} /> : null}
      </dialog>
    </>
  );
}
