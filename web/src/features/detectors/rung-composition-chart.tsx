/**
 * What every detector's open findings rest on, as one shape.
 *
 * **The question:** *is any detector on this screen asserting on a different class of evidence
 * from the others — and how much of everything the console currently claims rests on a static
 * read alone?*
 *
 * **Why the cards below cannot answer it.** They already carry every number this chart draws,
 * and they carry them correctly: one card per detector, a `By rung` table on each. But the
 * question is about composition *across* detectors, and the cards make that a reading exercise —
 * open each card, hold five counts in your head, divide each by a total printed somewhere else,
 * and compare the ratios. At the scale a customer repository produces, those are four-digit
 * counts. The shape is the answer here and the counts are the evidence for it, which is the one
 * case `dataviz`'s own form heuristic sends to a stacked bar rather than back to a table.
 *
 * It is horizontal because the categories are detector names — `parameter_deprecation` does not
 * fit under a vertical column — and because rows grow downward without reflowing the axis.
 *
 * **Every bar is full width, and that is a measurement rather than a preference.** On the seeded
 * graph at scale one detector holds 10,002 open findings and the other three hold one, two and
 * three. Encoding volume as length draws three of the four detectors as a sliver a pixel wide,
 * which reads as "these found nothing" — the absence-is-not-zero failure, arriving through the
 * axis instead of through a missing series. So length carries composition, which is the question,
 * and volume is *printed* beside each detector's name instead of encoded. A reader gets both, and
 * neither is inferred from the other.
 *
 * **What it deliberately is not.** No score, no ratio against a maximum, no colour that grades
 * anything: the series palette is identity, and a rung is a class of evidence rather than a
 * position on a good-to-bad scale. `DESIGN.md`'s rule that the provenance rung stays monochrome
 * governs the rung *badge*, which is prose furniture; a categorical fill in a chart is the one
 * place a rung takes a hue, and it takes it as identity, in the fixed slot order, with a legend
 * and a label beside it rather than as the only channel.
 *
 * No animation. `echarts` gives an entry transition by default and M4.5-W143 is auditing the
 * three this console already has; a fourth arriving by default is exactly what that audit is for.
 */

import { useCallback } from "react"

import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import {
  buildRungCompositionOption,
  chartHeight,
} from "@/features/detectors/rung-composition-option"
import type { RungComposition } from "@/features/detectors/rung-series"

export function RungCompositionChart({ composition }: { composition: RungComposition }) {
  const build = useCallback(
    (tokens: ChartTokens) => buildRungCompositionOption(composition, tokens),
    [composition],
  )

  const summary = composition.series
    .filter((entry) => entry.total > 0)
    .map((entry) => `${entry.total} ${entry.rung}`)
    .join(", ")

  return (
    <EChart
      buildOption={build}
      ariaLabel={`Open findings by evidence rung, per detector: ${summary}`}
      style={{ height: chartHeight(composition.detectors.length) }}
    />
  )
}
