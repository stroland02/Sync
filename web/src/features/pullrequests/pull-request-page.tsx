/**
 * The Pull Request level: one proposed change, and everything that checked it, in one locked view.
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../ai_driven_incident_resolution_workflow/`.**
 * The screen it replaces was a `DetailGrid` — a 360px fact rail beside one long scrolling column
 * holding a patch panel, an outcome panel and a five-stage bundle, in that order, at flow layout.
 * Three panes now: the change on the left, how the run ended and the stage-by-stage bundle stacked
 * on the right, each scrolling its own body under a header that holds still. The page itself does
 * not scroll.
 *
 * **The composition is the reference's lower half, inverted.** The reference stacks *Proposed Fix*,
 * *Verification Results* and *Implementation Status* down one column beside an evidence timeline;
 * here the patch is the subject rather than an output beside evidence, so it takes the wide half
 * and the record of what happened to it stacks beside it. Two screens already took that reference's
 * top-level evidence/remediation split (`finding-page.tsx`, `workflow-page.tsx`); taking it a third
 * time would have made a third screen that looks like the other two.
 *
 * **Owner decision 47 is now structural rather than positional.** The verification chain was
 * *beneath* the diff in one scrolling column, which is only "not behind anything" until the diff is
 * sixty lines long. It is pinned in the change pane's foot: it cannot be scrolled away from the
 * patch it judges, and it is still not a disclosure, not a tooltip and not a tab.
 *
 * **What the reference asks for here and this refuses.** `Overall Agent Confidence 98%` and its
 * progress bar — a composite scalar averaging distinct checks, rejected three times on the record.
 * The two checks are reported separately, `tsc` compiled is not the customer's CI, and the absence
 * of a combined figure is stated on screen rather than merely arranged for. Also refused: the
 * `Agent Active` pulse in the reference's pane header (a liveness claim no checkpoint supports —
 * a run parked on the customer's CI writes no checkpoint for as long as that takes, and a run whose
 * process died writes the same nothing), and the `Apply Fix & Deploy` / `Escalate to On-Call` /
 * `Dismiss` action bar, because nothing reaches a deploy, a page or a dismissal from a click here.
 * What survives of that bar is the one destination this screen genuinely offers, in the header.
 *
 * **Three facts the reference's header carries are not on this payload and none is invented.**
 * There is no timestamp anywhere on this route (B123); the repository is B125 — the checkpoint
 * carries `repo` on every run and `workflow_state` forwards eleven other channel values and not
 * that one; and this route reads the LangGraph checkpointer rather than the graph, so there is no
 * `indexed_at` and no binding rung, which the status band says rather than leaving to be inferred.
 */

import type { ReactNode } from "react"
import { FileDiff, Flag, ListChecks } from "lucide-react"
import { useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { WORKFLOW_POLL_MS, useDismissal, usePatch, useWorkflow } from "@/api/queries"
import type { PatchResponse, WorkflowNode } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { PanelPane } from "@/components/pane"
import { InfoHint } from "@/components/info-hint"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent } from "@/components/status"
import { Tag } from "@/components/tag"
import { Button } from "@/components/ui/button"
import { DetailSection } from "@/features/findings/detail-section"
import { HumanRuling, rulingWord, type RulingState } from "@/features/findings/human-ruling"
import { Pending } from "@/features/findings/pending"
import { bundleFacts } from "@/features/pullrequests/bundle-facts"
import { BundleHeader } from "@/features/pullrequests/bundle-header"
import { CheckTile } from "@/features/pullrequests/check-tile"
import { BUNDLE_STAGES, EvidenceBundle } from "@/features/pullrequests/evidence-bundle"
import {
  Diff,
  PatchStat,
  PatchTargetList,
  VISIBLE_DIFF_LINES,
} from "@/features/pullrequests/patch-parts"
import { verificationChain } from "@/features/pullrequests/verification-chain"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { Pane, PaneScroll } from "@/layouts/pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"

export interface PullRequestPageProps {
  readonly question?: string
}

export function PullRequestPage() {
  // Both identifiers come out of the URL, so both are checked before a request is made for them.
  // `repoId` was carried through unchecked and `workspacePath(undefined)` is `/repositories/`, so
  // this screen's workspace links resolved to an address that renders "No screen at this address".
  const { repoId, findingId } = useParams<{ repoId: string; findingId: string }>()
  if (repoId === undefined || findingId === undefined) return <UnknownRoute />
  return <PullRequest repoId={repoId} findingId={findingId} />
}

