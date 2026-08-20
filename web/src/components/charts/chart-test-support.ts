/**
 * Shared fixtures and the decision-58 assertion, in one place.
 *
 * Imported only by test files, so it never reaches the bundle.
 *
 * **The tokens are sentinels rather than colours.** What a chart suite proves is that a builder
 * reads a token *through*, never what the token's value is â€” `echart.tsx` resolves every chart
 * colour from the stylesheet at render time, so the value that arrives is whatever the theme
 * says. Real colours here would also be colours invented outside `index.css`, which the design
 * token guard refuses and rightly.
 *
 * **Decision 58 lives here once.** Four charts have to obey it and a rule copied into four suites
 * is a rule that will disagree with itself; this is the same argument the register's own grain
 * comment makes about facts written twice.
 */

import { expect } from "vitest"

import type { ChartTokens } from "@/components/charts/echart"

export const CHART_TOKENS: ChartTokens = {
  ink: "token:ink",
  inkSecondary: "token:ink-secondary",
  inkMuted: "token:ink-muted",
  surface: "token:surface",
  grid: "token:grid",
  axis: "token:axis",
  labelOnLight: "token:label-on-light",
  goodInk: "token:good-ink",
  warningInk: "token:warning-ink",
  seriousInk: "token:serious-ink",
  series: Array.from({ length: 8 }, (_, i) => `token:series-${i + 1}`),
}

/**
 * Decision 58: a quiet baseline and tick labels, no gridlines, and no legend unless there is more
 * than one series.
 *
 * The legend clause is conditional rather than absolute, so this takes the series count and
 * checks the right direction â€” a one-series chart with a legend names the obvious, and a
 * multi-series chart without one leaves the reader to guess which band is which.
 */
export function expectQuietChart(option: Record<string, any>): void {
  const axes = [option.xAxis, option.yAxis].filter(Boolean)

  for (const axis of axes) {
    // `show: false` is a hidden axis, which cannot draw a gridline either way.
    if (axis.show === false) continue
    // echarts defaults `splitLine.show` to true, so a `splitLine` present and merely styled still
    // draws gridlines. The first version of this assertion read `splitLine?.show ?? false` and
    // passed against every chart while all four were still drawing them -- a check that could not
    // fail. Absent, or explicitly off, and nothing else counts.
    expect(axis.splitLine === undefined || axis.splitLine.show === false).toBe(true)
    // The baseline stays: quiet is not absent, and an axis with no line leaves the ticks floating.
    expect(axis.axisLine).toBeDefined()
    expect(axis.axisLabel).toBeDefined()
  }

  const seriesCount = Array.isArray(option.series) ? option.series.length : 0
  if (seriesCount > 1) {
    expect(option.legend).toBeDefined()
  } else {
    expect(option.legend).toBeUndefined()
  }
}
