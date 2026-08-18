/**
 * Adapter coverage by tier — test suite for the derivation behind dashboard 9.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation. The option
 * builder's colours and geometry are not asserted here; what it counts is.
 */

import { describe, expect, it } from "vitest"

import type { AdapterRow } from "@/api/types"
import { CHART_TOKENS, expectQuietChart } from "@/components/charts/chart-test-support"
import {
  SERVING_TIERS,
  adapterCoverageByTier,
  buildAdapterCoverageOption,
} from "@/features/settings/adapter-coverage-option"

const row = (vendor_id: string, kind: AdapterRow["kind"]): AdapterRow => ({
  vendor_id,
  kind,
  source: null,
  changes: null,
  operations: null,
  last_change_at: null,
  sources: null,
})

describe("SERVING_TIERS", () => {
  /**
   * The dashboards plan writes this vocabulary as `coded / configured / generated`. No payload
   * carries `configured` and the registry never emits it, so the plan is not followed here — the
   * conflict is recorded in the module docstring and in the register.
   */
  it("is the registry's vocabulary and does not carry the plan's invented tier", () => {
    expect(SERVING_TIERS).toEqual(["coded", "generated", "mcp"])
    expect(SERVING_TIERS).not.toContain("configured")
  })

  /** `unregistered` is history for a vendor nothing serves. Counting it as coverage would inflate it. */
  it("excludes unregistered, which is not something serving a vendor", () => {
    expect(SERVING_TIERS).not.toContain("unregistered")
  })
})

describe("adapterCoverageByTier", () => {
  it("counts adapters into the tier each one reports", () => {
    const coverage = adapterCoverageByTier([
      row("stripe", "coded"),
      row("openai", "coded"),
      row("orb", "generated"),
    ])

    expect(coverage.serving).toEqual([
      { tier: "coded", count: 2 },
      { tier: "generated", count: 1 },
      { tier: "mcp", count: 0 },
    ])
  })

  /**
   * A tier no adapter reports is a measured nought rather than an absence: the inventory was
   * read and it held none. This is the one place on this screen where `0` is the honest answer,
   * and it is the opposite of the adapter table's rule, which is why it is asserted.
   */
  it("reports a tier with no adapters as nought, because the inventory was read", () => {
    const coverage = adapterCoverageByTier([row("stripe", "coded")])

    expect(coverage.serving.find((slice) => slice.tier === "mcp")).toEqual({
      tier: "mcp",
      count: 0,
    })
  })

  it("holds unregistered vendors apart from the serving tiers", () => {
    const coverage = adapterCoverageByTier([
      row("stripe", "coded"),
      row("gone", "unregistered"),
      row("also-gone", "unregistered"),
    ])

    expect(coverage.unregistered).toBe(2)
    expect(coverage.serving.reduce((sum, slice) => sum + slice.count, 0)).toBe(1)
  })

  it("counts nothing when the inventory is empty, and says the total is nought", () => {
    const coverage = adapterCoverageByTier([])

    expect(coverage.totalServing).toBe(0)
    expect(coverage.unregistered).toBe(0)
    expect(coverage.serving.every((slice) => slice.count === 0)).toBe(true)
  })
})

describe("buildAdapterCoverageOption", () => {
  it("draws a quiet chart: no gridlines, and no legend for its single series (decision 58)", () => {
    const option = buildAdapterCoverageOption(
      adapterCoverageByTier([row("stripe", "coded")]),
      CHART_TOKENS,
    ) as Record<string, any>

    expectQuietChart(option)
  })
})
