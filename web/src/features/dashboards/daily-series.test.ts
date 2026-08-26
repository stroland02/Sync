/**
 * The rule that decides a chart's shape from its payload.
 *
 * `web/CLAUDE.md` states it as prose — *a chart must be able to draw its own data* — and prose is
 * enforced by whoever remembers it. This is the same rule as a derivation, and what is asserted is
 * the boundary that actually bit: one day is not a series, and a set that does not span orders of
 * magnitude does not get a log axis.
 */

import { describe, expect, it } from "vitest"

import type { DayEntry } from "@/components/charts/day-stack-option"
import {
  ORDERS_OF_MAGNITUDE,
  dailySeriesForm,
  memberTotals,
  spansOrdersOfMagnitude,
} from "@/features/dashboards/daily-series"

const day = (name: string, counts: Record<string, number>): DayEntry => ({ day: name, counts })

describe("dailySeriesForm", () => {
  it("calls no day an absence rather than an empty series", () => {
    expect(dailySeriesForm([])).toBe("absent")
  })

  /**
   * The measurement that produced this file: all three Trends series returned exactly one day on
   * 2026-08-26. A stacked column over one category is one total wearing a time axis.
   */
  it("calls one day a composition, not a series", () => {
    expect(dailySeriesForm([day("2026-08-26", { breaking: 36 })])).toBe("composition")
  })

  it("calls two days a series, because two points make a slope", () => {
    expect(
      dailySeriesForm([day("2026-08-25", { breaking: 1 }), day("2026-08-26", { breaking: 2 })]),
    ).toBe("series")
  })
})

describe("memberTotals", () => {
  it("sums each member across every day and ranks the largest first", () => {
    const rows = memberTotals(
      [day("a", { stripe: 2, twilio: 5 }), day("b", { stripe: 9 })],
      ["stripe", "twilio"],
    )

    expect(rows).toEqual([
      { key: "stripe", value: 11 },
      { key: "twilio", value: 5 },
    ])
  })

  /**
   * The opposite of the stacked form's rule, and right for the opposite reason. A band of zeroes
   * puts a name in a legend for a measurement nobody took; a bar of zero is a row with a printed
   * count, which is what `web/CLAUDE.md` prefers wherever a set has meaningful zeros.
   */
  it("keeps a member measured at nought as a row rather than dropping it", () => {
    const rows = memberTotals([day("a", { breaking: 3 })], ["breaking", "info"])

    expect(rows).toEqual([
      { key: "breaking", value: 3 },
      { key: "info", value: 0 },
    ])
  })

  it("breaks ties on the name, so the order does not depend on object insertion", () => {
    const rows = memberTotals([day("a", { zeta: 1, alpha: 1 })], ["zeta", "alpha"])

    expect(rows.map((row) => row.key)).toEqual(["alpha", "zeta"])
  })
})

describe("spansOrdersOfMagnitude", () => {
  /** Today's changes ranking: 18 down to 1. One order, and a linear scale draws it fairly. */
  it("refuses a log scale for a set a linear axis draws fairly", () => {
    expect(spansOrdersOfMagnitude([18, 12, 12, 6, 3, 1])).toBe(false)
  })

  it("asks for a log scale once the smallest member would be a pixel", () => {
    expect(spansOrdersOfMagnitude([8576, 108, 39])).toBe(true)
  })

  it("uses two orders as the boundary, inclusive", () => {
    expect(spansOrdersOfMagnitude([ORDERS_OF_MAGNITUDE, 1])).toBe(true)
    expect(spansOrdersOfMagnitude([ORDERS_OF_MAGNITUDE - 1, 1])).toBe(false)
  })

  /** A single member has no span, and a zero is a measurement rather than a small quantity. */
  it("never asks for a log scale from fewer than two positive members", () => {
    expect(spansOrdersOfMagnitude([9000])).toBe(false)
    expect(spansOrdersOfMagnitude([9000, 0])).toBe(false)
    expect(spansOrdersOfMagnitude([])).toBe(false)
  })
})
