/**
 * The run's identity, derived from the checkpointer payload and from nothing else.
 *
 * The persistent fact rail on the Solution Workflow answers *what is this run* while the transcript
 * scrolls past it. Every field here is read off `WorkflowState`; a field the payload does not carry
 * comes back null and the rail renders the absence marker with a sentence saying which nothing it
 * is. Nothing is inferred, averaged or scored.
 *
 * **`checkpointSpanSeconds` is a checkpoint span, not a run duration, and the distinction is the
 * reason it is named that way.** A run parked on the customer's CI writes no checkpoint for as long
 * as that takes; a run that has died writes the same nothing. The distance between the first and
 * last checkpoint is a real measurement over real timestamps. "How long it has run" is not
 * derivable from this payload and is not derived.
 *
 * **`waitingOn` is null on a finished run whatever a node's standing still reads.** `standing` is
 * the checkpointer's own last word about a node, and a terminal outcome means the graph owes
 * nothing further — reporting a due node beside a finished run would read as a live claim, which is
 * exactly the claim this console refuses to make.
 */

import type { WorkflowState } from "@/api/types"

export interface RunIdentity {
  /** The repository the run cloned, when the checkpoint carried one. */
  repoId: string | null
  /** Which remediation tier the decision table routed this change kind to — `locate`'s evidence. */
  tier: string | null
  /** Which remediator produced the edit for the newest attempt — `patch`'s evidence. */
  strategy: string | null
  /** The earliest checkpoint stamp any node wrote. */
  startedAt: string | null
  /** The latest checkpoint stamp any node wrote. */
  lastCheckpointAt: string | null
  /** Distance between those two, in whole seconds. Never a wall-clock run duration. */
  checkpointSpanSeconds: number | null
  /** The node the graph owes a visit, on a run that has not finished. */
  waitingOn: string | null
}

/** A node's evidence value as a non-empty string, or null. Objects and arrays are not scalars. */
function evidenceText(state: WorkflowState, nodeName: string, key: string): string | null {
  const node = state.nodes.find((candidate) => candidate.name === nodeName)
  if (node === undefined) return null
  const value = node.evidence[key]
  if (typeof value === "string") return value === "" ? null : value
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return null
}

/** Every parseable stamp under one key, across every node. */
function stamps(state: WorkflowState, key: "first_seen_at" | "last_seen_at"): string[] {
  return state.nodes
    .map((node) => node[key])
    .filter((value): value is string => typeof value === "string" && !Number.isNaN(Date.parse(value)))
}

function earliest(values: string[]): string | null {
  if (values.length === 0) return null
  return values.reduce((best, value) => (Date.parse(value) < Date.parse(best) ? value : best))
}

function latest(values: string[]): string | null {
  if (values.length === 0) return null
  return values.reduce((best, value) => (Date.parse(value) > Date.parse(best) ? value : best))
}

export function runIdentity(state: WorkflowState): RunIdentity {
  const startedAt = earliest(stamps(state, "first_seen_at"))
  // A node that wrote a first stamp and no last one still bounds the span from below, so both
  // channels feed the upper bound rather than `last_seen_at` alone.
  const lastCheckpointAt = latest([...stamps(state, "last_seen_at"), ...stamps(state, "first_seen_at")])

  const finished =
    state.outcome !== null && state.outcome !== "running"

  const due = finished
    ? undefined
    : state.nodes.find((node) => node.standing === "due" || node.standing === "due_again")

  return {
    repoId: state.repo_id,
    tier: evidenceText(state, "locate", "tier"),
    strategy: evidenceText(state, "patch", "attempt_strategy"),
    startedAt,
    lastCheckpointAt,
    checkpointSpanSeconds:
      startedAt === null || lastCheckpointAt === null
        ? null
        : Math.max(0, Math.round((Date.parse(lastCheckpointAt) - Date.parse(startedAt)) / 1000)),
    waitingOn: due?.name ?? null,
  }
}

/**
 * A duration as an operator would say it, in two units at most.
 *
 * Coarse on purpose past a minute: the reader is deciding whether this run is quick, slow, or has
 * been sitting, and a figure to the second past an hour asks them to do arithmetic for nothing.
 */
export function formatSpan(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}
