/**
 * What the index last did, said in one line beside a table that has no rows.
 *
 * Decision 61 asks an empty table to state what was checked and name one next action. That
 * sentence could not be written honestly until `index_run` existed: `call_site.indexed_at` says
 * rows exist, which cannot tell a completed pass from one that died, and "the index ran" is not a
 * claim worth making if it might be false. The table records it now, so this renders it.
 *
 * **Four states, and none of them collapses into another.** No pass at all is never-indexed, and
 * that is not the same as a pass that ran and found nothing — which is a completed pass whose
 * count happens to be nought. A pass in flight has no outcome yet. A pass that failed left rows
 * behind that are partial, and saying so is the difference between a reader trusting the table
 * and a reader knowing not to.
 *
 * No count is shown for a pass that did not complete. A partial count is not a smaller count; it
 * would be read as the size of the codebase.
 */

import { RelativeTime } from "@/components/relative-time"
import type { IndexRunSummary } from "@/api/types"

export function IndexRunNote({ run }: { run: IndexRunSummary | null }) {
  if (run === null) {
    return (
      <p role="note" className="text-meta text-muted-foreground">
        This codebase has never been indexed, so nothing here has been looked for. That is the
        absence of a measurement rather than a measurement of nought.
      </p>
    )
  }

  if (run.outcome === null) {
    return (
      <p role="note" className="text-meta text-muted-foreground">
        An index pass started <RelativeTime iso={run.started_at} /> and has not finished. Nothing
        below is a result yet, and no count is stated because a partial one would read as the size
        of this codebase.
      </p>
    )
  }

  if (run.outcome !== "completed") {
    return (
      <p role="note" className="text-meta text-muted-foreground">
        The last index pass did not finish — it {run.outcome}{" "}
        <RelativeTime iso={run.finished_at} />. Whatever rows exist below are partial, and no
        count is stated for the same reason.
      </p>
    )
  }

  return (
    <p role="note" className="text-meta text-muted-foreground">
      The index last ran <RelativeTime iso={run.finished_at} /> and found{" "}
      {run.call_sites === null ? "no recorded count of" : run.call_sites.toLocaleString()} call
      sites. Anything absent below was looked for and not found, rather than not looked for.
    </p>
  )
}
