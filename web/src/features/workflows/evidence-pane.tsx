/**
 * The left pane: what the run read and did, in the order it did it.
 *
 * The Stitch reference calls this column *Evidence timeline* and draws it as a marker rail with one
 * card per step. We already draw that rail — `NodeSequence` is it — so the composition transfers
 * and the figures do not. The reference's per-span milliseconds (`AuthMiddleware.verifyToken 4ms`)
 * come from an OpenTelemetry waterfall; this route reads the LangGraph checkpointer, which holds no
 * spans and no per-node timing at all (B123). What each node carries instead is what it actually
 * produced.
 *
 * **The pane scrolls; the pane's header does not.** Exactly one `PaneScroll` inside one `Pane`, so
 * this half owns one scrollbar and the page owns none.
 *
 * Nothing in this pane claims a node is executing. A standing is the checkpoint's own last word,
 * and a run parked on the customer's CI writes the same nothing as a run whose process died.
 */

import { History } from "lucide-react"
import { Link } from "react-router"

import { WORKFLOW_POLL_MS } from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { PanelPane } from "@/components/pane"
import { ActivityTimeline } from "@/features/workflows/activity-timeline"
import { AgentActivityPanel } from "@/features/workflows/agent-activity-panel"
import { NodeSequence } from "@/features/workflows/node-sequence"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { SupersededGenerations } from "@/features/workflows/superseded-generations"
import { findingHref } from "@/lib/hrefs"

/** Pinned character-for-character by `workflow-page.test.tsx`. It moved; it did not change. */
export const NODE_BY_NODE_INTRO =
  "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing."

/**
 * What `RunOutcome` may say about this pane, which renders all eight nodes as a narrative and
 * places the outcome inside the sequence rather than above it. The panel does not know that; this
 * file does, so the sentences that depend on position live here.
 *
 * The `abandoned` wording still holds after the rebuild: the sequence stays whole inside one pane,
 * so "the entries above this one" and "any entry after it" still describe what a reader sees.
 */
const BELOW: BelowThisPanel = {
  inFlight: `Every entry here is the last state the checkpointer recorded, re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`,
  abandoned:
    "The attempt is still here in full: the entries above this one are what ran, with everything each node produced, and any entry after it is a node the run never reached.",
  opened: (
    <>
      The pull request is under <code>open_pr</code>.
    </>
  ),
  unrecognised: "The entries here are still what the run produced.",
}

/**
 * The narrative's opening entry: what arrived, and what this route can and cannot see about it.
 *
 * The vendor clause is the deleted fact rail's Vendor row, and it is a route boundary rather than
 * an oversight: the checkpointer holds the run, not the finding. Saying so is what stops a reader
 * reading its absence as a screen that forgot.
 */
function Arrival({ repoId, findingId }: { repoId: string; findingId: string }) {
  return (
    <>
      <h3 className="text-emphasis">What arrived</h3>
      <div className="mt-row flex max-w-prose flex-col gap-row text-body text-muted-foreground">
        <p>A finding arrived from the API Dependency Graph, and this run is what Sync did about it.</p>
        <p>
          Read from the checkpointer, which is a different database from the API Dependency
          Graph — this screen carries no indexing timestamp, no binding rung and no vendor for that
          reason: the checkpointer holds the run, not the finding.{" "}
          <Link to={findingHref(repoId, findingId)} className="underline underline-offset-2">
            The finding itself
          </Link>{" "}
          carries all three.
        </p>
        <p>
          The entries below are the remediation graph&#39;s own order, with the evidence each node
          produced. A node marked due after it has already run is a retry the graph owes another
          visit, not a finished step — the loop is real and this view does not hide it.
        </p>
      </div>
    </>
  )
}

export function EvidencePane({
  repoId,
  findingId,
  data,
}: {
  repoId: string
  findingId: string
  data: WorkflowState
}) {
  return (
    <section aria-label="Evidence" className="flex min-h-0 min-w-0 flex-col">
      <PanelPane label="Evidence" icon={History} bodyClassName="p-section">
        {/* Auto-height wrapper, and it is load-bearing: `MetricPanel` carries `h-full`, so a panel
            placed directly inside a scroller with a definite height would stretch to fill the
            whole pane and push its siblings out of view. */}
        <div className="flex min-w-0 flex-col gap-8">
          <MetricPanel label="Node by node" caption={NODE_BY_NODE_INTRO}>
            {data.nodes.length === 0 ? (
              <>
                <Arrival repoId={repoId} findingId={findingId} />
                {/* An empty `nodes` array used to render a bare ordered list with a marker rule
                    and no explanation, which reads as a run that has not started. It is not one. */}
                <p className="max-w-prose text-body text-ink-muted">
                  The checkpointer answered for this run and listed no nodes. That is a measured
                  nothing, not a run that has not started.
                </p>
                <RunOutcome
                  outcome={data.outcome}
                  abandonReason={data.abandon_reason}
                  reportReason={data.report_reason}
                  below={BELOW}
                  frame="entry"
                />
              </>
            ) : (
              <NodeSequence
                nodes={data.nodes}
                outcome={data.outcome}
                opening={<Arrival repoId={repoId} findingId={findingId} />}
                closing={
                  <RunOutcome
                    outcome={data.outcome}
                    abandonReason={data.abandon_reason}
                    reportReason={data.report_reason}
                    below={BELOW}
                    frame="entry"
                  />
                }
              />
            )}
          </MetricPanel>

          <ActivityTimeline state={data} />

          <AgentActivityPanel repoId={repoId} findingId={findingId} run={data} />

          <SupersededGenerations
            generations={data.generations}
            currentThreadId={data.thread_id}
          />
        </div>
      </PanelPane>
    </section>
  )
}
