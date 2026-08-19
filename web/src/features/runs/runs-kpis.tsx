/**
 * Dashboard R1: the Logs → Runs page's opening facts.
 *
 * **Every figure is `by_disposition`, which the payload computes before the outcome filter is
 * applied** — `sync.dashboard.fleet.runs` says so in its own docstring. So this strip describes
 * every run, and the table beneath describes whichever the reader narrowed to. That is exactly
 * the slot a tile earns: what you filtered yourself away from.
 *
 * **"In flight" is a run with no outcome written, and nothing here calls it live.** A run parked
 * on the customer's CI and a run whose process died look identical in this data — `CLAUDE.md`
 * names that as the reason a status dot is refused on this console, and the same refusal applies
 * to the word. The tile says *no outcome recorded*, which is the fact, rather than *running*,
 * which is an inference the graph cannot support.
 *
 * **No merge rate and no success percentage.** Runs that opened a pull request over runs total
 * is a ratio whose denominator includes runs that were never going to open one, and a figure
 * that reads as a quality score is the composite this console refuses. The counts sit beside each
 * other and the reader does their own division if they want it.
 */

import type { RunsPage } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { Absent } from "@/components/status"

export function RunsKpis({ page }: { page: RunsPage }) {
  const opened = page.by_disposition.opened ?? 0
  const abandoned = page.by_disposition.abandoned ?? 0
  // The payload keys finished outcomes and folds everything unfinished under a null key, which
  // arrives as the string "null" through JSON. Both spellings are read rather than one guessed.
  const inFlight =
    page.by_disposition.null ??
    page.unfiltered_total - Object.entries(page.by_disposition)
      .filter(([key]) => key !== "null")
      .reduce((sum, [, n]) => sum + n, 0)

  return (
    <KpiStrip
      items={[
        {
          label: "Runs recorded",
          value: page.unfiltered_total.toLocaleString(),
          note: "every attempt, before any narrowing on this page",
        },
        {
          label: "Opened a pull request",
          value: opened.toLocaleString(),
          note: "reached the forge with a verified patch",
        },
        {
          label: "Abandoned",
          value: abandoned.toLocaleString(),
          // Abandonment is data, not failure -- CLAUDE.md's own framing, and the note carries it
          // so the tile is not read as a defect count.
          note: "gave up, with a reason recorded",
        },
        {
          label: "No outcome recorded",
          value: inFlight <= 0 ? <Absent>none</Absent> : inFlight.toLocaleString(),
          // Never "in flight" or "running": nothing here distinguishes a run parked on the
          // customer's CI from one whose process died.
          note: "still open, or stopped without writing one — this cannot tell them apart",
          figure: inFlight > 0,
        },
      ]}
    />
  )
}
