/**
 * The live-signals page's derivations: the rate never travels without its denominator, and the
 * hourly series partitions cleanly into the two stacked bands.
 */

import { describe, expect, it } from "vitest"

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
