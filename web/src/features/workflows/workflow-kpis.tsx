/**
 * The four run facts that belong in the chrome, not in the page.
 *
 * `KpiStrip` portals into the chassis' second 48px row, so these four sit above every pane at all
 * times while the panes scroll under them. They are the four a reviewer checks without reading:
 * which tier the cascade routed to, which remediator wrote the edit, how far apart the run's
 * checkpoints are, and how many runs the checkpointer holds for this finding.
 *
 * **`Checkpoint span` is not a run duration**, and inheriting that refusal from the deleted
 * `run-fact-rail.tsx` is the point of naming it this way. It is the distance between the first and
 * last checkpoint this run wrote, which is a measurement over real timestamps. A run parked on the
 * customer's CI writes no checkpoint for as long as that takes and a run whose process died writes
 * the same nothing, so "how long it has been running" is a figure nothing computed. The tooltip
 * carries the qualification and `run-identity-header.tsx` carries it in full, on screen, because a
 * scope that lives only in a `note` is a scope qualified nowhere.
 *
 * **There is no outcome tile and no confidence tile.** The outcome is a status-band segment and
 * the narrative's closing entry; a third rendering would be one fact at three weights. A
 * confidence figure is refused outright — `remediation-pane.tsx` carries the argument where the
 * reference draws the bar.
 *
 * The strip restates neither of the status band's own figures (Nodes, Timeline entries): a tile
 * that repeats the band at tile weight earns its slot from nothing.
 */

import type { ReactNode } from "react"

import type { WorkflowState } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { Absent } from "@/components/status"
import { formatSpan, runIdentity } from "@/features/workflows/run-identity"

/**
 * A top-bar cell truncates, so every absence here is short.
 *
 * The long form of each — which nothing it is, in a sentence — stays visible in the header row
 * under the title, where nothing is cut off.
 */
function short(value: string | null, nothing: string): ReactNode {
  return value === null ? <Absent>{nothing}</Absent> : value
}

export function WorkflowKpis({ data }: { data: WorkflowState | undefined }) {
  // An unanswered run publishes nothing rather than four absence markers: the strip collapses via
  // `empty:hidden` and the panes gain the 48px, and the status band is already saying which
  // nothing this is.
  if (data === undefined) return null

  const identity = runIdentity(data)

  return (
    <KpiStrip
      items={[
        {
          label: "Repair tier",
          value: short(identity.tier, "locate recorded no tier"),
          note: "which remediation tier the decision table routed this change kind to",
          figure: false,
        },
        {
          label: "Strategy",
          value: short(identity.strategy, "patch has produced no attempt"),
          note: "which remediator produced the edit for the newest attempt",
          figure: false,
        },
        {
          label: "Checkpoint span",
          value:
            identity.checkpointSpanSeconds === null ? (
              <Absent>nothing stamped</Absent>
            ) : (
              formatSpan(identity.checkpointSpanSeconds)
            ),
          note: "first checkpoint to last — not how long the run took",
          figure: false,
        },
        {
          label: "Generations",
          value: data.generation_count.toLocaleString(),
          note: "runs the checkpointer holds for this finding; this is the newest",
        },
      ]}
    />
  )
}
