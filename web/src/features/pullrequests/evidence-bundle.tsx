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
 *
 * ## The stage is a ruled row, `CI-W375`, superseding M7-W180's frame
 *
 * The mock draws these five as rows inside one panel, separated by rules, each with its own time
 * on the right — and the 2026-08-18 ruling makes the mock authoritative for what it *draws*. So
 * the five `MetricPanel`s are one `ol` of ruled `li`s.
 *
 * **This does not discard M7-W180's argument; it is the first arrangement that actually settles
 * it.** That ruling was reacting to a real defect — each stage drew its own hairline border, and
 * M7-W179 then gave a multi-line evidence value the vendored card's plane, so a stage carrying
 * `diagnostics` or `replay_evidence` drew a card inside a hand-spelled border: two rectangles at
 * two radii with nothing to tell them apart. It fixed that by promoting the outer box to a
 * labelled panel, and recorded honestly that the box count had not changed.
 *
 * A rule is not a box. The outer rectangle is gone rather than relabelled, so a stage carrying a
 * block now draws exactly one frame — the block's — which is what M7-W180's own ruling 4 wanted
 * and could not reach without flattening something it did not own. Five verdicts do not run
 * together in one column, because the rule separates them and each row's title carries its weight.
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-pull-request.md` is still the mapping table that
 * port was gated on; this supersedes its ruling 3 for this file alone.
 *
 * ## What each node *is* is not described here, `CI-W379`
 *
 * Each stage carried a sentence explaining what that node does. `features/workflows/node-sequence
 * .tsx` already carries one for every node of the graph, including all five of these, and the two
 * were written in different words for the same fact — which `CLAUDE.md` calls the most expensive
 * debt in this repository precisely because the disagreement is silent.
 *
 * Measured before removing them: this screen carried 1,309 characters of prose against the drawn
 * mock's 282–579 across its own screens, and these five sentences were 757 of them — 58% of the
 * screen, in one constant. Removing them lands it at roughly 552, inside the mock's range.
 *
 * **This is a deduplication rather than a cut, and the distinction is load-bearing** — `M0-W329`
 * says the prose ratio names the problem and does not license deletion. Nothing was lost: the
 * canonical description is one click away on the Solution Workflow screen, which this file's own
 * opening paragraph already points at. What stays here is each node's *verdict*, which is the
 * question a reviewer opened this bundle to ask.
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
 * The stage titles below are written for a run that reached them, and rendering them
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

/**
 * The five stages, each a titled block on the card plane, in the order the graph runs them.
 *
 * An `ol` rather than a `div`, because the order is a fact about the run rather than a layout
 * choice: `sync.dashboard.queries` returns `WORKFLOW_NODES` order and this file renders five of
 * them in it, so the list is ordered in the markup as well as on screen.
 *
 * The panel body is one child rather than several. `MetricPanel`'s content is a `gap-section`
 * column and `NodeEvidence` already carries its own `mt-section`, so handing the panel three
 * siblings would spend both and double every gap inside a stage.
 */
function BundleStages({
  staged,
}: {
  staged: { stage: BundleStage; node: WorkflowNode | undefined }[]
}) {
  return (
    /* One panel of ruled rows rather than five stacked panels, which is what the mock draws and
       is the denser reading of the same five stages: a reviewer scanning for the one node that
       did not run reads five titles down a single edge instead of five framed boxes. Each row
       carries its own timestamp on the right, where the mock puts it.

       The rule sits on every row but the first, so the group reads as one list with separators
       rather than as five things that happen to be adjacent. */
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
              {/* `last_seen_at` is when the checkpointer last wrote this node, and it is optional
                  on the transport. A node that has one gets it; a node that does not gets the
                  absence marker rather than an empty column, because a blank right edge reads as
                  "nothing happened" and the truth is "this run recorded no time for it". */}
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
