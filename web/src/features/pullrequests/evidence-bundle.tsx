/**
 * The pull request's evidence bundle, in the remediation graph's own order.
 *
 * `sync.dashboard.queries.workflow_state` always returns all eight nodes of a run in
 * `WORKFLOW_NODES` order; this file renders the five that answer "did this patch earn a merge" in
 * that order, and the Solution Workflow page shows all eight. What each node *is* is described
 * once, in `features/workflows/node-sequence.tsx` — saying it here again was 757 of this screen's
 * 1,309 characters of prose against the mock's 282–579 (`CI-W379`), so what stays is each node's
 * verdict. Ruled rows in one panel rather than five framed stages, per the 2026-08-18 ruling that
 * the mock is authoritative for what it draws (`CI-W375`), superseding ruling 3 of
 * `docs/superpowers/briefs/2026-08-07-substrate-pull-request.md` for this file alone.
 */

import type { WorkflowNode, WorkflowNodeName, WorkflowOutcome } from "@/api/types"
import { Absent } from "@/components/status"
import { NodeEvidence } from "@/features/workflows/evidence"
import { STANDING_SENTENCE } from "@/features/workflows/node-standing"
import { formatTimestamp } from "@/lib/format"

type BundleNodeName = Extract<
  WorkflowNodeName,
  "static_verify" | "replay" | "push_branch" | "await_ci" | "open_pr"
>

interface BundleStage {
  name: BundleNodeName
  title: string
}

/** Exported so the status band counts this set rather than restating its size. */
export const BUNDLE_STAGES: BundleStage[] = [
  {
    name: "static_verify",
    title: "What the compiler said",
  },
  {
    name: "replay",
    title: "What replay found",
  },
  {
    name: "push_branch",
    title: "Where it was pushed",
  },
  {
    name: "await_ci",
    title: "What the customer's CI said",
  },
  {
    name: "open_pr",
    title: "The pull request",
  },
]

function findNode(nodes: WorkflowNode[], name: BundleNodeName): WorkflowNode | undefined {
  return nodes.find((node) => node.name === name)
}

/**
 * A node this bundle names, but the checkpoint holds no evidence for.
 *
 * Four different facts wear this same shape and must not be said the same way: the graph has not
 * reached the node yet; it reached it and the run ended without it producing this bundle's fields;
 * the graph owes it a visit; or the payload carries no node under this name at all. This component
 * collapsed the third onto "Running now.", a liveness claim no checkpoint supports; the first three
 * now arrive as `standing` from `sync.dashboard.queries`, worded once in `node-standing.ts`.
 */
function EmptyStage({ node }: { node: WorkflowNode | undefined }) {
  if (node === undefined) {
    return (
      <p className="text-body text-muted-foreground">
        The run carries no node under this name — the remediation graph has changed since this
        bundle was written.
      </p>
    )
  }
  if (node.standing === "ran") {
    // A node reaches "ran" with none of these fields only by failing before writing them: an
    // exception out of push_branch, await_ci or open_pr returns "fatal" without the field this
    // bundle names, and the reason is the run's own abandon_reason, not a field on the node.
    return (
      <p className="text-body text-muted-foreground">
        This node ran and produced none of the fields this bundle names — see the run's outcome
        above for why.
      </p>
    )
  }
  return <p className="text-body text-muted-foreground">{STANDING_SENTENCE[node.standing]}</p>
}

/**
 * What this bundle is, on a run that did not open a pull request.
 *
 * Rendering the stage titles unconditionally headed a `reported` run's page with "What Sync
 * actually opened." over five "Never reached" rows — a page asserting a pull request that routing
 * had decided against. `opened` gets no sentence: the panel above it already says the run opened
 * one.
 */
function Framing({ outcome }: { outcome: WorkflowOutcome | null }) {
  if (outcome === "opened") return null

  const sentence =
    outcome === "reported"
      ? "No pull request exists for this run. Routing decided no patch was warranted, so nothing below was attempted — the reason it decided that is in the panel above."
      : outcome === "abandoned"
        ? "No pull request exists for this run: Sync abandoned it before one was opened."
        : outcome === null || outcome === "running"
          ? "Whether this run reaches a pull request is not yet decided. The five nodes below are the evidence it has produced so far, and a node the graph still owes a visit says so."
          : "The console does not recognise this run's outcome, so it cannot say whether a pull request exists for it. The five nodes below are still what the run produced."

  return <p className="max-w-prose text-body text-muted-foreground">{sentence}</p>
}

/**
 * A `reported` run reached none of the five, so there are no five rows to draw.
 *
 * The nodes are named here rather than drawn as five identical "Never reached" rows, which read as
 * a run that got partway.
 */
function NothingAttempted() {
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      None of the five nodes this bundle names — <code className="font-mono">static_verify</code>,{" "}
      <code className="font-mono">replay</code>, <code className="font-mono">push_branch</code>,{" "}
      <code className="font-mono">await_ci</code> and <code className="font-mono">open_pr</code> —
      was ever reached, and none produced anything. That is not a gap in this view: a run that
      reports rather than patches ends before any of them runs.
    </p>
  )
}

export function EvidenceBundle({
  nodes,
  outcome,
}: {
  nodes: WorkflowNode[]
  outcome: WorkflowOutcome | null
}) {
  const staged = BUNDLE_STAGES.map((stage) => ({
    stage,
    node: findNode(nodes, stage.name),
  }))
  const anyEvidence = staged.some(
    ({ node }) => node !== undefined && Object.keys(node.evidence).length > 0
  )

  return (
    <div className="flex flex-col gap-section">
      <Framing outcome={outcome} />
      {outcome === "reported" && !anyEvidence ? (
        <NothingAttempted />
      ) : (
        <BundleStages staged={staged} />
      )}
    </div>
  )
}

/** The five stages as ruled rows — an `ol` because the order is the graph's, not a layout choice. */
function BundleStages({
  staged,
}: {
  staged: { stage: BundleStage; node: WorkflowNode | undefined }[]
}) {
  return (
    <ol className="flex min-w-0 flex-col">
      {staged.map(({ stage, node }, index) => {
        const hasEvidence = node !== undefined && Object.keys(node.evidence).length > 0

        return (
          <li
            key={stage.name}
            className={`min-w-0 py-field ${index === 0 ? "" : "border-line border-t"}`}
          >
            <div className="flex min-w-0 items-baseline justify-between gap-row">
              <h3 className="text-body font-medium">{stage.title}</h3>
              {/* `last_seen_at` is optional on the transport; a node without one gets the absence
                  marker rather than an empty column, which reads as "nothing happened". */}
              <span className="shrink-0 font-mono text-meta text-ink-muted">
                {node?.last_seen_at ? (
                  formatTimestamp(node.last_seen_at)
                ) : (
                  <Absent>no time recorded</Absent>
                )}
              </span>
            </div>
            {node?.standing === "due_again" && (
              <p className="mt-field max-w-prose text-body">{STANDING_SENTENCE.due_again}</p>
            )}
            {hasEvidence ? (
              <NodeEvidence name={stage.name} evidence={node.evidence} />
            ) : (
              <div className="mt-field">
                <EmptyStage node={node} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
