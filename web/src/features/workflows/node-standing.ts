/**
 * What a node's standing says, in the one place every screen that renders a node reads.
 *
 * Two screens render the same eight-node payload — the Solution Workflow's sequence and the
 * Pull Request level's evidence bundle — and each used to spell the same status for itself.
 * They disagreed: `current` read as "Running now." on one and as "due now — the graph owes
 * this node a visit" on the other, over a run whose newest checkpoint was a day old. The
 * classification moved to `sync.dashboard.queries`, where pytest can hold it; the wording
 * moved here, where there is one of it.
 *
 * No sentence below claims a node is executing. Nothing in a checkpoint can: a run parked on
 * the customer's CI writes no checkpoint for as long as that takes, by design, and a run that
 * has died writes the same nothing.
 */

import type { NodeStanding } from "@/api/types"

/** The status word beside a node's marker, where a glyph alone would be a legend to memorise. */
export const STANDING_LABEL: Record<NodeStanding, string> = {
  ran: "ran",
  due: "due now — the graph owes this node a visit",
  due_again: "due again — the graph owes this node another visit",
  not_reached_yet: "not started",
  never_reached: "never ran",
}

/**
 * The same fact as a sentence, for the place a screen has no evidence to show instead.
 *
 * `ran` is deliberately absent: a node that ran says what it produced, and a screen with
 * nothing to show for it has something more specific to say than its standing — which fields
 * that screen names, and that this node produced none of them.
 */
export const STANDING_SENTENCE: Record<Exclude<NodeStanding, "ran">, string> = {
  due:
    "Due now — the graph owes this node a visit. That is not a claim that anything is " +
    "running: a run waiting on the customer's CI and a run that has died look the same from " +
    "a checkpoint, and this console does not guess between them.",
  due_again:
    "Due again — this node has already produced evidence and the graph owes it another " +
    "visit, so what it holds is the attempt that was rejected rather than the finished answer.",
  not_reached_yet: "Not reached yet — the run is still in flight and may still get here.",
  never_reached: "Never reached — the run ended before the graph got here.",
}
