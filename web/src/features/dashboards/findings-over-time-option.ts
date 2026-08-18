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
 * **Every band is legible without its colour.** The tooltip names the severity beside its count
 * and the legend prints the word, so a reader who cannot separate two hues still reads the chart.
 *
 * **Days are the days that have rows.** A gap stays a gap: this is a category axis over the days
 * the payload carried, not a continuous date axis that would draw an implied zero for a day
 * nothing was recorded. Nothing here records that DETECT ran, so an invented zero would claim a
 * measurement nobody took.
 */

import type { FindingsOverTimeResponse } from "@/api/types"
import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

export function buildFindingsOverTimeOption(
  payload: FindingsOverTimeResponse,
  tokens: ChartTokens,
): EChartsOption {
  const days = payload.days.map((entry) => entry.day)

  // Only severities that actually occur get a band. A band of zeroes across every day would put
  // a name in the legend for a measurement nobody took.
  const present = payload.severities.filter((severity) =>
    payload.days.some((entry) => (entry.counts[severity] ?? 0) > 0),
  )

  return {
    grid: { left: 8, right: 16, top: 32, bottom: 8, containLabel: true },
    legend: { textStyle: { color: tokens.inkSecondary }, top: 0 },
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
      splitLine: { lineStyle: { color: tokens.grid } },
    },
    series: present.map((severity, index) => ({
      name: severity,
      type: "bar" as const,
      stack: "findings",
      data: payload.days.map((entry) => entry.counts[severity] ?? 0),
      itemStyle: { color: tokens.series[index % tokens.series.length] },
    })),
  }
}
