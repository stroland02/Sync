/**
 * Which pull request the fleet's one primary action reviews.
 *
 * `/api/runs` orders newest first, so the first `opened` row is the newest proposed
 * patch. No run opened means no action — a CTA pointing at an invented finding id is
 * fixture data rendered as fact, which is how the previous hardcoded link shipped.
 */

import type { RunRow } from "@/api/types"

export function proposedPatchTarget(runs: RunRow[]): string | null {
  const opened = runs.find((run) => run.outcome === "opened")
  if (opened === undefined) return null
  return `/findings/${encodeURIComponent(opened.finding_id)}/workflow/pull-request`
}
