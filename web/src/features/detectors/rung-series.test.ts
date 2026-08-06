/**
 * The derivation behind the rung composition chart. Rendering-side classification, so it is
 * tested here rather than in Python: what the payload holds is a tally per detector, and what a
 * stacked bar needs is one series per rung across every detector, in a fixed order, with the
 * gaps filled — none of which is a fact about the graph.
 *
 * Two of these are honesty rules rather than arithmetic. A rung no detector uses must still be a
 * series, or its absence is invisible; and a rung the transport has grown and this console has
 * not must be counted somewhere, or every bar silently understates its own total.
 */

import { describe, expect, it } from "vitest"

import { BINDING_SOURCES } from "@/api/types"
import type { DetectorRow } from "@/api/types"
import { rungComposition } from "@/features/detectors/rung-series"

function detector(name: string, by_rung: Record<string, number>): DetectorRow {
  const total = Object.values(by_rung).reduce((sum, n) => sum + n, 0)
  return { detector: name, total, by_rung, by_claim: {}, by_severity: {} }
}

describe("rungComposition", () => {
  it("returns one series per declared rung even when nothing carries it", () => {
    const composition = rungComposition([detector("vendor_change", { static: 3 })])

    expect(composition.series.map((s) => s.rung)).toEqual([...BINDING_SOURCES])
  })

  it("keeps the declared order whatever order the payload's keys arrive in", () => {
    // Colour follows the entity, never its rank: a tally that happens to list `observed` first
    // must not move `observed` into slot 1 and repaint every other bar in the console.
    const composition = rungComposition([
      detector("observed_drift", { observed: 9, static: 1 }),
    ])

    expect(composition.series.map((s) => s.rung)).toEqual([...BINDING_SOURCES])
    expect(composition.series[0].slot).toBe(0)
  })

  it("fills a detector's missing rung with zero rather than dropping the column", () => {
    const composition = rungComposition([
      detector("vendor_change", { static: 3 }),
      detector("observed_drift", { observed: 2 }),
    ])

    const staticSeries = composition.series.find((s) => s.rung === "static")!
    const observedSeries = composition.series.find((s) => s.rung === "observed")!
    expect(staticSeries.counts).toEqual([3, 0])
    expect(observedSeries.counts).toEqual([0, 2])
  })

  it("aligns every series to the detector order it was given", () => {
    const composition = rungComposition([
      detector("a", { static: 1 }),
      detector("b", { static: 2 }),
      detector("c", { static: 3 }),
    ])

    expect(composition.detectors).toEqual(["a", "b", "c"])
    for (const series of composition.series) {
      expect(series.counts).toHaveLength(3)
    }
  })

  it("names the rungs nothing here rests on, so absence is not read as zero volume", () => {
    const composition = rungComposition([detector("vendor_change", { static: 3 })])

    expect(composition.absentRungs).toEqual([
      "resolved",
      "observed",
      "unresolved",
      "unattributed",
    ])
  })

  it("reports no absent rung when every one of them carries something", () => {
    const composition = rungComposition([
      detector("everything", {
        static: 1,
        resolved: 1,
        observed: 1,
        unresolved: 1,
        unattributed: 1,
      }),
    ])

    expect(composition.absentRungs).toEqual([])
  })

  it("counts a rung this console has never heard of rather than dropping it", () => {
    // The column is text in the graph and the vocabulary is the transport's to grow. A key this
    // console does not know, silently skipped, makes every bar shorter than the detector's own
    // stated total — a chart disagreeing with the number printed beside it.
    const composition = rungComposition([
      detector("vendor_change", { static: 3, "correlated-next-month": 2 }),
    ])

    const folded = composition.series.find((s) => !s.known)!
    expect(folded.counts).toEqual([2])
    expect(composition.unrecognisedRungs).toEqual(["correlated-next-month"])
  })

  it("folds every unrecognised rung into one series rather than inventing a hue per value", () => {
    const composition = rungComposition([
      detector("a", { "from-the-future": 1, "also-new": 2 }),
    ])

    expect(composition.series.filter((s) => !s.known)).toHaveLength(1)
    expect(composition.series.find((s) => !s.known)!.counts).toEqual([3])
    expect(composition.unrecognisedRungs).toEqual(["also-new", "from-the-future"])
  })

  it("adds no unrecognised series when the payload only carries declared rungs", () => {
    const composition = rungComposition([detector("a", { static: 1 })])

    expect(composition.series.every((s) => s.known)).toBe(true)
    expect(composition.unrecognisedRungs).toEqual([])
  })

  it("gives every series a distinct slot, so no two share a colour", () => {
    const composition = rungComposition([detector("a", { static: 1, novel: 1 })])
    const slots = composition.series.map((s) => s.slot)

    expect(new Set(slots).size).toBe(slots.length)
  })

  it("totals what the bars will draw, so the chart can be checked against the payload", () => {
    const composition = rungComposition([
      detector("a", { static: 3, observed: 1 }),
      detector("b", { unattributed: 6, novel: 2 }),
    ])

    expect(composition.total).toBe(12)
  })

  it("carries each detector's own total, which is what the bars are shares of", () => {
    // The chart draws composition, so every bar is full width and volume has to be printed
    // rather than encoded. Measured on the seeded graph: one detector holds 10,002 findings
    // and three hold between one and three, so a length-encoded bar would render three of the
    // four as an invisible sliver and read as "these detectors found nothing".
    const composition = rungComposition([
      detector("vendor_change", { static: 3335, resolved: 3334, observed: 3333 }),
      detector("efficiency", { observed: 2, static: 1 }),
    ])

    expect(composition.rowTotals).toEqual([10002, 3])
  })

  it("reports a zero total for a detector carrying nothing, rather than dividing by it", () => {
    // `detector_accountability` only lists a detector that has raised something, so this is
    // belt and braces — but a share computed against zero is `NaN`, and `NaN` reaches echarts
    // as a bar of unknown length rather than as an error anybody sees.
    const composition = rungComposition([detector("silent", {})])

    expect(composition.rowTotals).toEqual([0])
  })

  it("holds an empty payload without inventing a detector", () => {
    const composition = rungComposition([])

    expect(composition.detectors).toEqual([])
    expect(composition.total).toBe(0)
    expect(composition.series.map((s) => s.rung)).toEqual([...BINDING_SOURCES])
    for (const series of composition.series) {
      expect(series.counts).toEqual([])
    }
  })
})
