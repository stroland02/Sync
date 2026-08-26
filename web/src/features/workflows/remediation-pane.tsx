/**
 * The right pane: what the run produced, and what checked it.
 *
 * The Stitch reference draws four blocks here — Proposed Fix, Verification Results, Implementation
 * Status, and a footer bar of three buttons. All four transfer. Two of their contents do not, and
 * the substitutions are the argument of this screen rather than a compromise on it.
 *
 * **"Overall Agent Confidence — 98%" with a progress bar is refused, and this pane is where the
 * refusal has to be legible.** `web/CLAUDE.md` bans a composite score, and averaging *we could not
 * check* with *we checked and it passed* is exactly what that bar does. In its place: the two
 * checks `verificationChain` already derives, reported as two checks, each legible without colour —
 * and the two paragraphs saying what a confidence number compresses, placed exactly where a reader
 * who has seen the reference would look for the bar.
 *
 * **"Unit Tests — Passed 142/142" is refused because we run no unit tests.** `static_verify` runs
 * the clone's own `tsc` and `await_ci` watches the customer's CI. Those are the two checks that
 * exist, and they are the two that are shown.
 *
 * **The footer bar's three buttons stay named in prose, by the owner's ruling of 2026-08-21.**
 * Sync's API is read-only — `tests/test_api_routes.py::test_no_route_reaches_past_the_read_surface`
 * holds it — and a control drawn for a capability the product does not have reads as a feature
 * merely switched off. Each is named along with the route it would need, in the position the
 * reference gives the bar, which is where a reviewer looks for them.
 *
 * **Two routes answer this pane and it says which is which.** The diff comes from
 * `GET /api/findings/{id}/patch`; the verdicts come from the checkpointer. Neither holds an authored
 * summary or a root-cause statement, so neither is rendered — an empty heading would be a claim
 * that one exists and is missing.
 *
 * **Two rows the spec asked for are deliberately not here, both measured against the seed corpus on
 * 2026-08-26 and both the same defect: one fact rendered twice, disagreeing.** `PatchTargetList`
 * beside the diff put the branch on this pane a second time, above the panel named for exactly that
 * question. And `PatchResponse.strategy` under the diff is not the same field as the top bar's
 * `Strategy` tile, which reads `nodes[patch].evidence.attempt_strategy`: on
 * `9f176dea…` the tile read `agent` while the row read *patch has produced no attempt*. Two
 * "Strategy" values on one screen contradicting each other is worse than one of them being absent,
 * so the tile owns it.
 */

import { Wrench } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import { usePatch } from "@/api/queries"
import type { WorkflowNode, WorkflowState } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { PanelPane } from "@/components/pane"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import { Diff, PatchStat, VerificationChain } from "@/features/pullrequests/patch-parts"
import { NodeEvidence, NodeEvidenceBlocks } from "@/features/workflows/evidence"
import { STANDING_SENTENCE } from "@/features/workflows/node-standing"
import { ReplyBox } from "@/features/workflows/reply-box"
import { runIdentity } from "@/features/workflows/run-identity"
import { asHttpUrl } from "@/lib/url"
import { findingHref, pullRequestHref } from "@/lib/hrefs"

type PatchQuery = ReturnType<typeof usePatch>

/** What each action a reviewer would reach for would need first. Named, so the gap is a work item. */
const ACTIONS: { label: string; needs: string }[] = [
  {
    label: "Copy the agent prompt",
    needs: "the prompt the remediation agent was given, which no checkpoint channel records",
  },
  {
    label: "Give feedback",
    needs: "a write route that accepts a reviewer's judgement of a run",
  },
  {
    label: "Restart the run",
    needs: "a route that starts remediation, which would mutate the graph",
  },
]

function find(nodes: WorkflowNode[], name: string): WorkflowNode | undefined {
  return nodes.find((node) => node.name === name)
}

/** A scalar row inside a panel: furniture label, mono value, and whichever nothing applies. */
function Line({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-field">
      <p className="furniture text-meta text-ink-muted">{label}</p>
      <div className="min-w-0 text-body break-words">{children}</div>
    </div>
  )
}

/**
 * A node's artefact, or the sentence saying why there is none.
 *
 * Three nothings, and they are three sentences rather than one blank: the run carries no such node
 * at all, the node has a standing that explains itself, or the node ran and recorded none of what
 * this screen names for it.
 */
