/**
 * The three small decisions that give the node sequence its honest dynamics: which ink a node
 * earns, when a node's evidence has ever been stamped, and which entry a reader sees open
 * without having to click for it.
 *
 * Kept apart from `node-sequence.tsx` so the derivation is testable without rendering React —
 * `sequence-dynamics.test.ts` is the RTL-free half of this task's coverage, and
 * `node-sequence.test.tsx` is the structural half.
 */

import type { NodeStanding, WorkflowNode } from "@/api/types"

const INK: Record<NodeStanding, "default" | "receded"> = {
  ran: "default",
  due: "default",
  due_again: "default",
  not_reached_yet: "receded",
  never_reached: "receded",
}

/**
 * A node the run has never visited reads as recessed ink, not as a status colour — there is no
 * judgement to spend a colour on, only the fact that the graph has not been there yet.
 */
export function inkFor(standing: NodeStanding): "default" | "receded" {
  return INK[standing]
}

/**
 * The newest timestamp any node has stamped, or null when nothing has been.
 *
 * `last_seen_at` is a node's most recent checkpoint; `first_seen_at` is its only one until a
 * second checkpoint lands. Falling back per node before taking the maximum across nodes is what
 * keeps a node on its first checkpoint from being read as older than it is.
 */
export function latestEvidenceAt(nodes: WorkflowNode[]): string | null {
  let latest: string | null = null
  for (const node of nodes) {
    const stamp = node.last_seen_at ?? node.first_seen_at ?? null
    if (stamp !== null && (latest === null || stamp > latest)) {
      latest = stamp
    }
  }
  return latest
}

/**
 * Whether a node's evidence disclosure starts open.
 *
 * Only the last node the run actually reached opens by default — the one entry a reviewer
 * arriving at this screen almost certainly came to read. Everything reached earlier is still a
 * click away, not hidden; everything not yet reached has no evidence to show regardless.
 */
export function defaultDisclosed(index: number, lastReachedIndex: number): boolean {
  return index === lastReachedIndex
}
