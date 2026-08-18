/**
 * Dashboard 6's derivation — what the abandon-reason distribution counts.
 *
 * Three things this must not erase, each asserted: the grain is an attempt and not a finding, a
 * null code is a row from before the column existed rather than the vocabulary's `unclassified`,
 * and a vocabulary member nobody hit is a measured nought.
 */

import { describe, expect, it } from "vitest"

import type { AbandonmentResponse } from "@/api/types"
import type { ChartTokens } from "@/components/charts/echart"
import {
  ABANDON_REASON_CODES,
  abandonReasonDistribution,
  buildAbandonReasonsOption,
} from "@/features/runs/abandon-reasons-option"

const response = (groups: AbandonmentResponse["groups"]): AbandonmentResponse => ({ groups })

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

describe("ABANDON_REASON_CODES", () => {
  it("is the closed vocabulary sync.remediate.state.AbandonReasonCode declares", () => {
    expect(ABANDON_REASON_CODES).toContain("locate_failed")
    expect(ABANDON_REASON_CODES).toContain("static_verify_exhausted")
    expect(ABANDON_REASON_CODES).toContain("unclassified")
    expect(ABANDON_REASON_CODES).toHaveLength(12)
  })
})

describe("abandonReasonDistribution", () => {
  it("sums one reason across every change kind and tier that hit it", () => {
    const result = abandonReasonDistribution(
      response([
        group({ tier: 0, abandon_reason_codes: { locate_failed: 2 } }),
        group({ tier: 1, abandon_reason_codes: { locate_failed: 3, push_failed: 1 } }),
      ])
    )

    expect(result.ranked).toEqual([
      { code: "locate_failed", attempts: 5 },
      { code: "push_failed", attempts: 1 },
    ])
  })

  it("ranks by attempts, breaking ties on the code so the order is total", () => {
    const result = abandonReasonDistribution(
      response([group({ abandon_reason_codes: { push_failed: 1, locate_failed: 1 } })])
    )

    expect(result.ranked.map((slice) => slice.code)).toEqual(["locate_failed", "push_failed"])
  })

  it("totals attempts, never findings", () => {
    const result = abandonReasonDistribution(
      response([group({ abandon_reason_codes: { locate_failed: 4 } })])
    )

    expect(result.totalAbandonedAttempts).toBe(4)
  })

  /**
   * `unclassified` is a real member of the vocabulary — a run reached the fallback. A null code
   * is a row recorded before the column existed. Folding one into the other would invent a
   * routing fact out of a schema migration.
   */
  it("holds rows recorded before the column existed apart from unclassified", () => {
    const result = abandonReasonDistribution(
      response([group({ abandon_reason_codes: { unclassified: 2, null: 3 } })])
    )

    expect(result.ranked).toEqual([{ code: "unclassified", attempts: 2 }])
    expect(result.uncoded).toBe(3)
  })

  it("reports how many vocabulary members no attempt reached", () => {
    const result = abandonReasonDistribution(
      response([group({ abandon_reason_codes: { locate_failed: 1 } })])
    )

    expect(result.unhitCodeCount).toBe(ABANDON_REASON_CODES.length - 1)
  })

  it("counts nothing, and says so, when no attempt has been abandoned", () => {
    const result = abandonReasonDistribution(response([]))

    expect(result.ranked).toEqual([])
    expect(result.totalAbandonedAttempts).toBe(0)
    expect(result.uncoded).toBe(0)
  })

  it("keeps a code the vocabulary does not declare rather than silently discarding it", () => {
    const result = abandonReasonDistribution(
      response([group({ abandon_reason_codes: { something_new: 1 } })])
    )

    expect(result.ranked).toEqual([{ code: "something_new", attempts: 1 }])
    expect(result.undeclaredCodes).toEqual(["something_new"])
  })
})

const TOKENS: ChartTokens = {
  ink: "#fff",
  inkSecondary: "#ddd",
  inkMuted: "#aaa",
  surface: "#000",
  grid: "#222",
  axis: "#333",
  labelOnLight: "#000",
  series: ["#1", "#2", "#3", "#4", "#5", "#6", "#7", "#8"],
}

describe("buildAbandonReasonsOption", () => {
  const option = () =>
    buildAbandonReasonsOption(
      abandonReasonDistribution({
        groups: [
          {
            change_kind: "k",
            tier: 0,
            attempt_count: 0,
            distinct_finding_count: 0,
            abandoned_attempt_count: 0,
            abandoned_distinct_finding_count: 0,
            abandon_reason_codes: { locate_failed: 3, push_failed: 1 },
          },
        ],
      }),
      TOKENS,
    ) as Record<string, any>

  /**
   * The requirement, as a test rather than as a reading of the code: colour carries nothing
   * here. Every bar is named on the category axis and valued by its own label, so the chart
   * survives a reader who cannot separate two hues — and every bar shares one fill, which is
   * what makes it impossible for colour to become load-bearing later without this failing.
   */
  it("names every bar on the axis, so none depends on its colour", () => {
    const built = option()

    expect(built.yAxis.data).toEqual(["push_failed", "locate_failed"])
    expect(built.series[0].label.show).toBe(true)
  })

  it("gives every bar the same fill, so colour cannot become load-bearing", () => {
    const built = option()

    expect(built.series).toHaveLength(1)
    expect(built.series[0].itemStyle.color).toBe(TOKENS.series[0])
  })

  it("plots the real counts rather than any derived share", () => {
    const built = option()

    expect(built.series[0].data).toEqual([1, 3])
  })
})
