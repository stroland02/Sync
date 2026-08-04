/**
 * The remediation graph as a sequence of nodes, each with its own state and its own output.
 *
 * Not a progress bar, and the difference is the point. A bar says "sixty per cent" and can
 * only go forwards; this graph loops — a `patch` that failed verification is due again, and
 * a bar would render that as progress. A sequence says which node ran, which one the graph
 * owes a visit, which never started, and what each one produced. That is what a reviewer
 * has to see before trusting a pull request.
 */

import type { WorkflowNode, WorkflowNodeStatus } from "@/api/types"
import { NodeEvidence } from "@/features/workflows/evidence"

/** What each node does, for a reader who has not read `sync.remediate.nodes`. */
const PURPOSE: Record<string, string> = {
  locate: "Read the finding's call site and vendor change out of the graph, then route the change kind to a remediation tier.",
  prepare: "Clone the repository and install its dependencies with the manager its lockfile names, then ask the language adapter whether a patch here can be verified at all.",
  patch: "Edit the call site. Every re-entry is a fresh attempt, carrying the feedback from whichever stage rejected the last one.",
  static_verify: "Compile the tree a push would carry, with untracked and ignored paths held out, using the clone's own tsc.",
  replay: "Execute the patched call path against a mock of the vendor's new response.",
  push_branch: "Push the branch to the customer's repository.",
  await_ci: "Wait on the customer's own CI. This is the long pole of the whole run.",
  open_pr: "Open the pull request, carrying the spec diff, the changelog entry, the call sites and the CI run as evidence.",
}

/**
 * What a node this file has never heard of says about itself.
 *
 * `PURPOSE` is a `Record<string, string>`, so a missing key types as `string` and renders as
 * nothing — a renamed node in the remediation graph would leave a blank line that reads as a
 * layout gap rather than as staleness. Naming the gap is the point: the payload is still
 * honest, this file is the part that has fallen behind.
 */
const UNKNOWN_NODE =
  "This node is not one the console knows about — the remediation graph has changed since this view was written."

interface Appearance {
  glyph: string
  /** What the status means here, in words, because a glyph alone is a legend to memorise. */
  label: string
  markerClass: string
  nameClass: string
}

function appearanceOf(status: WorkflowNodeStatus, terminal: boolean): Appearance {
  switch (status) {
    case "done":
      return {
        glyph: "✓",
        label: "ran",
        markerClass: "border-foreground text-foreground",
        nameClass: "text-foreground",
      }
    case "current":
      return {
        glyph: "▶",
        label: "due now — the graph owes this node a visit",
        markerClass: "border-foreground bg-foreground text-background",
        nameClass: "text-foreground font-semibold",
      }
    case "pending":
      return {
        glyph: "○",
        label: terminal ? "never ran" : "not started",
        markerClass: "border-border text-muted-foreground",
        nameClass: "text-muted-foreground",
      }
  }
}

function Step({
  node,
  isLast,
  terminal,
}: {
  node: WorkflowNode
  isLast: boolean
  terminal: boolean
}) {
  const look = appearanceOf(node.status, terminal)
  const revisited = node.status === "current" && Object.keys(node.evidence).length > 0

  return (
    <li className="grid grid-cols-[auto_1fr] gap-4">
      <div className="flex flex-col items-center">
        <span
          aria-hidden="true"
          className={`flex size-7 shrink-0 items-center justify-center rounded-full border text-xs ${look.markerClass}`}
        >
          {look.glyph}
        </span>
        {!isLast && <span aria-hidden="true" className="w-px flex-1 bg-border" />}
      </div>

      <div className={isLast ? "" : "pb-6"}>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className={`font-mono text-sm ${look.nameClass}`}>{node.name}</h3>
          <p className="text-xs text-muted-foreground">{look.label}</p>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {PURPOSE[node.name] ?? UNKNOWN_NODE}
        </p>
        {revisited && (
          <p className="mt-1 text-sm">
            This node has already produced evidence and the graph owes it another visit — it
            is a retry, not a finished step.
          </p>
        )}
        <NodeEvidence name={node.name} evidence={node.evidence} />
      </div>
    </li>
  )
}

export function NodeSequence({
  nodes,
  terminal,
}: {
  nodes: WorkflowNode[]
  terminal: boolean
}) {
  return (
    <ol className="flex flex-col">
      {nodes.map((node, index) => (
        <Step
          key={node.name}
          node={node}
          isLast={index === nodes.length - 1}
          terminal={terminal}
        />
      ))}
    </ol>
  )
}
