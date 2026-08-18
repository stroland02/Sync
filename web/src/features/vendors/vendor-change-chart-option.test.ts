import { describe, expect, it } from "vitest"

import {
  vendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"

describe("the volume comes from the vendor's own answer, not from a page", () => {
  /**
   * The defect this closes, found by Lane H and handed over: the chart aggregated
   * `VendorChangeRow[]` -- whichever page of the changes table happened to be loaded -- and printed
   * the result as the vendor's total. It was wrong by an amount that CHANGED WHEN YOU PAGINATED,
   * which is the worst shape a wrong number takes: plausible on every screen and never right.
   *
   * `GET /api/vendors/{vendor_id}/change-volume` counts `all_vendor_changes`, so the total is the
   * vendor's and no page can move it. These tests hold the mapping, and the first one holds the
   * property that was actually broken.
   */
  const payload = {
    vendor_id: "stripe",
    total_changes: 57,
    by_kind: { breaking: 12, deprecation: 45 },
    by_severity: {},
    timeline: [
      { period: "2026-06", count: 20, by_kind: { breaking: 5, deprecation: 15 } },
      { period: "2026-07", count: 37, by_kind: { breaking: 7, deprecation: 30 } },
    ],
    newest_change_at: "2026-07-30T00:00:00Z",
    oldest_change_at: "2026-06-01T00:00:00Z",
  }

  it("reports the vendor's total rather than the number of rows it was handed", () => {
    const data = vendorChangeVolume(payload)

    // 57 across the vendor, while the timeline this render can see sums the same 57. A page of ten
    // rows would once have made this say ten.
    expect(data.totalChanges).toBe(57)
    expect(data.periodTotals.reduce((a, b) => a + b, 0)).toBe(57)
  })

  it("keeps the periods in the order the answer gave them", () => {
    const data = vendorChangeVolume(payload)

    expect(data.periods).toEqual(["2026-06", "2026-07"])
    expect(data.periodTotals).toEqual([20, 37])
  })

  it("names every kind the vendor published, not only those on one page", () => {
    const data = vendorChangeVolume(payload)

    expect([...data.kinds].sort()).toEqual(["breaking", "deprecation"])
    expect(data.countsByPeriodAndKind["2026-07"]).toEqual({ breaking: 7, deprecation: 30 })
  })

  it("answers an empty vendor with a drawable shape rather than a zero-sized one", () => {
    const data = vendorChangeVolume({ ...payload, total_changes: 0, by_kind: {}, timeline: [] })

    expect(data.totalChanges).toBe(0)
    expect(data.periods).toEqual([])
    expect(data.kinds).toEqual([])
  })
})

