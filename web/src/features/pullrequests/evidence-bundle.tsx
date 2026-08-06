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

import type { WorkflowNode, WorkflowNodeName } from "@/api/types"
import { NodeEvidence } from "@/features/workflows/evidence"

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
      "What Sync actually opened. The bundle it assembles for a reviewer — the spec diff, the changelog entry, and the call sites it touched — is not exposed by this transport beyond the two fields below: sync.dashboard.queries reads only pr_url and pr_number out of the checkpoint, so that is all this page can show.",
  },
]

function findNode(nodes: WorkflowNode[], name: BundleNodeName): WorkflowNode | undefined {
  return nodes.find((node) => node.name === name)
}

/**
 * A node this bundle names, but the checkpoint holds no evidence for.
 *
 * Three different facts wear this same shape and must not be said the same way: the graph
 * has not reached the node yet and may still; the graph reached it and the run then ended
 * without it ever producing this bundle's fields, so it never will for this generation; or
 * the node is running right now. Collapsing any two of these into one sentence is the
 * "nearly right label" defect this milestone keeps finding.
 */
function EmptyStage({
  node,
  terminal,
}: {
  node: WorkflowNode | undefined
  terminal: boolean
}) {
  const status = node?.status ?? "pending"
  if (status === "current") {
    return <p className="text-body text-muted-foreground">Running now.</p>
  }
  if (status === "pending") {
    return (
      <p className="text-body text-muted-foreground">
        {terminal ? "Never reached — the run ended before the graph got here." : "Not reached yet."}
      </p>
    )
  }
  // status === "done" and evidence is still empty: the node ran and produced none of this
  // bundle's fields, which happens only when it failed before writing them — an exception
  // out of push_branch, await_ci or open_pr returns "fatal" without the field this bundle
  // names. The reason is the run's own abandon_reason, not a field this node carries.
  return (
    <p className="text-body text-muted-foreground">
      This node ran and produced none of the fields this bundle names — see the run's outcome
      above for why.
    </p>
  )
}

export function EvidenceBundle({
  nodes,
  terminal,
}: {
  nodes: WorkflowNode[]
  terminal: boolean
}) {
  return (
    <ol className="flex flex-col gap-section">
      {BUNDLE_STAGES.map((stage) => {
        const node = findNode(nodes, stage.name)
        const hasEvidence = node !== undefined && Object.keys(node.evidence).length > 0
        const revisiting = node?.status === "current" && hasEvidence

        return (
          <li key={stage.name} className="rounded border border-border p-section">
            <h3 className="text-emphasis">{stage.title}</h3>
            <p className="mt-field max-w-prose text-body text-muted-foreground">{stage.blurb}</p>
            {revisiting && (
              <p className="mt-field max-w-prose text-body">
                This is what the previous attempt produced — the graph owes this node another
                visit, so it is not the finished answer.
              </p>
            )}
            {hasEvidence ? (
              <NodeEvidence name={stage.name} evidence={node.evidence} />
            ) : (
              <div className="mt-field">
                <EmptyStage node={node} terminal={terminal} />
              </div>
            )}
          </li>
        )
      })}
    </ol>
  )
}
