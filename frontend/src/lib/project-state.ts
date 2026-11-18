/**
 * Shared form state and limits for the Projects UI.
 *
 * These limits mirror the backend validation and the database check
 * constraints so an invalid request is stopped before it reaches the API.
 */

export type ProjectActionState = {
  status: "idle" | "success" | "error";
  error: string | null;
};

export const INITIAL_PROJECT_ACTION_STATE: ProjectActionState = {
  status: "idle",
  error: null,
};

export const PROJECT_TITLE_MAX_LENGTH = 120;
export const PROJECT_DESCRIPTION_MAX_LENGTH = 2000;
