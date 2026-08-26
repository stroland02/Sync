/**
 * What the Findings screen says about the findings it is *not* listing: the table lists open
 * findings only, so without this a finding somebody set aside reads as one nobody has looked at.
 *
 * The fleet scope is stated in every branch that carries a figure. A dismissal records a finding
 * and no repository, and the findings table is rebuilt by every scan -- so a dismissal outlives
 * the row that would have named the workspace, and there is no honest way to narrow this to one.
 *
 * Three answers, not two: in flight, did-not-answer, and a measured zero are different facts.
 */

import { useQuery } from "@tanstack/react-query"

import { fetchDismissalTally } from "@/api/client"
import type { DismissalTally } from "@/api/types"
import type { StatusSegment } from "@/layouts/status-band"

/**
 * The fleet's standing dismissals, counted over the latest ruling per finding.
 *
 * One key, two readers: this note and the Trends chart (`features/dashboards/dismissed-pane.tsx`).
 * The query lives outside both so they cannot ask under different keys and render two different
 * numbers.
 */
export function useDismissalTally() {
  return useQuery({
    queryKey: ["findings", "dismissals"],
    queryFn: ({ signal }) => fetchDismissalTally(signal),
  })
}

/** The three outcomes of that read, and the counted zero, as one status segment. */
export function dismissedNote(query: {
  isPending: boolean
  isError: boolean
  data: DismissalTally | undefined
}): StatusSegment {
  if (query.isPending) {
    return { kind: "note", text: "asking how many findings stand dismissed" }
  }
  if (query.isError || query.data === undefined) {
    return {
      kind: "note",
      text:
        "the dismissal tally did not answer, so this screen cannot say how many findings stand " +
        "set aside",
    }
  }
  if (query.data.total === 0) {
    return {
      kind: "note",
      text:
        "Nobody has dismissed a finding in any repository this deployment holds — a measured " +
        "zero, not a screen that cannot see them.",
    }
  }
  return {
    kind: "note",
    text:
      `${query.data.total.toLocaleString()} findings stand dismissed across every repository ` +
      "this deployment holds, not in this workspace alone. This table lists open findings only.",
  }
}
