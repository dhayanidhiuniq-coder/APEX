import { fetchBackendIdentity, requireVerifiedUser } from "@/lib/auth";
import { loadProjects } from "@/lib/projects";

import { DeleteProjectButton } from "./delete-project-button";
import { NewProjectDialog } from "./new-project-dialog";

const createdAtFormatter = new Intl.DateTimeFormat("en", {
  dateStyle: "medium",
});

function formatCreatedAt(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "recently"
    : createdAtFormatter.format(date);
}

/**
 * Protected application area.
 *
 * The projects list is read through the server-side backend bridge, which
 * attaches the current Supabase access token. Mutations run through Server
 * Actions, which re-check the session before calling the backend.
 */
export default async function DashboardPage() {
  const user = await requireVerifiedUser("/dashboard");
  const [backendIdentity, projectsResult] = await Promise.all([
    fetchBackendIdentity(),
    loadProjects(),
  ]);

  return (
    <div className="flex flex-col gap-10">
      <section className="flex flex-col gap-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
            <p className="max-w-2xl text-sm text-neutral-600 dark:text-neutral-300">
              Create a project to group the work you want to track. Every project
              belongs to the signed-in account and is only visible to that account.
            </p>
          </div>
          <NewProjectDialog />
        </div>

        {projectsResult.error ? (
          <div
            role="alert"
            className="flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200"
          >
            <h2 className="text-sm font-semibold">Projects could not be loaded</h2>
            <p className="text-sm">{projectsResult.error}</p>
            <p className="text-xs opacity-80">
              The rest of the dashboard is still available. Check the backend
              database configuration and try again.
            </p>
          </div>
        ) : projectsResult.projects.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-neutral-300 px-6 py-12 text-center dark:border-neutral-700">
            <h2 className="text-base font-semibold">No projects yet</h2>
            <p className="max-w-md text-sm text-neutral-600 dark:text-neutral-300">
              Use <span className="font-medium">New project</span> to create the
              first one. It will appear here once it has been saved.
            </p>
          </div>
        ) : (
          <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projectsResult.projects.map((project) => (
              <li
                key={project.id}
                className="flex min-h-40 flex-col gap-3 rounded-xl border border-neutral-200 p-5 dark:border-neutral-800"
              >
                <div className="flex items-start justify-between gap-3">
                  <h2 className="text-base font-semibold break-words">
                    {project.title}
                  </h2>
                  <DeleteProjectButton
                    projectId={project.id}
                    projectTitle={project.title}
                  />
                </div>

                {project.description ? (
                  <p className="text-sm whitespace-pre-wrap break-words text-neutral-600 dark:text-neutral-300">
                    {project.description}
                  </p>
                ) : (
                  <p className="text-sm text-neutral-500 italic dark:text-neutral-400">
                    No description
                  </p>
                )}

                <p className="mt-auto text-xs text-neutral-500 dark:text-neutral-400">
                  Created {formatCreatedAt(project.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold tracking-tight">Account</h2>
          <p className="text-sm text-neutral-600 dark:text-neutral-300">
            Signed in as {user.email ?? "an account without an email address"}.
          </p>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
            <h3 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              Identity from Supabase session
            </h3>
            <p className="font-mono text-sm break-all">id: {user.id}</p>
            <p className="text-sm break-all">email: {user.email ?? "—"}</p>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              email confirmed: {user.emailVerified ? "yes" : "no"}
            </p>
          </article>

          <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
            <h3 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              Profile
            </h3>
            {user.profile ? (
              <>
                <p className="text-sm break-all">name: {user.profile.name}</p>
                <p className="text-sm">age: {user.profile.age}</p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  Supplied on the Create Account form. Held by Supabase Auth, not by APEX.
                </p>
              </>
            ) : (
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                No name and age on this account. Accounts created before the Create
                Account flow have no profile data.
              </p>
            )}
          </article>

          <article className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-5 dark:border-neutral-800">
            <h3 className="text-sm font-medium text-neutral-500 dark:text-neutral-400">
              Identity verified by backend
            </h3>

            {backendIdentity ? (
              <>
                <p className="font-mono text-sm break-all">id: {backendIdentity.id}</p>
                <p className="text-sm break-all">
                  email: {backendIdentity.email ?? "—"}
                </p>
                <p className="text-xs text-neutral-500 dark:text-neutral-400">
                  GET /api/v1/me accepted the access token.
                </p>
              </>
            ) : (
              <p className="text-sm text-neutral-600 dark:text-neutral-300">
                The backend did not return an identity. It may not be running on{" "}
                <code className="font-mono">localhost:8000</code>, or{" "}
                <code className="font-mono">SUPABASE_URL</code> /{" "}
                <code className="font-mono">SUPABASE_ANON_KEY</code> may be unset on the backend.
              </p>
            )}
          </article>
        </div>
      </section>

      <p className="text-xs text-neutral-500 dark:text-neutral-400">
        Tasks will appear here in a later release.
      </p>
    </div>
  );
}
