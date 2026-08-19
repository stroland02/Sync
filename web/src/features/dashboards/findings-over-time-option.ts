/**
 * Dashboard 1: findings by kind over time — the echarts option.
 *
 * Stacked bars per day, one band per severity, in the vocabulary's own order.
 *
 * **Categorical slots, never a severity ramp.** Decision 5 permits a multi-hue series for
 * findings by kind because those are categories, and refuses a red-to-green ramp because it
 * reintroduces the good-versus-bad axis this console does not draw. Severity is an *ordered*
 * vocabulary, which is what makes the ramp the tempting mistake here specifically: the bands take
 * consecutive slots from the shared categorical series so the order is the vocabulary's, and the
 * hues carry identity rather than a gradient from bad to fine.
 *
 * **The legend appears only when there is more than one band**, per decision 58 — with one
 * severity it would name the obvious.
 *
 * **Every band is legible without its colour.** The tooltip names the severity beside its count
 * and the legend prints the word, so a reader who cannot separate two hues still reads the chart.
 *
 * **Days are the days that have rows.** A gap stays a gap: this is a category axis over the days
 * the payload carried, not a continuous date axis that would draw an implied zero for a day
 * nothing was recorded. Nothing here records that DETECT ran, so an invented zero would claim a
 * measurement nobody took.
 */

import type { FindingsOverTimeResponse } from "@/api/types"
import { buildDayStackOption } from "@/components/charts/day-stack-option"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

export function buildFindingsOverTimeOption(
  payload: FindingsOverTimeResponse,
  tokens: ChartTokens,
): EChartsOption {
  // Delegated to the shared builder at the second use of this shape (`day-stack-option.ts`).
  // Everything that made this chart honest lives there now and is stated once: no band for a
  // severity that never occurs, no zero filled in for a day the payload omits, no legend below
  // two bands. What stays here is what is particular to findings -- the vocabulary and its
  // order, which is the payload's `severities` and not this file's opinion.
  return buildDayStackOption(
    { days: payload.days, members: payload.severities, stackId: "findings" },
    tokens,
  )
}
