/**
 * The Findings tab: what this run settled, apart from the transcript of how it got there.
 *
 * Activity is the turn-by-turn record. This is the output a reviewer merges on — the verdict the
 * graph recorded, and the artifacts the five verification nodes produced. The split is a closed set
 * (`SETTLED_NODES`) rather than a per-render judgement, so a reader who learns what this tab holds
 * on one run is right about the next one.
 *
 * **Three things a reference incident view carries here are not on this payload, and the tab says
 * so rather than filling the space.** There is no authored summary, no root-cause statement and no
 * diff: the checkpointer records channels the graph wrote, and none of those three is one of them.
 * Inventing any of them would be a claim nothing computed, on the one screen whose whole argument
 * is that it does not ask to be trusted on faith.
 *
 * **And the fourth is the one that matters most.** That view puts a confidence number beside its
 * root cause. Ours would put the provenance rung — what class of evidence stands behind the claim —
 * except that the rung belongs to the API Dependency Graph and this route reads the checkpointer.
 * So the tab names the rung and sends the reader to the finding that holds it, which is a shorter
 * walk than a number that means nothing.
 */

import { Link } from "react-router"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { NodeEvidence } from "@/features/workflows/evidence"
import { STANDING_LABEL } from "@/features/workflows/node-standing"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

import { findingHref, pullRequestHref } from "@/lib/hrefs"
/**
 * The nodes whose evidence is an artifact rather than a step of the story.
 *
 * The same five the Pull Request level's evidence bundle carries, and for the same reason: they are
 * the ones that answer whether this run earned a merge. `locate`, `prepare` and `patch` describe
 * how the run reached its edit, which is the Activity tab's subject.
 */
export const SETTLED_NODES = [
  "static_verify",
  "replay",
  "push_branch",
  "await_ci",
  "open_pr",
] as const

const BELOW: BelowThisPanel = {
  inFlight: "Whatever it has settled so far is below; the rest of the run is under Activity.",
  abandoned:
    "What the run produced before it stopped is below, and the turn-by-turn record of how it got there is under Activity.",
  opened: (
    <>
      The pull request's own evidence is below, under <code>open_pr</code>.
    </>
  ),
  unrecognised: "What the run produced is still below.",
}

function settledNodes(state: WorkflowState): WorkflowNode[] {
  return SETTLED_NODES.map((name) => state.nodes.find((node) => node.name === name)).filter(
    (node): node is WorkflowNode => node !== undefined && Object.keys(node.evidence).length > 0,
  )
}

export function SettledOutput({
  repoId,
  findingId,
  state,
}: {
  repoId: string
  findingId: string
  state: WorkflowState
}) {
  const settled = settledNodes(state)

  return (
    <div className="flex min-w-0 flex-col gap-8">
      <MetricPanel
        label="Settled output"
        caption="The verdict the graph recorded, and the artifacts the verification nodes produced."
      >
        <RunOutcome
          outcome={state.outcome}
          abandonReason={state.abandon_reason}
          reportReason={state.report_reason}
          below={BELOW}
          frame="entry"
        />
        <p className="max-w-prose text-body text-ink-muted">
          This route reads the checkpointer, which records the channels the remediation graph wrote.
          It holds no authored summary, no root-cause statement and no diff, so none of the three is
          rendered here — an empty heading would be a claim that one exists and is missing.
        </p>
        <p className="max-w-prose text-body text-ink-muted">
          What stands behind a claim on this console is the provenance rung, and the rung lives on
          the API Dependency Graph rather than in the checkpointer.{" "}
          <Link
            to={findingHref(repoId, findingId)}
            className="underline underline-offset-2"
          >
            The finding
          </Link>{" "}
          carries it. Nothing here scores how sure a model felt.
        </p>
        <p className="max-w-prose text-body text-ink-muted">
          {/* Argued rather than merely omitted, because an omission is invisible to a reader who has
              seen a competitor's screen. The scale quoted is Superlog's own documentation of its
              `rootCause.confidence` field, read on 2026-08-18. */}
          A confidence score is not a different answer to this question — it is this one compressed.
          The scales that carry it read “ten means direct, verbatim evidence: a line of code, a
          matching stacktrace, a clear log message; zero means speculative.” That is a{" "}
          <strong>class of evidence</strong>, which is what the rung records — a line of code is{" "}
          <code className="font-mono">static</code>, a matching trace is{" "}
          <code className="font-mono">observed</code>, and nothing found is{" "}
          <code className="font-mono">unresolved</code>. Collapsing those onto a number loses which
          one it was, and then needs a footnote telling you where to cut the scale. We keep the
          class and skip the number.
        </p>
      </MetricPanel>

      {settled.length === 0 ? (
        <MetricPanel
          label="Artifacts"
          caption="What a settled run leaves behind: a compiler verdict, a replay result, a branch, a CI run and a pull request."
        >
          <p className="max-w-prose text-body text-ink-muted">
            This run has settled nothing yet — none of the five verification nodes has recorded
            evidence. That is absence rather than zero: it says the run has not got here, not that
            it got here and found nothing.
          </p>
        </MetricPanel>
      ) : (
        settled.map((node) => (
          <Card key={node.name} className="min-w-0">
            <CardHeader className="flex flex-row flex-wrap items-baseline gap-row">
              <h3 className="font-mono text-emphasis">{node.name}</h3>
              <p className="text-meta text-ink-muted">{STANDING_LABEL[node.standing]}</p>
            </CardHeader>
            <CardContent>
              <NodeEvidence name={node.name} evidence={node.evidence} />
            </CardContent>
          </Card>
        ))
      )}

      <p className="max-w-prose text-body text-muted-foreground">
        <Link
          to={pullRequestHref(repoId, findingId)}
          className="underline underline-offset-2"
        >
          {state.outcome === "opened"
            ? "See the pull request's evidence bundle"
            : "See the evidence bundle for this run"}
        </Link>{" "}
        — the five nodes that answer whether this run earned a merge, at their own address a
        reviewer can send on.
      </p>
    </div>
  )
}
