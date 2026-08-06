/**
 * The pull request's evidence bundle, in the remediation graph's own order.
 *
 * `sync.dashboard.queries.workflow_state` always returns all eight nodes of a run, in
 * `WORKFLOW_NODES` order. This file renders the five that answer "did this patch earn a
 * merge" — the compiler, the replay, the push, the customer's CI, and the pull request
 * itself — in the same order the graph runs them, not a designer's grouping. `locate` and
 * `prepare` decide whether a patch is attempted at all, and `patch` produces the edit; none
 * of the three is evidence *for* a pull request, so none is repeated here. The Solution
 * Workflow page already shows all eight, node by node.
 */

import type { WorkflowNode, WorkflowNodeName, WorkflowOutcome } from "@/api/types"
import { NodeEvidence } from "@/features/workflows/evidence"
import { STANDING_SENTENCE } from "@/features/workflows/node-standing"

type BundleNodeName = Extract<
  WorkflowNodeName,
  "static_verify" | "replay" | "push_branch" | "await_ci" | "open_pr"
>

interface BundleStage {
  name: BundleNodeName
  title: string
  blurb: string
}

const BUNDLE_STAGES: BundleStage[] = [
  {
    name: "static_verify",
    title: "What the compiler said",
    blurb:
      "Whether the tree this pull request would carry actually compiles, using the clone's own tsc.",
  },
  {
    name: "replay",
    title: "What replay found",
    blurb:
      "Whether the patched call path behaves correctly against a mock of the vendor's new response — stronger than a typecheck, and cheaper than spending a CI run to find out.",
  },
  {
    name: "push_branch",
    title: "Where it was pushed",
    blurb: "The branch the patch was pushed to, in the customer's own repository.",
  },
  {
    name: "await_ci",
    title: "What the customer's CI said",
    blurb: "The customer's own pipeline, watched rather than trusted — the long pole of the run.",
  },
  {
    name: "open_pr",
    title: "The pull request",
    blurb:
      "What Sync opened, on a run that reached this node. The bundle it assembles for a reviewer — the spec diff, the changelog entry, and the call sites it touched — is not exposed by this transport beyond the two fields below: sync.dashboard.queries reads only pr_url and pr_number out of the checkpoint, so that is all this page can show.",
  },
]

function findNode(nodes: WorkflowNode[], name: BundleNodeName): WorkflowNode | undefined {
  return nodes.find((node) => node.name === name)
}

/**
 * A node this bundle names, but the checkpoint holds no evidence for.
 *
 * Four different facts wear this same shape and must not be said the same way: the graph has
 * not reached the node yet and may still; the graph reached it and the run then ended without
 * it ever producing this bundle's fields, so it never will for this generation; the graph owes
 * it a visit; or the payload does not carry a node under this name at all. Collapsing any two
 * of these into one sentence is the "nearly right label" defect this milestone keeps finding —
 * and this component collapsed the third onto "Running now.", a liveness claim no checkpoint
 * supports. The first three now arrive as `standing` from `sync.dashboard.queries` and are
 * worded once in `node-standing.ts`, because the same three were also being classified
 * separately on the Solution Workflow screen.
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
    // The node ran and produced none of this bundle's fields, which happens only when it
    // failed before writing them — an exception out of push_branch, await_ci or open_pr
    // returns "fatal" without the field this bundle names. The reason is the run's own
    // abandon_reason, not a field this node carries.
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
 * The stage blurbs below are written for a run that reached them, and rendering them
 * unconditionally headed a `reported` run's page with "What Sync actually opened." and five
 * "Never reached" rows — a page asserting a pull request that routing had decided against.
 * The outcome is on the payload, so the framing follows it rather than presupposing the happy
 * path. `opened` gets none of this: the panel above it already says the run opened one, and a
 * second sentence saying so is a fact written twice.
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
 * The nodes are named here rather than rendered as five identical "Never reached" panels: the
 * fact is one fact, and five copies of it read as a run that got partway. Naming them keeps
 * what this bundle would have shown visible, which is the part that must not be lost.
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

function BundleStages({
  staged,
}: {
  staged: { stage: BundleStage; node: WorkflowNode | undefined }[]
}) {
  return (
    <ol className="flex flex-col gap-section">
      {staged.map(({ stage, node }) => {
        const hasEvidence = node !== undefined && Object.keys(node.evidence).length > 0

        return (
          <li key={stage.name} className="rounded border border-border p-section">
            <h3 className="text-emphasis">{stage.title}</h3>
            <p className="mt-field max-w-prose text-body text-muted-foreground">{stage.blurb}</p>
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