/**
 * What `RunOutcome` may say about this screen, which renders five of the run's eight nodes.
 *
 * `locate`, `prepare` and `patch` are deliberately not here, so nothing beside this panel may be
 * described as the attempt in full — and the node the workflow screen calls `open_pr` is labelled
 * "The pull request" in the bundle, so naming the channel would send a reader looking for a heading
 * that is not on this page.
 *
 * The words moved from "below" to "beside" with the panel: the outcome no longer sits above the
 * bundle in one column, it sits in a pane next to it, and a sentence claiming a direction the
 * layout does not have is the same defect at a smaller scale.
 */
const BESIDE: BelowThisPanel = {
  inFlight: `The five stages beside this are the last state the checkpointer recorded for them, re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`,
  abandoned:
    "The five stages beside this carry however far the evidence got; locate, prepare and patch are not among them, and the solution workflow shows all eight.",
  opened: "The pull request itself is the last of the five stages beside this.",
  unrecognised: "The five stages beside this are still what the run produced.",
}

/**
 * How many of the five this bundle names the run has actually been through.
 *
 * `ran` and `due_again` are the two standings that mean the graph executed the node at least once;
 * `due` does not — `node-standing.ts` words it as a visit the graph still owes. A node the payload
 * carries no entry for is not reached either, which is why this counts the stages rather than the
 * nodes.
 */
function nodesReached(nodes: WorkflowNode[]): number {
  return BUNDLE_STAGES.filter((stage) => {
    const standing = nodes.find((node) => node.name === stage.name)?.standing
    return standing === "ran" || standing === "due_again"
  }).length
}

/** The window `Diff` draws, counted for the band rather than restated by it. */
function diffWindow(diff: string): string {
  const total = diff.split("\n").length
  return `${Math.min(total, VISIBLE_DIFF_LINES).toLocaleString()} of ${total.toLocaleString()}`
}

/**
 * A top-bar cell truncates, so every absence published there is short.
 *
 * The long form of each — which nothing it is, in a sentence — stays visible on the screen: the
 * header states the pull request's own absence in the outcome's words, and the change pane states
 * the patch's.
 */
function shortPatchFact(
  patch: ReturnType<typeof usePatch>,
  read: (data: PatchResponse) => ReactNode,
): ReactNode {
  if (patch.data !== undefined) return read(patch.data)
  if (patch.isError) {
    return patch.error instanceof NotFoundError ? (
      <Absent>no run recorded</Absent>
    ) : (
      <Absent>not answered</Absent>
    )
  }
  return <Pending />
}

