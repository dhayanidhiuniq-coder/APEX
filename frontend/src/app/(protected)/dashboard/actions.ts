"use server";

/**
 * Server Actions for Projects mutations.
 *
 * Every action re-checks the session before doing work. The browser is never
 * trusted to supply an owner: the backend derives ownership from the verified
 * access token attached by {@link createProject}/{@link deleteProject}.
 */

import { revalidatePath } from "next/cache";

import { requireVerifiedUser } from "@/lib/auth";
import {
  PROJECT_DESCRIPTION_MAX_LENGTH,
  PROJECT_TITLE_MAX_LENGTH,
  type ProjectActionState,
} from "@/lib/project-state";
import { createProject, deleteProject } from "@/lib/projects";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function errorState(message: string): ProjectActionState {
  return { status: "error", error: message };
}

export async function createProjectAction(
  _previousState: ProjectActionState,
  formData: FormData,
): Promise<ProjectActionState> {
  await requireVerifiedUser("/dashboard");

  const rawTitle = formData.get("title");
  const rawDescription = formData.get("description");
  const title = typeof rawTitle === "string" ? rawTitle.trim() : "";
  const description =
    typeof rawDescription === "string" ? rawDescription.trim() : "";

  if (!title) {
    return errorState("Enter a project title.");
  }
  if (title.length > PROJECT_TITLE_MAX_LENGTH) {
    return errorState(
      `Keep the title to ${PROJECT_TITLE_MAX_LENGTH} characters or fewer.`,
    );
  }
  if (description.length > PROJECT_DESCRIPTION_MAX_LENGTH) {
    return errorState(
      `Keep the description to ${PROJECT_DESCRIPTION_MAX_LENGTH} characters or fewer.`,
    );
  }

  const result = await createProject({
    title,
    description: description || null,
  });

  if (!result.ok) {
    return errorState(result.error);
  }

  revalidatePath("/dashboard");
  return { status: "success", error: null };
}

export async function deleteProjectAction(
  projectId: string,
): Promise<ProjectActionState> {
  await requireVerifiedUser("/dashboard");

  if (!UUID_PATTERN.test(projectId)) {
    return errorState("That project could not be found.");
  }

  const result = await deleteProject(projectId);

  if (!result.ok) {
    return errorState(result.error);
  }

  revalidatePath("/dashboard");
  return { status: "success", error: null };
}