function NodeArtifact({
  node,
  missing,
  children,
}: {
  node: WorkflowNode | undefined
  /** What it means that this run has no such node. */
  missing: string
  children: ReactNode
}) {
  if (node === undefined) {
    return <p className="max-w-prose text-body text-ink-muted">{missing}</p>
  }
  if (Object.keys(node.evidence).length === 0) {
    return (
      <p className="max-w-prose text-body text-ink-muted">
        {node.standing === "ran"
          ? "This node ran and recorded none of the evidence this screen shows for it — a measured nothing, not a node nobody has opened."
          : STANDING_SENTENCE[node.standing]}
      </p>
    )
  }
  return <>{children}</>
}

/** The change itself. The one place on this screen where a real diff exists. */
function TheChange({ query }: { query: PatchQuery }) {
  return (
    <MetricPanel
      label="The change this run wrote"
      caption="Served by GET /api/findings/{finding_id}/patch, which is a different route from the checkpointer the rest of this screen reads. Neither holds an authored summary or a root-cause statement, so neither is rendered here."
    >
      {query.isPending && (
        <p className="text-body text-muted-foreground">Asking for the patch this run wrote…</p>
      )}

      {query.isError && (
        <div className="flex flex-col items-start gap-row">
          <p className="text-body text-muted-foreground">
            <Absent>the API did not answer for this patch</Absent>
          </p>
          <Button
            variant="outline"
            size="sm"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            {query.isFetching ? "Asking…" : "Check again"}
          </Button>
        </div>
      )}

      {query.data !== undefined && (
        <>
          <Line label="Why this change">
            {query.data.rationale === null ? (
              // Never falls back to `strategy` or to a node's prose: a rationale nobody wrote is
              // not the same fact as the name of the remediator that wrote the edit.
              <Absent>the run recorded no rationale for this patch</Absent>
            ) : (
              <p className="max-w-prose text-body">{query.data.rationale}</p>
            )}
          </Line>

          {query.data.diff !== null ? (
            <>
              <Diff diff={query.data.diff} />
              <PatchStat stat={query.data.stat} />
            </>
          ) : (
            /* The payload owns which nothing this is: a run that decided against a patch, one that
               gave up and one still working are three different sentences and the console must not
               pick one. */
            <p className="max-w-prose text-body text-ink-muted">{query.data.absent_because}</p>
          )}
        </>
      )}
    </MetricPanel>
  )
}

/** The two checks, the artefacts behind them, and the figure that is refused in their place. */
function WhatCheckedIt({ repoId, findingId, data }: { repoId: string; findingId: string; data: WorkflowState }) {
  const staticVerify = find(data.nodes, "static_verify")
  const replay = find(data.nodes, "replay")

  return (
    <MetricPanel
      label="What checked it"
      caption="Two checks, reported as two. tsc verifies the tree a push would carry, with untracked and ignored paths held out; the customer's CI is theirs and answers on its own schedule."
    >
      <VerificationChain nodes={data.nodes} />

      {/* Only the diagnostics block, never the full node evidence: `verify_ok` is the verdict the
          chain directly above has already put into a sentence, and rendering it again would be one
          fact at two weights. */}
      <NodeEvidenceBlocks name="static_verify" evidence={staticVerify?.evidence ?? {}} />

      <div className="flex min-w-0 flex-col gap-field">
        <p className="furniture text-meta text-ink-muted">Replay</p>
        <NodeArtifact
          node={replay}
          missing="This run carries no replay step, so nothing here says the original failure was reproduced."
        >
          {/* In full, unlike `static_verify`: the chain says nothing at all about replay, so
              omitting its scalars would leave that check unreported rather than unrepeated. */}
          <NodeEvidence name="replay" evidence={replay?.evidence ?? {}} />
        </NodeArtifact>
      </div>

      <p className="max-w-prose text-body text-ink-muted">
        What stands behind a claim on this console is the provenance rung, and the rung lives on the
        API Dependency Graph rather than in the checkpointer.{" "}
        <Link to={findingHref(repoId, findingId)} className="underline underline-offset-2">
          The finding
        </Link>{" "}
        carries it. Nothing here scores how sure a model felt.
      </p>

      <p className="max-w-prose text-body text-ink-muted">
        {/* Argued rather than merely omitted, because an omission is invisible to a reader who has
            seen a competitor's screen -- and this is the position that screen gives its bar. The
            scale quoted is a reference product's own documentation of its `rootCause.confidence`
            field (`superlog-02` in the reference notes), read on 2026-08-18. */}
        A confidence score is not a different answer to this question — it is this one compressed.
        The scales that carry it read “ten means direct, verbatim evidence: a line of code, a
        matching stacktrace, a clear log message; zero means speculative.” That is a{" "}
        <strong>class of evidence</strong>, which is what the rung records — a line of code is{" "}
        <code className="font-mono">static</code>, a matching trace is{" "}
        <code className="font-mono">observed</code>, and nothing found is{" "}
        <code className="font-mono">unresolved</code>. Collapsing those onto a number loses which one
        it was, and then needs a footnote telling you where to cut the scale. We keep the class and
        skip the number.
      </p>
    </MetricPanel>
  )
}

