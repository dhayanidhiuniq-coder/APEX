import "server-only";

import { backendRequest, type BackendResult } from "@/lib/backend-api";

export type Project = {
  id: string;
  title: string;
  description: string | null;
  created_at: string;
};

export type ProjectsLoadResult = {
  projects: Project[];
  error: string | null;
};

function isProject(value: unknown): value is Project {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const project = value as Record<string, unknown>;
  return (
    typeof project.id === "string" &&
    typeof project.title === "string" &&
    (project.description === null || typeof project.description === "string") &&
    typeof project.created_at === "string"
  );
}

export async function loadProjects(): Promise<ProjectsLoadResult> {
  const result = await backendRequest<unknown>("/api/v1/projects");

  if (!result.ok) {
    return { projects: [], error: result.error };
  }

  if (
    !Array.isArray(result.data) ||
    !result.data.every(isProject)
  ) {
    return {
      projects: [],
      error: "The backend returned an unexpected projects response.",
    };
  }

  return { projects: result.data, error: null };
}

export async function createProject(input: {
  title: string;
  description: string | null;
}): Promise<BackendResult<unknown>> {
  return backendRequest<unknown>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteProject(
  projectId: string,
): Promise<BackendResult<undefined>> {
  return backendRequest<undefined>(
    `/api/v1/projects/${encodeURIComponent(projectId)}`,
    { method: "DELETE" },
  );
}
