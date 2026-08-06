/**
 * How the run ended, at the top of the screen rather than at the bottom of it.
 *
 * An abandoned run is not an error to tuck away in a corner. `abandon_reason` is queryable
 * data by deliberate design — it is where routing learns which change kinds are not
 * mechanically safe — so a reader who came to find out why Sync gave up should not have to
 * scroll eight nodes to find out.
 *
 * `abandon_reason` renders under `abandoned` and `report_reason` renders under `reported` --
 * routing writes a reason even when the answer is "no patch was warranted", because that is
 * still a decision a reviewer can audit. On `opened` whatever either channel holds describes a
 * superseded attempt.
 */

import type { ReactNode } from "react"

import { WORKFLOW_POLL_MS } from "@/api/queries"
import type { WorkflowOutcome } from "@/api/types"
import { Absent } from "@/components/status"

// A run's disposition — running, abandoned, opened, reported — is identity, not a verdict:
// an abandoned run is not an error, it is data routing learns from. So this panel never
// reaches for the reserved status colour; every outcome gets the same neutral treatment.
function Panel({ headline, children }: { headline: string; children: ReactNode }) {
  return (
    <div className="max-w-prose rounded border border-border p-section">
      <h2 className="text-emphasis">{headline}</h2>
      <div className="mt-row flex flex-col gap-row text-body text-ink-secondary">{children}</div>
    </div>
  )
}

export function RunOutcome({
  outcome,
  abandonReason,
  reportReason,
}: {
  outcome: WorkflowOutcome | null
  abandonReason: string | null
  reportReason: string | null
}) {
  if (outcome === null || outcome === "running") {
    return (
      <Panel headline="This run is still in flight.">
        <p>
          No outcome has been written yet. The sequence below is the last state the
          checkpointer recorded, re-read every {WORKFLOW_POLL_MS / 1000} seconds until the
          run finishes.
        </p>
      </Panel>
    )
  }

  if (outcome === "abandoned") {
    return (
      <Panel headline="Sync abandoned this run.">
        <p>
          The attempt is still below in full, with everything each node produced. An
          abandoned run is kept rather than hidden: the reason is what teaches routing which
          change kinds are not mechanically safe.
        </p>
        <div>
          <p className="furniture text-meta text-ink-muted">Reason it was abandoned</p>
          <p className="mt-field font-mono text-body whitespace-pre-wrap text-foreground">
            {abandonReason === null || abandonReason === "" ? (
              <Absent>the run recorded no reason, which is itself a gap worth chasing</Absent>
            ) : (
              abandonReason
            )}
          </p>
        </div>
      </Panel>
    )
  }

  if (outcome === "opened") {
    return (
      <Panel headline="This run opened a pull request.">
        <p>
          Every node below ran to completion and the patch passed both <code>tsc</code> and
          the customer's own CI. The pull request is under <code>open_pr</code>.
        </p>
      </Panel>
    )
  }

  if (outcome === "reported") {
    return (
      <Panel headline="This run reported rather than patched.">
        <p>
          Routing found no patch was warranted, so nothing was attempted. That is not an
          abandonment: the finding stays open and unremediated, which is the honest state.
        </p>
        <div>
          <p className="furniture text-meta text-ink-muted">Reason it reported</p>
          <p className="mt-field font-mono text-body whitespace-pre-wrap text-foreground">
            {reportReason === null || reportReason === "" ? (
              <Absent>the run reported without recording why</Absent>
            ) : (
              reportReason
            )}
          </p>
        </div>
      </Panel>
    )
  }

  // Every outcome the type knows is handled above, so this is the value the console has
  // never heard of. It is named rather than folded into whichever branch fell through
  // last: an unknown outcome rendered as a known one is a confident wrong verdict, which
  // is the failure this whole view exists to replace.
  return (
    <Panel headline="This run ended in a way the console does not recognise.">
      <p>
        The checkpointer recorded{" "}
        <code className="font-mono">{String(outcome)}</code>, which is not an outcome this
        view was written for. The sequence below is still what the run produced; the
        remediation graph has grown an outcome the console has not caught up with.
      </p>
    </Panel>
  )
}