/** Where the change went: the branch, the pull request, and the CI run that watched it. */
function WhereItWent({ patch, nodes }: { patch: PatchQuery; nodes: WorkflowNode[] }) {
  const awaitCi = find(nodes, "await_ci")
  const target = patch.data?.target
  const ciUrlPresent = awaitCi !== undefined && "ci_url" in awaitCi.evidence
  const ciUrl = ciUrlPresent ? asHttpUrl(awaitCi.evidence.ci_url) : null

  return (
    <MetricPanel
      label="Where it went"
      caption="The branch and the pull request come from the patch route; the CI run is what await_ci recorded watching."
    >
      <Line label="Branch">
        {target?.branch == null ? (
          <Absent>this patch was never pushed</Absent>
        ) : (
          <code className="font-mono text-meta break-all">{target.branch}</code>
        )}
      </Line>

      <Line label="Pull request">
        {target?.pr_url == null ? (
          <Absent>no pull request was opened for this run</Absent>
        ) : (
          <a
            href={target.pr_url}
            target="_blank"
            rel="noreferrer noopener"
            className="font-mono text-meta break-all underline underline-offset-2"
          >
            {target.pr_number === null ? target.pr_url : `#${target.pr_number}`}
          </a>
        )}
      </Line>

      <Line label="CI run">
        {/* Two nothings one key apart: a run that never reached the customer's CI, and a run that
            reached it and recorded no URL. The payload distinguishes them and so does this. */}
        {!ciUrlPresent ? (
          <Absent>the run never reached the customer&#39;s CI</Absent>
        ) : ciUrl === null ? (
          <Absent>the run reached CI and recorded no URL</Absent>
        ) : (
          <a
            href={ciUrl}
            target="_blank"
            rel="noreferrer noopener"
            className="font-mono text-meta break-all underline underline-offset-2"
          >
            {ciUrl}
          </a>
        )}
      </Line>
    </MetricPanel>
  )
}

export function RemediationPane({
  repoId,
  findingId,
  data,
}: {
  repoId: string
  findingId: string
  data: WorkflowState
}) {
  // One subscription for two panels: the branch and the pull request come off the same payload as
  // the diff, and two `usePatch` calls would be two subscriptions to one answer.
  const patch = usePatch(findingId)

  return (
    <section aria-label="Remediation" className="flex min-h-0 min-w-0 flex-col">
      <PanelPane label="Remediation" icon={Wrench} bodyClassName="p-section">
        {/* Auto-height wrapper: `MetricPanel` carries `h-full` and would stretch to the whole pane
            if it sat directly inside a scroller with a definite height. */}
        <div className="flex min-w-0 flex-col gap-8">
          <TheChange query={patch} />

          <WhatCheckedIt repoId={repoId} findingId={findingId} data={data} />

          <WhereItWent patch={patch} nodes={data.nodes} />

          <MetricPanel
            label="A reviewer's turn"
            caption="The position the reference gives Dismiss / Escalate to On-Call / Apply Fix & Deploy. None of the three can act, and each is named with what it would need."
          >
            <ReplyBox waitingOn={runIdentity(data).waitingOn} />

            <p className="max-w-prose text-meta text-ink-muted">
              Three things a reviewer would reach for on this run:{" "}
              {ACTIONS[0].label.toLowerCase()}, {ACTIONS[1].label.toLowerCase()},{" "}
              {ACTIONS[2].label.toLowerCase()}. None of these can act. Sync&#39;s API is read-only —
              no route mutates a run or starts one — so each is named here in prose rather than
              drawn as a control that cannot act, because an action that disappears reads as an
              oversight. Copying the agent prompt needs {ACTIONS[0].needs}; feedback needs{" "}
              {ACTIONS[1].needs}; restarting needs {ACTIONS[2].needs}.
            </p>

            <p className="max-w-prose text-body text-muted-foreground">
              <Link to={pullRequestHref(repoId, findingId)} className="underline underline-offset-2">
                {data.outcome === "opened"
                  ? "See the pull request's evidence bundle"
                  : "See the evidence bundle for this run"}
              </Link>{" "}
              — the five nodes that answer whether this run earned a merge, at their own address a
              reviewer can send on.
            </p>
          </MetricPanel>
        </div>
      </PanelPane>
    </section>
  )
}
