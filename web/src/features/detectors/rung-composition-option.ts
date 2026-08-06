/**
 * The echarts option for the rung composition chart, in its own module so a test can read it
 * without importing echarts. The rules encoded here are rendering classification with a wrong
 * answer — what a zero draws, what a share is taken against, which way the categories run — so
 * they are held by `npm test` rather than by looking at the screen once.
 */

import type { ChartTokens } from "@/components/charts/echart"
import {
  INLINE_LABEL_SHARE_FLOOR,
  escapeHtml,
  labelInkFor,
} from "@/components/charts/chart-text"
import type { RungComposition } from "@/features/detectors/rung-series"

/** One bar's thickness, and the row pitch that follows from it. */
const BAR_WIDTH = 18
const ROW_HEIGHT = 34
/** Legend, axis labels and padding, so the container never crops its own x-axis band. */
const CHROME_HEIGHT = 92

export function chartHeight(rows: number): number {
  return rows * ROW_HEIGHT + CHROME_HEIGHT
}

export function buildRungCompositionOption(composition: RungComposition, tokens: ChartTokens) {
  const { detectors, series, rowTotals } = composition
  const label = (index: number) =>
    `${detectors[index]}  ${rowTotals[index].toLocaleString()}`

  return {
    // echarts fades every segment in on first paint unless told not to. A chart that animates
    // says a time passed; nothing here happened over time.
    animation: false,
    grid: { left: 8, right: 24, top: 8, bottom: 52, containLabel: true },
    legend: {
      bottom: 4,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: tokens.inkSecondary, fontSize: 12 },
    },
    tooltip: {
      trigger: "item" as const,
      backgroundColor: tokens.surface,
      borderColor: tokens.grid,
      borderWidth: 1,
      textStyle: { color: tokens.ink },
      // Every string interpolated here is one the graph wrote — a detector name, a rung the
      // transport may have grown — and echarts renders this through `innerHTML`.
      // The count leads and the share follows it: the count is the evidence, the share is
      // only what this chart happens to draw with it.
      formatter: (params: {
        seriesName: string
        dataIndex: number
        data: { count: number }
      }) => {
        const count = params.data.count
        const total = rowTotals[params.dataIndex] ?? 0
        const share = total === 0 ? 0 : Math.round((count / total) * 100)
        return (
          `<strong>${count.toLocaleString()}</strong> finding${count === 1 ? "" : "s"} ` +
          `&middot; ${escapeHtml(params.seriesName)}<br/>` +
          `${share}% of ${escapeHtml(detectors[params.dataIndex] ?? "")}'s ` +
          `${total.toLocaleString()}`
        )
      },
    },
    xAxis: {
      type: "value" as const,
      max: 100,
      axisLine: { lineStyle: { color: tokens.axis } },
      splitLine: { lineStyle: { color: tokens.grid } },
      axisLabel: {
        color: tokens.inkMuted,
        fontSize: 12,
        formatter: (value: number) => `${value}%`,
      },
    },
    yAxis: {
      type: "category" as const,
      // echarts puts category 0 at the bottom of a horizontal bar chart. The payload is
      // alphabetical and the cards below render it in that order top-down, so without this
      // the chart and the table read in opposite directions — measured on the running screen,
      // where `vendor-change` sat first in the chart and last in the cards.
      inverse: true,
      data: detectors.map((_, index) => label(index)),
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.inkMuted, fontSize: 12 },
    },
    series: series.map((entry, index) => {
      const isFirst = index === 0
      const isLast = index === series.length - 1
      const color = tokens.series[entry.slot]

      return {
        name: entry.rung,
        type: "bar" as const,
        stack: "rung",
        barWidth: BAR_WIDTH,
        // The value drawn is this rung's share of that detector's own findings; the count
        // rides along for the label and the tooltip, so no formatter recomputes it.
        //
        // `null` rather than `0`, and this is the absence rule rather than a tidy-up: a zero
        // drawn with a 2px border paints a sliver at the axis origin, which is a value where
        // the data has none. A detector whose total is zero divides by nothing and draws
        // nothing. The legend still carries every series, and `absentRungs` says in words
        // which rungs nothing here rests on.
        data: entry.counts.map((count, index) => {
          const total = rowTotals[index] ?? 0
          if (count === 0 || total === 0) return null
          return { value: (count / total) * 100, count }
        }),
        itemStyle: {
          color,
          // The 2px surface-colour gap `marks-and-anatomy.md` specifies between touching
          // stacked segments, drawn as a border because the segments must still sum to the
          // full bar width.
          borderColor: tokens.surface,
          borderWidth: 2,
          borderRadius: [isFirst ? 4 : 0, isLast ? 4 : 0, isLast ? 4 : 0, isFirst ? 4 : 0],
        },
        label: {
          show: true,
          position: "inside" as const,
          color: labelInkFor(color, tokens.ink, tokens.labelOnLight),
          fontSize: 12,
          // The count, not the percentage: the share is already the bar's width, and a
          // number that restates the length of the thing it sits inside says nothing.
          formatter: (params: { data: { value: number; count: number } | null }) => {
            if (params.data === null) return ""
            if (params.data.value / 100 < INLINE_LABEL_SHARE_FLOOR) return ""
            return params.data.count.toLocaleString()
          },
        },
        emphasis: { focus: "series" as const },
      }
    }),
  }
}


