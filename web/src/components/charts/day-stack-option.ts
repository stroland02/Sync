/**
 * A stacked daily series over a closed set of members — the shape both time series on this
 * console need, written once at the second use rather than the third.
 *
 * `findings-over-time-option.ts` was the first: days on the category axis, one stacked band per
 * member, counts only. Integration change volume is the same picture of a different subject, and
 * two copies would drift on the two rules below, which are the ones that make either chart
 * honest rather than the ones that make it render.
 *
 * **A member with no occurrence anywhere gets no band.** A band of zeroes across every day puts a
 * name in the legend for a measurement nobody took.
 *
 * **A gap is a gap.** Days come from the payload, which emits an entry only for a day that has
 * something. Nothing here fills a missing day with a zero, because in both series a day with no
 * row is a day nothing was *recorded* — which may be a day nothing happened or a day nothing ran,
 * and a zero would assert the first.
 *
 * **No legend below two members** (decision 58): with one band the legend names the obvious and
 * costs the bars the space.
 */

import type { EChartsOption } from "echarts-for-react"

import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"

export interface DayEntry {
  readonly day: string
  readonly counts: Record<string, number>
}

export interface DayStackInput {
  readonly days: readonly DayEntry[]
  /**
   * The full member vocabulary, in the order bands should stack. Members that never occur are
   * dropped here rather than by the caller, so every caller gets the rule.
   */
  readonly members: readonly string[]
  /** Distinguishes this chart's stack from another's on the same screen. */
  readonly stackId: string
}

export function buildDayStackOption(input: DayStackInput, tokens: ChartTokens): EChartsOption {
  const days = input.days.map((entry) => entry.day)
  const present = input.members.filter((member) =>
    input.days.some((entry) => (entry.counts[member] ?? 0) > 0),
  )

  return {
    grid: { left: 8, right: 16, top: present.length > 1 ? 32 : 8, bottom: 8, containLabel: true },
    ...(present.length > 1
      ? { legend: { textStyle: { color: tokens.inkSecondary }, top: 0 } }
      : {}),
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const points = params as Array<{ axisValue: string; seriesName: string; value: number }>
        if (points.length === 0) return ""
        const lines = points
          .filter((point) => point.value > 0)
          .map((point) => `${escapeHtml(point.seriesName)}: <strong>${point.value}</strong>`)
        return `${escapeHtml(points[0].axisValue)}<br/>${lines.join("<br/>")}`
      },
    },
    xAxis: {
      type: "category",
      data: days,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.inkMuted },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisLabel: { color: tokens.inkMuted },
    },
    series: present.map((member, index) => ({
      name: member,
      type: "bar" as const,
      stack: input.stackId,
      data: input.days.map((entry) => entry.counts[member] ?? 0),
      itemStyle: { color: tokens.series[index % tokens.series.length] },
    })),
  }
}
