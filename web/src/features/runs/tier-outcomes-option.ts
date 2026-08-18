/**
 * Dashboard 5: how each routing tier's attempts ended — derivation and echarts option.
 *
 * The cascade is the product's routing argument made visible: tier 0 is a codemod that costs
 * nothing, and the agent tiers above it cost money, so "did the cheap tier actually settle
 * things" is the question this chart exists to answer.
 *
 * **Two outcomes, not three.** `migration_outcome` records whether an attempt was abandoned;
 * `settled` here is simply the attempts that were not. It is deliberately not called *succeeded* —
 * an attempt that was not abandoned reached the end of the pipeline, and whether the pull request
 * it opened was any good is a different measurement this payload does not carry.
 *
 * **The grain is an attempt.** Same rule as dashboard 6 and for the same reason: a finding
 * retried three times is three rows, so nothing here may be labelled a count of findings.
 *
 * **A tier nothing routed to is absent, not a zero bar.** No attempt was made there, which is a
 * different fact from attempts that were all settled, and drawing an empty bar would state the
 * second while meaning the first.
 *
 * **Sparsity is reported rather than hidden.** The plan predicted this chart would be thin and
 * said it must say so. A four-attempt corpus drawn as a confident cascade is the chart lying about
 * how much it knows, so the frame states the total and the derivation flags it.
 *
 * **No rate.** Two counts per tier, side by side. A percentage abandoned per tier is exactly the
 * score this console refuses, and a reader who wants it can divide.
 */

import type { AbandonmentResponse } from "@/api/types"
import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

/**
 * Below this many attempts the shape is noise rather than a cascade.
 *
 * A documented judgement, not a measurement: with a handful of attempts one unlucky abandonment
 * swings a tier's whole appearance, and the honest thing is to say the corpus is young. The
 * number is here so it can be argued with rather than buried in a component.
 */
export const SPARSE_ATTEMPT_FLOOR = 25

export interface TierOutcome {
  readonly tier: number
  readonly attempts: number
  readonly abandoned: number
  /** Attempts that were not abandoned. Not "succeeded" — this payload cannot say that. */
  readonly settled: number
}

export interface TierOutcomes {
  readonly tiers: readonly TierOutcome[]
  readonly totalAttempts: number
  readonly isSparse: boolean
}

export function tierOutcomes(payload: AbandonmentResponse): TierOutcomes {
  const byTier = new Map<number, { attempts: number; abandoned: number }>()

  for (const group of payload.groups) {
    const row = byTier.get(group.tier) ?? { attempts: 0, abandoned: 0 }
    row.attempts += group.attempt_count
    row.abandoned += group.abandoned_attempt_count
    byTier.set(group.tier, row)
  }

  const tiers = [...byTier.entries()]
    .map(([tier, row]) => ({
      tier,
      attempts: row.attempts,
      abandoned: row.abandoned,
      settled: row.attempts - row.abandoned,
    }))
    .sort((a, b) => a.tier - b.tier)

  const totalAttempts = tiers.reduce((sum, row) => sum + row.attempts, 0)

  return {
    tiers,
    totalAttempts,
    isSparse: totalAttempts > 0 && totalAttempts < SPARSE_ATTEMPT_FLOOR,
  }
}

/**
 * Grouped horizontal bars, two per tier.
 *
 * Two colours here rather than one, and that is consistent rather than an exception: settled and
 * abandoned are a run *outcome*, which is one of the three things colour is allowed to carry on
 * this console. They are two categorical slots from the shared series ramp, not a good-to-bad
 * gradient — decision 5 permits the first and refuses the second.
 */
export function buildTierOutcomesOption(
  outcomes: TierOutcomes,
  tokens: ChartTokens,
): EChartsOption {
  const labels = outcomes.tiers.map((row) => `tier ${row.tier}`)

  const series = (name: string, values: number[], color: string) => ({
    name,
    type: "bar" as const,
    data: [...values].reverse(),
    barMaxWidth: 14,
    itemStyle: { color },
    label: { show: true, position: "right" as const, color: tokens.inkMuted },
  })

  return {
    grid: { left: 8, right: 32, top: 28, bottom: 8, containLabel: true },
    legend: { textStyle: { color: tokens.inkSecondary }, top: 0 },
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const { name, seriesName, value } = params as {
          name: string
          seriesName: string
          value: number
        }
        const attempts = value === 1 ? "attempt" : "attempts"
        return `${escapeHtml(name)}<br/>${escapeHtml(seriesName)}: ${value} ${attempts}`
      },
    },
    xAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisLabel: { color: tokens.inkMuted },
    },
    yAxis: {
      type: "category",
      // Reversed so tier 0 reads at the top; echarts draws a category axis bottom-up.
      data: [...labels].reverse(),
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.ink },
    },
    series: [
      series("settled", outcomes.tiers.map((row) => row.settled), tokens.series[0]),
      series("abandoned", outcomes.tiers.map((row) => row.abandoned), tokens.series[1]),
    ],
  }
}
