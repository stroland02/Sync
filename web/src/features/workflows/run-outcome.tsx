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
import { ABSENT } from "@/lib/format"

function Panel({
  headline,
  tone,
  children,
}: {
  headline: string
  tone: "neutral" | "abandoned"
  children: ReactNode
}) {
  return (
    <div
      className={
        tone === "abandoned"
          ? "rounded border-2 border-destructive p-4"
          : "rounded border border-border p-4"
      }
    >
      <h2
        className={
          tone === "abandoned"
            ? "text-base font-semibold text-destructive"
            : "text-base font-semibold"
        }
      >
        {headline}
      </h2>
      <div className="mt-2 flex flex-col gap-2 text-sm text-muted-foreground">{children}</div>
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
      <Panel headline="This run is still in flight." tone="neutral">
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
      <Panel headline="Sync abandoned this run." tone="abandoned">
        <p>
          The attempt is still below in full, with everything each node produced. An
          abandoned run is kept rather than hidden: the reason is what teaches routing which
          change kinds are not mechanically safe.
        </p>
        <div>
          <p className="text-xs tracking-wide uppercase">Reason it was abandoned</p>
          <p className="mt-1 font-mono text-base whitespace-pre-wrap text-foreground">
            {abandonReason === null || abandonReason === "" ? (
              <span className="text-muted-foreground">
                {ABSENT} the run recorded no reason, which is itself a gap worth chasing
              </span>
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
      <Panel headline="This run opened a pull request." tone="neutral">
        <p>
          Every node below ran to completion and the patch passed both <code>tsc</code> and
          the customer's own CI. The pull request is under <code>open_pr</code>.
        </p>
      </Panel>
    )
  }

  if (outcome === "reported") {
    return (
      <Panel headline="This run reported rather than patched." tone="neutral">
        <p>
          Routing found no patch was warranted, so nothing was attempted. That is not an
          abandonment: the finding stays open and unremediated, which is the honest state.
        </p>
        <div>
          <p className="text-xs tracking-wide uppercase">Reason it reported</p>
          <p className="mt-1 font-mono text-base whitespace-pre-wrap text-foreground">
            {reportReason === null || reportReason === "" ? (
              <span className="text-muted-foreground">
                {ABSENT} the run reported without recording why
              </span>
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
    <Panel headline="This run ended in a way the console does not recognise." tone="neutral">
      <p>
        The checkpointer recorded{" "}
        <code className="font-mono">{String(outcome)}</code>, which is not an outcome this
        view was written for. The sequence below is still what the run produced; the
        remediation graph has grown an outcome the console has not caught up with.
      </p>
    </Panel>
  )
}
