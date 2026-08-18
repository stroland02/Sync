/**
 * The echarts option for the vendor change volume timeline and composition chart.
 *
 * M0-W329 Dashboard 4: Vendor change volume, per vendor, over time.
 * Answers "how often this vendor changes things and what kinds of changes are published".
 */

import type { ChartTokens } from "@/components/charts/echart"
import { escapeHtml } from "@/components/charts/chart-text"
import type { VendorChangeVolumeResponse } from "@/api/types"

export interface VendorChangeVolumeData {
  periods: string[]
  kinds: string[]
  countsByPeriodAndKind: Record<string, Record<string, number>>
  periodTotals: number[]
  totalChanges: number
}

/**
 * The vendor's own answer, shaped for the chart.
 *
 * **This replaces a client-side aggregate and the difference is not cosmetic.** The old
 * `extractVendorChangeVolume` counted `VendorChangeRow[]` -- one page of the changes table -- and
 * the chart printed the result as the vendor's total. It was wrong by an amount that changed when
 * the reader paginated, which is the worst shape a wrong figure takes: plausible on every screen and
 * never right. It is deleted rather than left beside this, per delete-rather-than-deprecate.
 *
 * Nothing is computed here that the payload does not already state. The periods keep the order the
 * API sorted them into, and the kinds are every kind the vendor published rather than every kind a
 * page happened to contain.
 */
export function vendorChangeVolume(
  payload: VendorChangeVolumeResponse
): VendorChangeVolumeData {
  const periods = payload.timeline.map((bucket) => bucket.period)
  const periodTotals = payload.timeline.map((bucket) => bucket.count)
  const countsByPeriodAndKind: Record<string, Record<string, number>> = {}
  for (const bucket of payload.timeline) {
    countsByPeriodAndKind[bucket.period] = { ...bucket.by_kind }
  }
  return {
    periods,
    kinds: Object.keys(payload.by_kind),
    countsByPeriodAndKind,
    periodTotals,
    totalChanges: payload.total_changes,
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
