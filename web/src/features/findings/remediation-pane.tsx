/**
 * The right half of the finding detail: what Sync proposes, what checked it, where the ruling
 * stands, and where to go next.
 *
 * **Deliberately not gated on `useFinding`, and this must not regress.** The checkpointer is a
 * different database from the graph and outlives the re-derived `finding` row, so the run, the
 * patch and the dismissal all still answer on a page whose left half 404s — which is exactly the
 * finding whose run is most worth reading.
 *
 * **Three reads, and each has its own four nothings.** The two that are one `instanceof
 * NotFoundError` apart are the pair that matters: *the checkpointer holds no run for this finding*
 * is an answer about the finding, and *the API did not answer* is a failure of the request.
 * Rendering the second over the first puts a false report of a breakage on top of a true answer.
 *
 * **The verification chain is rendered only when a run exists.** `verificationChain([])` returns
 * two checks reading "This run carries no compile step", which is the wrong nothing for a finding
 * that has no run at all — it describes a run that ran and skipped a step.
 *
 * What the reference asks for here and this refuses: the `4/4 Passing` confidence bar (a composite
 * scalar averaging distinct checks, rejected three times on the record — the two checks are
 * reported separately and the absence of a combined figure is stated), the spinning *Analyzing*
 * chip (a liveness pulse; the standing is a static word from a closed vocabulary), and *Apply Fix
 * & Deploy* / *Escalate to On-Call* / *Dismiss* (nothing reaches a pull request, a deploy or a
 * dismissal from a click here). The one write this console is permitted is the ticket, and it is
 * pinned in the pane's foot where the reference draws its action bar.
 */

import { Link } from "react-router"

import { NotFoundError } from "@/api/errors"
import { usePatch, useDismissal } from "@/api/queries"
import type { WorkflowNode } from "@/api/types"
import { Absent } from "@/components/status"
import { Tag } from "@/components/tag"
import { Button } from "@/components/ui/button"
import { DetailSection } from "@/features/findings/detail-section"
import { HumanRuling, type RulingState } from "@/features/findings/human-ruling"
import { Pending } from "@/features/findings/pending"
import {
  reachedPullRequest,
  remediationBadge,
  type RemediationState,
} from "@/features/findings/remediation"
import { CheckTile } from "@/features/pullrequests/check-tile"
import { Diff, PatchStat, PatchTargetList } from "@/features/pullrequests/patch-parts"
import { verificationChain } from "@/features/pullrequests/verification-chain"
import { pullRequestHref, workflowHref } from "@/lib/hrefs"

/**
 * Which nothing stands in for the chain when there is no run to read it from.
 *
 * Three sentences for three facts, taken from the same classification the standing badge wears, so
 * the badge in the pane header and the sentence in the body can never disagree about why the
 * checks are missing.
 */
function noRunSentence(remediation: RemediationState): string {
  if (remediation.kind === "pending") {
    return "Still asking the checkpointer for this finding's run, so nothing here has been read yet."
  }
  if (remediation.kind === "none") {
    return "The checkpointer holds no run for this finding, so nothing has checked anything. Not a failed check — an absent one."
  }
  return "The API did not answer for this finding's run, so what checked the patch is unknown here rather than missing."
}

