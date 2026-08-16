/**
 * Where the run's outcome sits among the node entries.
 *
 * The Solution Workflow reads as a narrative rather than as a status list, and the outcome is the
 * entry that closes it — placed at the point the run actually stopped, not pinned to the bottom and
 * not banished to a banner above the sequence. On an abandoned run that is the whole value of the
 * arrangement: the reason lands directly beneath the evidence of the node that failed and directly
 * above the nodes reading "the run ended before the graph got here", so a tail of never-reached
 * entries has a visible cause rather than being four statements of an unexplained absence.
 *
 * `node-standing.ts` owns what a standing says and `sync.dashboard.queries` owns what it is. This
 * file only reads them, and the one judgement it makes is which standings mean the run got there.
 */

import type { NodeStanding, WorkflowNode } from "@/api/types"

/**
 * The standings that mean the run reached this node.
 *
 * `due` and `due_again` are reached: the graph owes the node a visit, which is a statement about
 * where the run *is*, so a live run's in-flight entry belongs under its due node rather than above
 * it. The two never-visited standings are the ones the outcome must sit ahead of.
 *
 * Typed as a full `Record` rather than a `Set` of strings so that a standing added to
 * `NODE_STANDINGS` fails the build here instead of silently defaulting to unreached — which would
 * move the outcome entry up the page with nothing to say it had.
 */
const REACHED: Record<NodeStanding, boolean> = {
  ran: true,
  due: true,
  due_again: true,
  not_reached_yet: false,
  never_reached: false,
}

/**
 * How many node entries precede the closing entry.
 *
 * The last node the run reached, rather than the first one it did not: nothing in the payload
 * forbids a reached node behind an unreached one, and reading the first gap would file the run's
 * outcome above evidence the run really produced. Zero when the run reached nothing, which is where
 * a `reported` run's decision belongs — above the seven entries it explains.
 */
export function closingEntryIndex(nodes: WorkflowNode[]): number {
  for (let index = nodes.length - 1; index >= 0; index -= 1) {
    const node = nodes[index]
    if (node !== undefined && REACHED[node.standing]) return index + 1
  }
  return 0
}
