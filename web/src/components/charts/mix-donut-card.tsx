/**
 * A mix donut inside a panel, with the two sentences every mix on this console owes.
 *
 * Written once because six screens draw a mix and six copies of the absence rule would be six
 * chances to drop it — `CLAUDE.md` factors at the second use, and this is the second.
 *
 * **The two sentences.** A donut cannot draw a member at zero and cannot draw a member that was
 * never measured, so both have to be said in prose beside it: `absentNote` names what a missing
 * arc means for this particular mix, and it is required rather than optional. A caller with no
 * answer to that question has a chart it should not be drawing.
 *
 * **The empty case is not an empty donut.** A donut of nothing renders as a grey ring that reads
 * as "measured, and all zero". Where the mix has no members the panel says which nothing it is
 * instead, in the caller's words.
 */

import { useCallback } from "react"
import type { ReactNode } from "react"

import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { buildMixDonutOption, type MixSlice } from "@/components/charts/mix-donut-option"
import { MetricPanel } from "@/components/metric-panel"

export function MixDonutCard({
  label,
  hint,
  caption,
  slices,
  unit,
  absentNote,
  emptyHeadline,
  emptyDetail,
}: {
  label: string
  hint?: ReactNode
  /** What the arcs are counted over, and what the centre total is a total of. */
  caption: string
  slices: readonly MixSlice[]
  unit: string
  /** What a member missing from this mix means. Required — see this file's docstring. */
  absentNote: string
  emptyHeadline: string
  emptyDetail: string
}) {
  const build = useCallback(
    (tokens: ChartTokens) => buildMixDonutOption({ slices, unit }, tokens),
    [slices, unit],
  )

  if (slices.length === 0) {
    return (
      <MetricPanel label={label} hint={hint} caption={caption}>
        <p className="max-w-prose text-body text-ink-muted">
          <span className="text-ink">{emptyHeadline}</span> {emptyDetail}
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel label={label} hint={hint} caption={caption}>
      <EChart buildOption={build} ariaLabel={`${label}: ${caption}`} style={{ height: 260 }} />
      <p className="max-w-prose text-meta text-ink-muted">{absentNote}</p>
    </MetricPanel>
  )
}
