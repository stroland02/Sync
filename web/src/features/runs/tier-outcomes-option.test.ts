/**
 * Dashboard 5's derivation — attempts against outcome, per routing tier.
 *
 * The plan warns this one will be sparse. Sparse is a fact about the corpus and must read as
 * one, so what is asserted here is that the derivation reports its own thinness rather than
 * leaving four rows to look like a broken chart.
 */

import { describe, expect, it } from "vitest"

import type { AbandonmentResponse } from "@/api/types"
import { CHART_TOKENS, expectQuietChart } from "@/components/charts/chart-test-support"
import { buildTierOutcomesOption, tierOutcomes } from "@/features/runs/tier-outcomes-option"

const group = (over: Partial<AbandonmentResponse["groups"][number]> = {}) => ({
  change_kind: "response-field-type-changed",
  tier: 0,
  attempt_count: 0,
  distinct_finding_count: 0,
  abandoned_attempt_count: 0,
  abandoned_distinct_finding_count: 0,
  abandon_reason_codes: {},
  ...over,
})

describe("tierOutcomes", () => {
  it("splits each tier's attempts into abandoned and not, without inventing a third", () => {
    const result = tierOutcomes({
      groups: [group({ tier: 0, attempt_count: 5, abandoned_attempt_count: 2 })],
    })

    expect(result.tiers).toEqual([{ tier: 0, attempts: 5, abandoned: 2, settled: 3 }])
  })

  it("sums a tier across every change kind routed to it", () => {
    const result = tierOutcomes({
      groups: [
        group({ tier: 1, change_kind: "a", attempt_count: 2, abandoned_attempt_count: 1 }),
        group({ tier: 1, change_kind: "b", attempt_count: 3, abandoned_attempt_count: 0 }),
      ],
    })

    expect(result.tiers).toEqual([{ tier: 1, attempts: 5, abandoned: 1, settled: 4 }])
  })

  it("orders by tier, because the tiers are a cascade and not a ranking", () => {
    const result = tierOutcomes({
      groups: [
        group({ tier: 2, attempt_count: 1 }),
        group({ tier: 0, attempt_count: 1 }),
        group({ tier: 1, attempt_count: 1 }),
      ],
    })

    expect(result.tiers.map((row) => row.tier)).toEqual([0, 1, 2])
  })

  /** A tier nothing routed to is absent rather than a zero bar: nothing was attempted there,
   *  which is different from attempts that all settled. */
  it("omits a tier no attempt was routed to", () => {
    const result = tierOutcomes({ groups: [group({ tier: 0, attempt_count: 1 })] })

    expect(result.tiers.map((row) => row.tier)).toEqual([0])
  })

  it("reports the total attempts so the chart can say how thin it is", () => {
    const result = tierOutcomes({
      groups: [
        group({ tier: 0, attempt_count: 3, abandoned_attempt_count: 1 }),
        group({ tier: 1, attempt_count: 1, abandoned_attempt_count: 1 }),
      ],
    })

    expect(result.totalAttempts).toBe(4)
  })

  /** The plan's own warning: four rows must read as a young corpus, not a broken chart. */
  it("flags a corpus too thin to read a cascade from", () => {
    expect(tierOutcomes({ groups: [group({ tier: 0, attempt_count: 4 })] }).isSparse).toBe(true)
    expect(tierOutcomes({ groups: [group({ tier: 0, attempt_count: 60 })] }).isSparse).toBe(false)
  })

  it("counts nothing, and is not sparse but empty, when no attempt exists", () => {
    const result = tierOutcomes({ groups: [] })

    expect(result.tiers).toEqual([])
    expect(result.totalAttempts).toBe(0)
  })
})

describe("buildTierOutcomesOption", () => {
  /**
   * Decision 58's legend clause is conditional, and this is the chart that earns one: settled and
   * abandoned are two series, so without a legend a reader cannot tell which bar is which.
   */
  it("draws no gridlines but keeps a legend, because it has two series (decision 58)", () => {
    const option = buildTierOutcomesOption(
      tierOutcomes({
        groups: [group({ tier: 0, attempt_count: 5, abandoned_attempt_count: 2 })],
      }),
      CHART_TOKENS,
    ) as Record<string, any>

    expect(option.series).toHaveLength(2)
    expectQuietChart(option)
  })
})
