/**
 * The activity timeline, assembled from what the checkpointer actually holds.
 *
 * Mock screen 07's timeline shows CI events and pull-request events, each carrying its own
 * timestamp. `WorkflowState` carries neither — it has node checkpoints and a run outcome, and
 * nothing else with a time attached. So this module does not reconstruct the mock's timeline;
 * it derives the one timeline our payload can actually support: one entry per node that wrote
 * `first_seen_at`, and one closing entry for the run's outcome.
 *
 * The closing entry's `at` is always null. The payload records no outcome timestamp, and
 * synthesising one from the last node's time would assert a moment the data does not hold —
 * the run could have sat on the customer's CI for hours after that node last wrote a
 * checkpoint. `omittedCount` exists for the same reason in the other direction: a node with no
 * timestamp is not silently dropped, it is a counted absence.
 */

import type { NodeStanding, WorkflowNode, WorkflowState } from "@/api/types"
import { FIELDS } from "@/features/workflows/evidence"

export interface ActivityEntry {
  at: string | null
  name: string
  detail: string | null
}

/**
 * The verb in `<node>.<verb>`. `due` and `due_again` share a word because both describe the
 * graph owing the node a visit, and the distinction is a data question `NodeStanding` itself
 * already answers, not a wording one. `not_reached_yet` and `never_reached` have no timestamp
 * by construction — the checkpointer never wrote `first_seen_at` for a node the run never
 * visited — so this branch is not reachable through `activityEntries`'s own filter. It is
 * written anyway, so a node that somehow carries both a standing and a timestamp the type
 * does not expect still renders something honest rather than throwing.
 */
function verb(standing: NodeStanding): string {
  switch (standing) {
    case "ran":
      return "ran"
    case "due":
    case "due_again":
      return "due"
    case "not_reached_yet":
    case "never_reached":
      return standing
  }
}

/**
 * The first evidence value under this node's own keys whose type is `string`, in the order
 * `FIELDS` declares them — reusing the evidence vocabulary rather than building a second one.
 * A node this file's `FIELDS` does not name, or one whose evidence holds no string, has no
 * detail: `null`, not a guess.
 */
export function primaryDetail(node: WorkflowNode): string | null {
  const fields = FIELDS[node.name] ?? []
  for (const field of fields) {
    const value = node.evidence[field.key]
    // An empty string is "produced, and empty" rather than "not produced", and the two are
    // distinguished where the evidence itself is rendered. As a one-line summary it says nothing,
    // so the search continues rather than surfacing a blank line under a timestamp.
    if (typeof value === "string" && value !== "") return value
  }
  return null
}

/** Nodes whose `first_seen_at` is present and non-null: the ones that produce a row at all. */
function stampedNodes(state: WorkflowState): WorkflowNode[] {
  return state.nodes.filter(
    (node) => node.first_seen_at !== undefined && node.first_seen_at !== null,
  )
}

/** Nodes that wrote no `first_seen_at`, and therefore have no row — counted, not dropped. */
export function omittedCount(state: WorkflowState): number {
  return state.nodes.length - stampedNodes(state).length
}

/**
 * One entry per stamped node, ordered by `first_seen_at` ascending, plus one closing entry for
 * the run's outcome when it has one. The closing entry always sorts last: its `at` is null, and
 * null sorts after every timestamp.
 */
export function activityEntries(state: WorkflowState): ActivityEntry[] {
  const stamped = stampedNodes(state).map((node) => ({
    at: node.first_seen_at as string,
    name: `${node.name}.${verb(node.standing)}`,
    detail: primaryDetail(node),
  }))

  stamped.sort((a, b) => Date.parse(a.at) - Date.parse(b.at))

  const entries: ActivityEntry[] = [...stamped]

  if (state.outcome !== null) {
    entries.push({
      at: null,
      name: `run.${state.outcome}`,
      detail: state.abandon_reason ?? state.report_reason ?? null,
    })
  }

  return entries
}
