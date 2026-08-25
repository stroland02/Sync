/**
 * The live-signals page's derivations: the rate never travels without its denominator, and the
 * hourly series partitions cleanly into the two stacked bands.
 */

import { describe, expect, it } from "vitest"

import { CHART_TOKENS } from "@/components/charts/chart-test-support"
import { TRAFFIC_MEMBERS, bucketLabel, rateSentence, seriesToDays } from "@/features/telemetry/traffic"

describe("rateSentence", () => {
  it("spells the denominator into the same sentence as the percentage", () => {
    expect(rateSentence(80, 240)).toBe("80 of 240 requests (33.3%)")
  })

  it("answers absence for a zero denominator instead of dividing", () => {
    expect(rateSentence(0, 0)).toBe("no statused requests")
  })

  it("renders a measured zero as a figure, never as absence", () => {
    // Zero errors over real requests is a measurement; "no statused requests" is not.
    expect(rateSentence(0, 240)).toBe("0 of 240 requests (0.0%)")
  })
})

describe("seriesToDays", () => {
  it("partitions each bucket's requests into errored and succeeded, nothing drawn twice", () => {
    const days = seriesToDays([{ bucket: "2026-08-19T14:00:00+00:00", requests: 240, errors: 80 }])

    expect(days).toEqual([{ day: "08-19 14:00", counts: { errored: 80, succeeded: 160 } }])
    const total = Object.values(days[0].counts).reduce((a, b) => a + b, 0)
    expect(total).toBe(240)
  })

  it("keeps the date in the label, so two mornings never render as one", () => {
    expect(bucketLabel("2026-08-19T09:00:00+00:00")).toBe("08-19 09:00")
    expect(bucketLabel("2026-08-20T09:00:00+00:00")).toBe("08-20 09:00")
  })

  it("stacks errors on the baseline", () => {
    expect(TRAFFIC_MEMBERS[0]).toBe("errored")
  })
})

/**
 * Every traffic band is painted from a reserved status ink, never a categorical slot.
 *
 * This has now failed twice in opposite directions. First a categorical slot rendered errors
 * green and successes orange. Then `errored` was pinned to serious and `succeeded` was left to
 * slot order, which is also an orange -- so the chart drew two near-identical bands and the
 * legend was the only thing distinguishing a failure from a success.
 *
 * The rule is the fix: a band that means a state takes a status ink. Asserting the two are
 * *different* is what would have caught the second failure, since both were individually valid.
 */
describe("the traffic bands are painted from status inks", () => {
  const tokens = CHART_TOKENS
  const colors: Record<string, string> = {
    errored: tokens.seriousInk,
    succeeded: tokens.goodInk,
  }

  it("pins every member, so none falls through to a categorical slot", () => {
    for (const member of TRAFFIC_MEMBERS) {
      expect(colors[member], `${member} takes a categorical slot`).toBeTruthy()
      expect(tokens.series).not.toContain(colors[member])
    }
  })

  it("gives the two bands different inks, which is what the legend cannot do alone", () => {
    expect(colors.errored).not.toBe(colors.succeeded)
  })
})
