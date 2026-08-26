/**
 * The change-kind half of the abandonment aggregate, which nothing read until 2026-08-26.
 *
 * The derivation has a wrong answer available to it in two places: the payload is grouped by
 * `(change_kind, tier)`, so a kind routed to two tiers must sum rather than appear twice; and
 * abandoned attempts must stay a second count rather than being folded into a rate.
 */

import { describe, expect, it } from "vitest"

import type { AbandonmentResponse } from "@/api/types"
import { changeKindAttempts } from "@/features/dashboards/change-kind-attempts"

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

describe("changeKindAttempts", () => {
  it("sums a change kind across every tier it was routed to", () => {
    const result = changeKindAttempts({
      groups: [
        group({ change_kind: "field-removed", tier: 0, attempt_count: 2 }),
        group({ change_kind: "field-removed", tier: 2, attempt_count: 3 }),
      ],
    })

    expect(result.rows).toEqual([{ key: "field-removed", value: 5 }])
    expect(result.kindCount).toBe(1)
  })

  it("ranks by attempts, breaking ties on the kind's name", () => {
    const result = changeKindAttempts({
      groups: [
        group({ change_kind: "zeta", attempt_count: 1 }),
        group({ change_kind: "alpha", attempt_count: 1 }),
        group({ change_kind: "busiest", attempt_count: 9 }),
      ],
    })

    expect(result.rows.map((row) => row.key)).toEqual(["busiest", "alpha", "zeta"])
  })

  /** Two counts, never a rate: the abandoned figure sits beside the attempts, not inside them. */
  it("keeps abandoned attempts as a second count against the same kind", () => {
    const result = changeKindAttempts({
      groups: [
        group({ change_kind: "field-removed", tier: 0, attempt_count: 4, abandoned_attempt_count: 1 }),
        group({ change_kind: "field-removed", tier: 2, attempt_count: 2, abandoned_attempt_count: 2 }),
      ],
    })

    expect(result.abandoned["field-removed"]).toBe(3)
    expect(result.totalAttempts).toBe(6)
    expect(result.totalAbandoned).toBe(3)
  })

  /**
   * `kindCount` counts what was seen, never what exists. The corpus declares no closed list of
   * change kinds, so a denominator here would be invented.
   */
  it("reports an unread corpus as no rows rather than as kinds at nought", () => {
    const result = changeKindAttempts({ groups: [] })

    expect(result.rows).toEqual([])
    expect(result.kindCount).toBe(0)
    expect(result.totalAttempts).toBe(0)
  })
})
