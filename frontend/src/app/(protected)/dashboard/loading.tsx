/**
 * Streamed placeholder while the dashboard loads projects from the backend.
 *
 * Kept intentionally close to the real layout so the page does not jump when
 * the server response arrives.
 */
export default function DashboardLoading() {
  return (
    <div className="flex animate-pulse flex-col gap-10" aria-busy="true">
      <section className="flex flex-col gap-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="flex flex-col gap-2">
            <div className="h-8 w-36 rounded bg-neutral-200 dark:bg-neutral-800" />
            <div className="h-4 w-80 max-w-full rounded bg-neutral-200 dark:bg-neutral-800" />
          </div>
          <div className="h-9 w-28 rounded-md bg-neutral-200 dark:bg-neutral-800" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              className="flex min-h-40 flex-col gap-3 rounded-xl border border-neutral-200 p-5 dark:border-neutral-800"
            >
              <div className="h-5 w-2/3 rounded bg-neutral-200 dark:bg-neutral-800" />
              <div className="h-4 w-full rounded bg-neutral-200 dark:bg-neutral-800" />
              <div className="h-4 w-4/5 rounded bg-neutral-200 dark:bg-neutral-800" />
              <div className="mt-auto h-3 w-24 rounded bg-neutral-200 dark:bg-neutral-800" />
            </div>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <div className="h-6 w-24 rounded bg-neutral-200 dark:bg-neutral-800" />
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              className="h-32 rounded-lg border border-neutral-200 bg-neutral-100 dark:border-neutral-800 dark:bg-neutral-900"
            />
          ))}
        </div>
      </section>
    </div>
  );
}
