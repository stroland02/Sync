/**
 * The echarts option for the vendor change volume timeline and composition chart.
 *
 * M0-W329 Dashboard 4: Vendor change volume, per vendor, over time.
 * Answers "how often this vendor changes things and what kinds of changes are published".
 */

import type { ChartTokens } from "@/components/charts/echart"
import { escapeHtml } from "@/components/charts/chart-text"
import type { VendorChangeRow } from "@/api/types"

export interface VendorChangeVolumeData {
  periods: string[]
  kinds: string[]
  countsByPeriodAndKind: Record<string, Record<string, number>>
  periodTotals: number[]
  totalChanges: number
}

export function extractVendorChangeVolume(items: VendorChangeRow[]): VendorChangeVolumeData {
  const periodMap = new Map<string, Record<string, number>>()
  const kindSet = new Set<string>()

  for (const item of items) {
    const kind = item.change_kind || "other"
    kindSet.add(kind)
    let period = "unknown"
    if (item.published_at) {
      const d = new Date(item.published_at)
      if (!isNaN(d.getTime())) {
        period = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`
      }
    }
    const current = periodMap.get(period) ?? {}
    current[kind] = (current[kind] ?? 0) + 1
    periodMap.set(period, current)
  }

  const periods = Array.from(periodMap.keys()).sort()
  const kinds = Array.from(kindSet).sort()
  const countsByPeriodAndKind: Record<string, Record<string, number>> = {}
  const periodTotals: number[] = []

  for (const p of periods) {
    const counts = periodMap.get(p) ?? {}
    countsByPeriodAndKind[p] = counts
    const total = Object.values(counts).reduce((a, b) => a + b, 0)
    periodTotals.push(total)
  }

  return {
    periods,
    kinds,
    countsByPeriodAndKind,
    periodTotals,
    totalChanges: items.length,
  }
}

export function buildVendorChangeVolumeOption(
  data: VendorChangeVolumeData,
  tokens: ChartTokens,
) {
  const { periods, kinds, countsByPeriodAndKind, periodTotals } = data

  return {
    animation: false,
    grid: { left: 8, right: 24, top: 16, bottom: 44, containLabel: true },
    legend: {
      bottom: 0,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: tokens.inkSecondary, fontSize: 12 },
    },
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "shadow" as const },
      backgroundColor: tokens.surface,
      borderColor: tokens.grid,
      borderWidth: 1,
      textStyle: { color: tokens.ink },
      formatter: (params: Array<{ seriesName: string; value: number; dataIndex: number }>) => {
        if (!params.length) return ""
        const idx = params[0].dataIndex
        const period = periods[idx] ?? ""
        const total = periodTotals[idx] ?? 0
        const rows = params
          .filter((p) => p.value > 0)
          .map(
            (p) =>
              `<div><span style="display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px;"></span>` +
              `${escapeHtml(p.seriesName)}: <strong>${p.value}</strong></div>`,
          )
          .join("")
        return (
          `<strong>${escapeHtml(period)}</strong> &middot; ${total} published change${total === 1 ? "" : "s"}<br/>` +
          rows
        )
      },
    },
    xAxis: {
      type: "category" as const,
      data: periods,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.inkMuted, fontSize: 12 },
    },
    yAxis: {
      type: "value" as const,
      minInterval: 1,
      axisLine: { lineStyle: { color: tokens.axis } },
      splitLine: { lineStyle: { color: tokens.grid } },
      axisLabel: { color: tokens.inkMuted, fontSize: 12 },
    },
    series: kinds.map((kind, idx) => {
      const color = tokens.series[idx % tokens.series.length]
      return {
        name: kind,
        type: "bar" as const,
        stack: "total",
        itemStyle: {
          color,
          borderColor: tokens.surface,
          borderWidth: 1,
        },
        data: periods.map((p) => countsByPeriodAndKind[p]?.[kind] ?? 0),
      }
    }),
  }
}