export function RemediationPane({
  repoId,
  findingId,
  nodes,
  remediation,
}: {
  repoId: string | undefined
  findingId: string
  /** The newest run's nodes, or `undefined` when there is no run to read. */
  nodes: WorkflowNode[] | undefined
  remediation: RemediationState
}) {
  const patch = usePatch(findingId)
  // Not gated on the finding either: `finding_dismissal` is durable and `finding` is re-derived,
  // so a finding this page 404s on can still carry a standing somebody recorded.
  const dismissalQuery = useDismissal(findingId)
  const dismissal: RulingState = dismissalQuery.isPending
    ? "pending"
    : dismissalQuery.isError
      ? "failed"
      : dismissalQuery.data

  return (
    <>
      <DetailSection
        heading="What Sync proposes to change"
        hintLabel="About the proposed patch"
        hint="The patch the newest run produced, as the checkpointer holds it. Nothing on this screen applies it: the console reads the record, and the runner is what writes to a repository."
      >
        <div className="flex min-w-0 flex-col gap-row rounded-surface border border-line bg-popover p-section">
          {patch.isPending && <Pending />}

          {patch.isError &&
            (patch.error instanceof NotFoundError ? (
              /* The same sentence `describeRemediation`'s `none` branch uses, and explicitly not
                 "the API did not answer": the two are one `instanceof` apart and collapsing them
                 reports a breakage over a true answer about the finding. */
              <p className="text-body">
                <Absent>the checkpointer holds no run for this finding</Absent>
              </p>
            ) : (
              <p className="text-body">
                <Absent>the API did not answer for this patch</Absent>
              </p>
            ))}

          {patch.data !== undefined && (
            <>
              {patch.data.strategy !== null && (
                <span className="self-start">
                  <Tag>{patch.data.strategy}</Tag>
                </span>
              )}

              {patch.data.diff !== null ? (
                <>
                  <p className="max-w-prose text-body text-ink-muted">
                    {patch.data.rationale ?? <Absent>the run recorded no rationale</Absent>}
                  </p>
                  <Diff diff={patch.data.diff} />
                  <PatchStat stat={patch.data.stat} />
                </>
              ) : (
                /* Which nothing comes from the payload: a run that decided against a patch, one
                   that gave up before writing one, one whose checkpoint no longer carries it and
                   one that has not produced it yet are four facts, and the API tells them apart. */
                <p className="max-w-prose text-body text-ink-muted">{patch.data.absent_because}</p>
              )}

              {/* Outside the diff branch: a branch or a pull request can exist with no diff on
                  this checkpoint, and the target is the half that says where the change went. */}
              <PatchTargetList target={patch.data.target} />
            </>
          )}
        </div>
      </DetailSection>

      <DetailSection
        heading="What checked it"
        hintLabel="About the two checks"
        hint="Two gates the pipeline records: whether the patched tree compiled, and what the customer's own CI said. They are reported separately because averaging them would put “we could not check” on the same axis as “we checked and it passed”, which is the collapse this console exists to replace."
      >
        {nodes === undefined ? (
          <p className="max-w-prose text-body text-ink-muted">{noRunSentence(remediation)}</p>
        ) : (
          <>
            <div className="grid gap-row sm:grid-cols-2">
              {verificationChain(nodes).map((check) => (
                <CheckTile key={check.label} check={check} />
              ))}
            </div>
            <p className="text-meta text-ink-muted">
              Two checks, reported separately — no combined figure.
            </p>
          </>
        )}
      </DetailSection>

      <DetailSection
        heading="Where the human ruling stands"
        hintLabel="About the standing"
        hint="Dismissing is a command-line action and this console reads the record. A finding somebody deliberately set aside and one nobody has opened are different facts, and without this row they would render as the same screen."
      >
        <HumanRuling state={dismissal} />
      </DetailSection>

      <DetailSection heading="Where to go next">
        {/* Outside any success branch on purpose. A finding that has been patched or abandoned is
            no longer open, so the left pane 404s for it — and that is exactly the finding whose
            run is most worth reading. */}
        <div className="flex flex-col gap-row">
          <div className="flex flex-col gap-field">
            <Button asChild variant="outline" className="w-full justify-start">
              <Link to={workflowHref(repoId ?? "", findingId)}>Open the solution workflow</Link>
            </Button>
            <p className="text-body text-ink-muted">
              What Sync did about this finding, node by node.
            </p>
          </div>
          {reachedPullRequest(remediation) && (
            <div className="flex flex-col gap-field">
              <Button asChild variant="outline" className="w-full justify-start">
                <Link to={pullRequestHref(repoId ?? "", findingId)}>Pull request</Link>
              </Button>
              <p className="text-body text-ink-muted">
                The evidence bundle behind the patch this run opened.
              </p>
            </div>
          )}
        </div>
      </DetailSection>
    </>
  )
}

/** The standing badge the pane header wears, from the same classification the body reads. */
export function RemediationBadge({ remediation }: { remediation: RemediationState }) {
  const badge = remediationBadge(remediation)
  return <Tag tone={badge.tone}>{badge.label}</Tag>
}
