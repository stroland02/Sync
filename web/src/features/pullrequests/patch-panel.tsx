/**
 * The change itself, leading the screen, with what verified it directly beneath.
 *
 * Owner decision 47. Before this the pull request screen could show a reviewer every verdict about
 * a patch without ever showing the patch — five evidence stages above a run outcome, and no diff
 * anywhere. `CI-W427`'s route serves it, and this is where it lands.
 *
 * **The verification chain is beneath the diff and not behind anything.** Not a disclosure, not a
 * tooltip, not a second tab. That chain is the entire difference between Sync and a bot that opens
 * pull requests, and a reader who has to click to discover whether anything checked the change is
 * being asked for exactly the faith this console exists to refuse.
 *
 * **The target travels with the diff** because a diff shown alone is the shape a reader mistakes
 * for a change that has already landed in their repository. Where it went is never more than a
 * line away from what it says.
 *
 * The five pieces below the headings live in `patch-parts.tsx` now — the Solution Workflow's
 * remediation pane renders the same diff, and two implementations of one renderer would eventually
 * disagree about how much of a patch a reader is being shown.
 */

import { usePatch } from "@/api/queries"
import type { WorkflowNode } from "@/api/types"
import { Absent } from "@/components/status"
import { Pending } from "@/features/findings/pending"
import {
  Diff,
  PatchStat,
  PatchTargetList,
  VerificationChain,
} from "@/features/pullrequests/patch-parts"

export function PatchPanel({ findingId, nodes }: { findingId: string; nodes: WorkflowNode[] }) {
  const query = usePatch(findingId)

  return (
    <section className="flex min-w-0 flex-col gap-section">
      {/* `text-heading` was a class no stylesheet declares -- the ramp is meta / body / emphasis /
          section / page / figure / display -- so both of these rendered at the inherited size on
          a screen whose other panel headings are `text-section`. */}
      <h2 className="text-section">What Sync changed</h2>

      {query.isPending && <Pending />}

      {query.isError && <Absent>the API did not answer for this patch</Absent>}

      {query.data !== undefined && (
        <>
          <PatchTargetList target={query.data.target} />

          {query.data.diff !== null ? (
            <>
              <Diff diff={query.data.diff} />
              <PatchStat stat={query.data.stat} />
            </>
          ) : (
            /* Not an empty panel. Which kind of nothing this is comes from the payload, because
               a run that decided against a patch, one that gave up and one still working are
               three different facts and one sentence for all three is the defect. */
            <p className="max-w-prose text-body text-ink-muted">{query.data.absent_because}</p>
          )}
        </>
      )}

      <div className="flex min-w-0 flex-col gap-field">
        <h2 className="text-section">What checked it</h2>
        <VerificationChain nodes={nodes} />
      </div>
    </section>
  )
}
