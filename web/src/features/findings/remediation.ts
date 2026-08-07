/**
 * How remediation stands for one finding, from the one thread the workflow route answers with.
 *
 * `GET /api/workflows/{finding_id}` always returns the **newest** generation and reports
 * `generation_count` beside it, so a finding retried across generations has more runs than this
 * payload describes. `WorkflowState`'s own docstring names `sync.dashboard.fleet.runs` as the query
 * that lists every generation as its own row, which is why `retried` exists here: the screen has to
 * be able to say *newest of N* rather than *the run*, and the number is the only part of the other
 * threads this route can see.
 *
 * The four kinds are four different facts and the screen renders four different sentences.
 * `none` is the checkpointer answering that it holds nothing for this finding — a true answer about
 * remediation, not a failure. `unavailable` is the request not arriving. `pending` is neither yet.
 * Collapsing any two of them would put "no run" on screen for a console that simply could not ask.
 */

import type { WorkflowState } from "@/api/types"

/**
 * How the newest run stands, in one word the rail can render.
 *
 * `in-flight` covers both a null outcome and the literal `running` a checkpoint writes on the first
 * hop, because the two are one fact — nothing terminal has been recorded. `unrecognised` is the
 * remediation graph having grown an outcome this console has not caught up with; it is named rather
 * than folded into whichever branch fell through last, for the reason
 * `features/workflows/run-outcome.tsx` gives at its own final branch.
 */
export type RemediationStanding =
  | "in-flight"
  | "opened"
  | "abandoned"
  | "reported"
  | "unrecognised"

export type RemediationState =
  | { kind: "pending" }
  /** The API answered 404: the checkpointer holds no thread for this finding. */
  | { kind: "none" }
  /** The request did not produce an answer. Which is not the same as there being no run. */
  | { kind: "unavailable" }
  | {
      kind: "run"
      standing: RemediationStanding
      /** The checkpointer's own word, carried verbatim so `unrecognised` can still be quoted. */
      outcome: string | null
      /** How many threads the checkpointer holds for this finding, this one included. */
      generations: number
      retried: boolean
    }

function standingOf(outcome: string | null): RemediationStanding {
  if (outcome === null || outcome === "running") return "in-flight"
  if (outcome === "opened" || outcome === "abandoned" || outcome === "reported") return outcome
  return "unrecognised"
}

/**
 * `data` is read before `failed`, and that ordering is the rule rather than an accident.
 *
 * `useWorkflow` polls while a run is in flight, so a refetch can fail with the last good answer
 * still in `data`. `features/pullrequests/pull-request-page.tsx` spells the same precedence as
 * `data === undefined && query.isError`: a failed re-ask does not unmake the run it was re-asking
 * about.
 *
 * **There is no `pending` input, and leaving it out is the point.** No answer and no failure *is*
 * pending, so a flag saying so would be the same fact carried twice and able to disagree with the
 * two fields it is derived from.
 */
export function describeRemediation({
  data,
  missing,
  failed,
}: {
  data: WorkflowState | undefined
  /** The failure was a 404 — an answer about the finding rather than about the request. */
  missing: boolean
  failed: boolean
}): RemediationState {
  if (data !== undefined) {
    return {
      kind: "run",
      standing: standingOf(data.outcome),
      outcome: data.outcome,
      generations: data.generation_count,
      retried: data.generation_count > 1,
    }
  }
  if (missing) return { kind: "none" }
  if (failed) return { kind: "unavailable" }
  return { kind: "pending" }
}

/**
 * Whether there is a pull request for this finding to link to.
 *
 * Read off the outcome and never off the `open_pr` node's evidence. `isRunTerminal`'s comment in
 * `api/queries.ts` carries the argument one field over: a node reads `done` on a run that went on
 * to be abandoned, so a `pr_url` in its evidence says a pull request existed at some point on some
 * thread rather than that this run ended with one.
 */
export function reachedPullRequest(state: RemediationState): boolean {
  return state.kind === "run" && state.standing === "opened"
}
