/**
 * Adapter coverage by tier — the derivation and echarts option behind dashboard 9.
 *
 * Answers "is the plugin story real", by counting how many vendors each kind of adapter serves.
 *
 * **The plan this implements names the wrong vocabulary, and the payload wins.**
 * `docs/superpowers/plans/2026-08-18-dashboards.md` writes dashboard 9 as
 * `coded / configured / generated`. Nothing emits `configured`: `sync/signals/registry.py`
 * constructs `coded`, `generated` and `mcp`, and `sync/dashboard/adapters.py` adds `unregistered`.
 * `vendor-card.tsx` already carries this exact drift as a documented hazard — a screen inventing a
 * tier is the same defect as a screen inventing a number. The settled authority order puts the
 * payload above a plan, so the registry's vocabulary is what is counted here.
 *
 * **`unregistered` is held apart rather than charted beside the others.** It is not something
 * serving a vendor; it is history keyed by a vendor id nothing serves any more. A bar for it
 * inside a coverage chart would inflate coverage with its own opposite. Dashboard 2 holds
 * `unresolved` and `unattributed` apart for the same reason.
 *
 * **A tier no adapter reports is nought, not absence.** The inventory was read and held none of
 * that kind. This is the one figure on this screen where `0` is the honest answer, and it is the
 * opposite of the adapter table's rule about a count the graph never computed.
 *
 * **No composite.** Four counts over a closed vocabulary, and nothing averages them.
 */

import type { AdapterRow } from "@/api/types"
import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

/** The tiers that actually serve a vendor, in the order the registry builds them. */
export const SERVING_TIERS = ["coded", "generated", "mcp"] as const

export type ServingTier = (typeof SERVING_TIERS)[number]

export interface TierSlice {
  readonly tier: ServingTier
  readonly count: number
}

export interface AdapterCoverage {
  /** One entry per serving tier, always all of them, in registry order. */
  readonly serving: readonly TierSlice[]
  /** Vendors the graph holds history for and no adapter serves. Never counted as coverage. */
  readonly unregistered: number
  readonly totalServing: number
}

export function adapterCoverageByTier(adapters: readonly AdapterRow[]): AdapterCoverage {
  const counts = new Map<ServingTier, number>(SERVING_TIERS.map((tier) => [tier, 0]))
  let unregistered = 0

  for (const adapter of adapters) {
    if (adapter.kind === "unregistered") {
      unregistered += 1
      continue
    }
    counts.set(adapter.kind, (counts.get(adapter.kind) ?? 0) + 1)
  }

  const serving = SERVING_TIERS.map((tier) => ({ tier, count: counts.get(tier) ?? 0 }))

  return {
    serving,
    unregistered,
    totalServing: serving.reduce((sum, slice) => sum + slice.count, 0),
  }
}

/**
 * Horizontal bars, one per serving tier, sharing one categorical colour.
 *
 * One colour rather than a palette across the tiers: on this console colour carries a change kind,
 * a rung or a run outcome, and a tier is none of the three. `coded` is not better than `generated`,
 * so four hues would read as a quality ordering that nothing measured — the argument
 * `vendor-card.tsx` makes for keeping the tier badge monochrome, applied to its chart.
 */
export function buildAdapterCoverageOption(
  coverage: AdapterCoverage,
  tokens: ChartTokens,
): EChartsOption {
  const tiers = coverage.serving.map((slice) => slice.tier)
  const counts = coverage.serving.map((slice) => slice.count)

  return {
    grid: { left: 8, right: 24, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const { name, value } = params as { name: string; value: number }
        const vendors = value === 1 ? "vendor" : "vendors"
        return `${escapeHtml(name)}<br/>${value} ${vendors}`
      },
    },
    xAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisLabel: { color: tokens.inkMuted },
      splitLine: { lineStyle: { color: tokens.grid } },
    },
    yAxis: {
      type: "category",
      // Reversed so the registry's order reads top-to-bottom; echarts draws a category
      // axis from the bottom up.
      data: [...tiers].reverse(),
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.ink },
    },
    series: [
      {
        type: "bar",
        data: [...counts].reverse(),
        barMaxWidth: 18,
        itemStyle: { color: tokens.series[0] },
        label: {
          show: true,
          position: "right",
          color: tokens.inkMuted,
        },
      },
    ],
  }
}
