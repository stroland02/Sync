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
 *
 * **A one-member mix is not a mix, and it does not get a donut.** Measured on the Overview
 * against this repository's own graph: 24 open findings, every one of them at the `static` rung,
 * so the chart drew a single closed ring with a one-line legend. A ring at 100% asserts nothing —
 * it is the same picture for 24 findings as for 24,000 — and it reads as a chart that failed to
 * load rather than as an answer, which is what the owner reported. Below two members the panel
 * states the fact in a sentence and lets `breakdown` carry the numbers, which is strictly more
 * information in less space.
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
  soleMemberNote,
  breakdown,
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
  /**
   * The sentence shown instead of a donut when exactly one member has any count, given the
   * member's name and its total. Required, because a caller with one member has a fact to state
   * and a ring cannot state it.
   */
  soleMemberNote: (member: string, value: number) => ReactNode
  /**
   * The full breakdown, rendered under either form. This is what makes the one-member case
   * informative rather than merely honest: the caller passes every member of the vocabulary,
   * including the ones at nought, and says in `absentNote` what a nought means for this mix.
   */
  breakdown?: ReactNode
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
        {breakdown}
      </MetricPanel>
    )
  }

  // One member is not a mix. A closed ring at 100% is the same picture whatever the count is.
  if (slices.length === 1) {
    return (
      <MetricPanel label={label} hint={hint} caption={caption}>
        <p className="max-w-prose text-body text-ink">
          {soleMemberNote(slices[0].key, slices[0].value)}
        </p>
        {breakdown}
        <p className="max-w-prose text-meta text-ink-muted">{absentNote}</p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel label={label} hint={hint} caption={caption}>
      <EChart buildOption={build} ariaLabel={`${label}: ${caption}`} style={{ height: 260 }} />
      {breakdown}
      <p className="max-w-prose text-meta text-ink-muted">{absentNote}</p>
    </MetricPanel>
  )
}