function PullRequest({ repoId, findingId }: { repoId: string; findingId: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  const facts = bundleFacts(data?.nodes ?? [])
  // One read for the whole screen: the change pane draws it, the status band counts its window and
  // the top bar states its file count, and three components each opening their own request is three
  // chances for the figure and the diff beneath it to describe different payloads.
  const patch = usePatch(findingId)
  // Not gated on the run either. `finding_dismissal` is durable and the checkpointer is a different
  // database again, so a finding whose run 404s can still carry a standing somebody recorded.
  const dismissalQuery = useDismissal(findingId)
  const dismissal: RulingState = dismissalQuery.isPending
    ? "pending"
    : dismissalQuery.isError
      ? "failed"
      : dismissalQuery.data

  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>no run for this finding</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  // Three absences and they are three claims: nothing has answered, the answer failed, and the run
  // produced no patch at all. The last one is a measurement that happened and found nothing to
  // window, so it never wears a scope that says a count was taken.
  const diffScope =
    patch.data === undefined
      ? patch.isError
        ? "did not answer"
        : "still asking"
      : patch.data.diff === null
        ? "no diff on this run — the change pane says which nothing that is"
        : "of the patch this run produced; the rest are on the branch named above"

  const status: StatusSegment[] =
    data === undefined
      ? [
          {
            kind: "none",
            why: query.isError
              ? query.error instanceof NotFoundError
                ? "no run for this finding, so there is nothing here to count"
                : "the run did not answer"
              : "asking the checkpointer for this run",
          },
        ]
      : [
          {
            kind: "figure",
            label: "Nodes reached",
            value: `${nodesReached(data.nodes)} of ${BUNDLE_STAGES.length}`,
            scope:
              "the five this bundle names — reached means the graph ran the node, not that it " +
              "produced evidence",
          },
          {
            kind: "figure",
            label: "Diff lines shown",
            value:
              patch.data === undefined || patch.data.diff === null
                ? null
                : diffWindow(patch.data.diff),
            scope: diffScope,
          },
          {
            kind: "note",
            text:
              "Read from the LangGraph checkpointer, a different database from the graph: nothing " +
              "here is dated by an index run or attributed to a binding rung.",
          },
        ]

  return (
    <ScreenFrame
      layout="locked"
      status={status}
      subtitle="One proposed change, what checked it, where it went, and where a human ruling stands."
    >
      {/* Portals into the chassis stats bar, so it draws nothing in place and costs the locked
          column no height. None of the three restates a status-band figure: the band counts the
          bundle's stages and the diff's window, and these three are facts the band does not carry. */}
      <KpiStrip
        items={[
          {
            label: "Files changed",
            value: shortPatchFact(patch, (found) =>
              found.stat === null ? (
                <Absent>no diff on this run</Absent>
              ) : (
                found.stat.files_changed.toLocaleString()
              ),
            ),
            note: "files the patch this run produced touches, counted from the diff itself",
          },
          {
            label: "Human ruling",
            value:
              rulingWord(dismissal) ??
              (dismissal === "failed" ? (
                <Absent>not answered</Absent>
              ) : (
                <Pending />
              )),
            note: "whether anybody has dismissed this finding; dismissing is a command-line action",
            figure: false,
          },
          {
            label: "Generations",
            // Three absences, not one: nothing has answered, the checkpointer holds no run for
            // this finding, and the request failed. A cell that truncates gets the short form of
            // each; the header and the pane beneath carry them in full.
            value:
              data !== undefined ? (
                data.generation_count.toLocaleString()
              ) : query.isError ? (
                query.error instanceof NotFoundError ? (
                  <Absent>no run recorded</Absent>
                ) : (
                  <Absent>not answered</Absent>
                )
              ) : (
                <Pending />
              ),
            note: "runs the checkpointer holds for this finding; this page reads the newest",
          },
        ]}
      />

      {/* One column rather than three children of the content band: the header states what this
          bundle is and the panes hang beneath it, so the gap between them is `section` rather than
          the band's 32px — which at 1366×768 is a fifth of what the panes have to divide. */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section">
        <BundleHeader
          repoId={repoId}
          findingId={findingId}
          data={data}
          facts={facts}
          failure={failure}
        />

        {data === undefined ? (
          <Pane className="rounded-surface border border-line bg-card">
            <PaneScroll className="flex flex-col items-start gap-section p-section">
              {query.isPending && <LoadingState what={`the run for finding ${findingId}`} />}

              {query.isError &&
                (query.error instanceof NotFoundError ? (
                  <>
                    <NotFoundState
                      headline="No remediation run for this finding, so there is no pull request."
                      detail="The API answered, and the checkpointer holds no run under this identifier. Either remediation has not been started for this finding, or it has never been started for any finding on this database. This is an answer about the run, not a failure of the console — a finding can be perfectly real and have no attempt against it yet."
                      identifier={query.error.identifier}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={query.isFetching}
                      onClick={() => void query.refetch()}
                    >
                      {query.isFetching ? "Asking…" : "Check again"}
                    </Button>
                  </>
                ) : (
                  <ErrorState
                    error={query.error}
                    what={`the run for finding ${findingId}`}
                    onRetry={() => void query.refetch()}
                  />
                ))}
            </PaneScroll>
          </Pane>
        ) : (
          /* `min-h-0` on the row and on every pane is what makes the panes scroll instead of the
             column growing. Below `xl` it stacks and each pane still owns its own scroll: a locked
             screen stamps `data-screen="locked"` at every width, so a stack that expected the page
             to scroll would be clipped instead, and clipping is the one outcome that lies. */
          <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section xl:flex-row">
            <ChangePane patch={patch} nodes={data.nodes} />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-section xl:flex-[5]">
              <PanelPane
                label="How this run ended"
                icon={Flag}
                bodyClassName="flex min-w-0 flex-col gap-section p-section"
              >
                <RunOutcome
                  outcome={data.outcome}
                  abandonReason={data.abandon_reason}
                  reportReason={data.report_reason}
                  below={BESIDE}
                  frame="entry"
                />

                <DetailSection
                  heading="Where the human ruling stands"
                  hintLabel="About the standing"
                  hint="Dismissing is a command-line action and this console reads the record. A finding somebody deliberately set aside and one nobody has opened are different facts, and without this a pull request open against each would render as the same screen."
                >
                  <HumanRuling state={dismissal} />
                </DetailSection>
              </PanelPane>

              <PanelPane
                label="The evidence bundle"
                // The bundle holds five stages of evidence against the outcome pane's two blocks,
                // so it takes twice the column. Equal shares gave it an 88px body over 843px of
                // content at 1366×768 — measured, not guessed.
                icon={ListChecks}
                className="flex-[2]"
                hint={
                  <InfoHint label="About the five stages">
                    The five nodes of the remediation graph that answer whether a patch earned a
                    merge, in the graph&#39;s own order. What each node is is described on the
                    solution workflow, which shows all eight; what is here is each one&#39;s verdict.
                  </InfoHint>
                }
                bodyClassName="flex min-w-0 flex-col gap-section p-section"
              >
                <EvidenceBundle nodes={data.nodes} outcome={data.outcome} />
              </PanelPane>
            </div>
          </div>
        )}
      </div>
    </ScreenFrame>
  )
}

/**
 * The change itself, with what checked it pinned beneath.
 *
 * The chain is the pane's foot rather than the last thing in its body, and that is owner decision
 * 47 read structurally: a reader who has to scroll past sixty lines of diff to discover whether
 * anything verified the change is being asked for exactly the faith this console exists to refuse.
 * A foot cannot scroll away from the body above it.
 *
 * **The target travels with the diff** because a diff shown alone is the shape a reader mistakes
 * for a change that has already landed in their repository. It renders outside the diff branch: a
 * branch or a pull request can exist on a checkpoint that no longer carries the patch, and the
 * target is the half that says where the change went.
 */
function ChangePane({
  patch,
  nodes,
}: {
  patch: ReturnType<typeof usePatch>
  nodes: WorkflowNode[]
}) {
  const chain = verificationChain(nodes)

  return (
    <PanelPane
      className="xl:flex-[7]"
      label="The change"
      icon={FileDiff}
      hint={
        <InfoHint label="About the proposed patch">
          The patch the newest run produced, as the checkpointer holds it. Nothing on this screen
          applies it: the console reads the record, and the runner is what writes to a repository.
        </InfoHint>
      }
      actions={
        patch.data === undefined ? undefined : (
          <>
            {patch.data.strategy !== null && <Tag>{patch.data.strategy}</Tag>}
            <PatchStat stat={patch.data.stat} />
          </>
        )
      }
      bodyClassName="flex min-w-0 flex-col gap-section p-section"
      footerClassName="h-auto flex-col items-stretch gap-row px-section py-row text-body text-ink"
      footer={
        <>
          {/* Heading and disclaimer share one line: this foot is pinned, so every row it takes
              is a row the diff above it does not get, and at 1366×768 the pane has 287px total. */}
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-row gap-y-field">
            <h3 className="text-section">What checked it</h3>
            <InfoHint label="About the two checks">
              Two gates the pipeline records: whether the patched tree compiled, and what the
              customer&#39;s own CI said. They are reported separately because averaging them would
              put &ldquo;we could not check&rdquo; on the same axis as &ldquo;we checked and it
              passed&rdquo;, which is the collapse this console exists to replace.
            </InfoHint>
            {/* Stated rather than merely arranged for. A reader cannot see a figure that is not
                there, and the absence of one is the claim this screen most needs to make. */}
            <p className="min-w-0 text-meta text-ink-muted">
              Two checks, reported separately — no combined figure. <code>tsc</code> compiling is
              not the customer&#39;s CI.
            </p>
          </div>
          <div data-testid="verification-chain" className="grid gap-row sm:grid-cols-2">
            {chain.map((check) => (
              <CheckTile key={check.label} check={check} />
            ))}
          </div>
        </>
      }
    >
      {patch.isPending && <Pending />}

      {patch.isError &&
        (patch.error instanceof NotFoundError ? (
          /* One `instanceof` apart from the line below, and collapsing them reports a breakage
             over a true answer about the finding. */
          <p className="text-body">
            <Absent>the checkpointer holds no run for this finding</Absent>
          </p>
        ) : (
          <p className="text-body">
            <Absent>the API did not answer for this patch</Absent>
          </p>
        ))}

      {/* Outside the diff branch: a branch or a pull request can exist on a checkpoint that no
          longer carries the patch, and the target is the half that says where the change went. It
          is inside the answered branch because its own two rows read "this patch was never pushed",
          which is a claim about a payload, not about a request still in flight. */}
      {patch.data !== undefined && <PatchTargetList target={patch.data.target} />}

      {patch.data !== undefined &&
        (patch.data.diff !== null ? (
          <>
            {patch.data.rationale !== null && (
              <p className="max-w-prose text-body text-ink-muted">{patch.data.rationale}</p>
            )}
            <Diff diff={patch.data.diff} />
          </>
        ) : (
          /* Not an empty panel. Which kind of nothing this is comes from the payload, because a
             run that decided against a patch, one that gave up, one whose checkpoint no longer
             carries it and one still working are four facts and one sentence for all four is the
             defect. */
          <p className="max-w-prose text-body text-ink-muted">{patch.data.absent_because}</p>
        ))}
    </PanelPane>
  )
}

