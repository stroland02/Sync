/**
 * The rules the option carries, which are the ones a reader would have to catch by looking.
 *
 * Three of these are honesty invariants rather than formatting: a zero must draw nothing at the
 * axis origin, a share must be taken against the row it belongs to, and the categories must run
 * the same way as the cards beneath the chart. The fourth is the no-motion rule, which echarts
 * breaks by default rather than on request.
 */

import { describe, expect, it } from "vitest"

import type { ChartTokens } from "@/components/charts/echart"
import { buildRungCompositionOption, chartHeight } from "@/features/detectors/rung-composition-option"
import { rungComposition } from "@/features/detectors/rung-series"
import type { DetectorRow } from "@/api/types"

/**
 * Sentinels rather than the real hexes. What these tests assert is that the option reads the
 * right *token* — slot 3's colour for `observed`, the surface for the gap between segments —
 * and a literal here would assert a value `index.css` owns and this file cannot see. It would
 * also be a colour literal outside `index.css`, which `tests/test_console_design_tokens.py`
 * bans for exactly that reason.
 */
const TOKENS: ChartTokens = {
  ink: "ink",
  inkSecondary: "ink-secondary",
  inkMuted: "ink-muted",
  surface: "surface",
  grid: "chart-grid",
  axis: "chart-axis",
  labelOnLight: "chart-label-on-light",
  goodInk: "good-ink",
  warningInk: "warning-ink",
  outcome: { opened: "o1", retried: "o2", in_flight: "o3", reported: "o4", abandoned: "o5" },
  seriousInk: "serious-ink",
  series: Array.from({ length: 8 }, (_, i) => `series-${i + 1}`),
}

function detector(name: string, by_rung: Record<string, number>): DetectorRow {
  const total = Object.values(by_rung).reduce((sum, n) => sum + n, 0)
  return { detector: name, total, by_rung, by_claim: {}, by_severity: {} }
}

function build(rows: DetectorRow[]) {
  return buildRungCompositionOption(rungComposition(rows), TOKENS)
}

type Point = { value: number; count: number } | null

function pointsFor(option: ReturnType<typeof build>, rung: string): Point[] {
  return option.series.find((s) => s.name === rung)!.data as Point[]
}

describe("buildRungCompositionOption", () => {
  it("draws nothing where a detector has no findings at a rung", () => {
    // The absence rule, at the one place it would break silently: a zero carrying the 2px
    // surface border paints a sliver at the axis origin, which is a mark where there is no
    // value. `null` is the only thing echarts leaves undrawn.
    const option = build([detector("vendor_change", { static: 3 })])

    expect(pointsFor(option, "resolved")).toEqual([null])
    expect(pointsFor(option, "observed")).toEqual([null])
  })

  it("draws nothing at all for a detector carrying nothing, rather than dividing by zero", () => {
    const option = build([detector("silent", {})])

    for (const series of option.series) {
      expect(series.data).toEqual([null])
    }
  })

  it("takes each share against the detector's own total, not the screen's", () => {
    // 10,002 against 3 is the seeded shape. A share taken against the screen's total would
    // render the small detector as a rounding error, which is the whole failure this form
    // exists to avoid.
    const option = build([
      detector("vendor_change", { static: 5001, observed: 5001 }),
      detector("efficiency", { static: 1, observed: 2 }),
    ])

    const staticPoints = pointsFor(option, "static")
    expect(staticPoints[0]!.value).toBeCloseTo(50)
    expect(staticPoints[1]!.value).toBeCloseTo((1 / 3) * 100)
  })

  it("carries the count beside the share, so no formatter recomputes it", () => {
    const option = build([detector("vendor_change", { static: 3, observed: 1 })])

    expect(pointsFor(option, "static")[0]!.count).toBe(3)
  })

  it("runs the categories the same way the cards beneath it do", () => {
    // echarts puts category 0 at the bottom of a horizontal bar chart. Without `inverse` the
    // chart reads bottom-up and the cards read top-down over the same alphabetical list.
    const option = build([detector("a", { static: 1 }), detector("b", { static: 1 })])

    expect(option.yAxis.inverse).toBe(true)
    expect(option.yAxis.data[0]).toContain("a")
  })

  it("prints each detector's own total beside its name, because length no longer carries it", () => {
    const option = build([detector("vendor_change", { static: 10002 })])

    expect(option.yAxis.data[0]).toContain("10,002")
  })

  it("does not animate", () => {
    expect(build([detector("a", { static: 1 })]).animation).toBe(false)
  })

  it("holds the x axis at a full 100, so a bar's width is a share and not a maximum", () => {
    // Without a fixed max, a screen where every detector is 100% static would draw one
    // full-width segment and read identically to one where every detector is 100% of a
    // different rung — the axis would rescale to whatever happened to be on it.
    expect(build([detector("a", { static: 1 })]).xAxis.max).toBe(100)
  })

  it("keeps every rung's colour on its own slot, whatever the payload contains", () => {
    // Colour follows the entity, never its rank. A detector that happens to carry only
    // `observed` must still paint it in slot 3's hue.
    const only = build([detector("observed_drift", { observed: 4 })])
    const mixed = build([detector("a", { static: 1, resolved: 1, observed: 1 })])

    const hue = (option: ReturnType<typeof build>, rung: string) =>
      option.series.find((s) => s.name === rung)!.itemStyle.color

    expect(hue(only, "observed")).toBe(TOKENS.series[2])
    expect(hue(mixed, "observed")).toBe(TOKENS.series[2])
  })

  it("gives every declared rung a legend entry even when nothing carries it", () => {
    const option = build([detector("a", { static: 1 })])

    expect(option.series.map((s) => s.name)).toEqual([
      "static",
      "resolved",
      "observed",
      "unresolved",
      "unattributed",
    ])
  })
})

describe("chartHeight", () => {
  it("grows with the rows, so the axis band is never cropped", () => {
    expect(chartHeight(4)).toBeGreaterThan(chartHeight(2))
  })

  it("reserves room for the legend and axis even with no rows", () => {
    expect(chartHeight(0)).toBeGreaterThan(0)
  })
})
