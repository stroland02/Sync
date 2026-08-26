/**
 * The two judgements the vendor record screen makes about its own payload.
 *
 * Both are the kind of rule `CLAUDE.md` says to encode where it fails: one decides which *nothing*
 * a traffic figure is, the other decides which chart form the payload can actually draw. Written
 * as derivations rather than as rendering assertions, so they are testable without a DOM and
 * cannot be satisfied by a class name.
 */

import { describe, expect, it } from "vitest"

import type { VendorChangeVolumeResponse, VendorOperationExposure } from "@/api/types"
import { publishingForm, trafficSummary } from "@/features/vendors/vendor-record"

function operation(
  operationId: string,
  observed: boolean | null,
  callSites = 1,
): VendorOperationExposure {
  return {
    operation_id: operationId,
    call_site_count: callSites,
    repository_count: 1,
    binding_rung: "static",
    observed,
  }
}

function volume(over: Partial<VendorChangeVolumeResponse>): VendorChangeVolumeResponse {
  return {
    vendor_id: "stripe",
    total_changes: 0,
    by_kind: {},
    by_severity: {},
    timeline: [],
    newest_change_at: null,
    oldest_change_at: null,
    ...over,
  }
}

describe("trafficSummary: three answers, and two of them are not a number", () => {
  it("counts confirmed against the whole operation set, so the denominator is on screen", () => {
    const summary = trafficSummary(
      [operation("PostPaymentIntents", true), operation("GetInvoices", false)],
      "2026-08-26T11:00:00+00:00",
    )

    expect(summary).toEqual({ kind: "counted", confirmed: 1, total: 2 })
  })

  it("refuses to count when any operation was never measured, and says telemetry is not attached", () => {
    const summary = trafficSummary(
      [operation("PostPaymentIntents", true), operation("GetInvoices", null)],
      null,
    )

    expect(summary.kind).toBe("never-measured")
    // Never "0 of 2": a null `observed` is nobody having looked, and folding it into a
    // confirmed-count would report a measurement nobody took.
    expect(summary.kind === "never-measured" && summary.why).toMatch(/no telemetry is attached/i)
  })

  it("names the other reason a null arrives — a question asked across repositories", () => {
    const summary = trafficSummary(
      [operation("GetInvoices", null)],
      "2026-08-26T11:00:00+00:00",
    )

    expect(summary.kind).toBe("never-measured")
    expect(summary.kind === "never-measured" && summary.why).toMatch(/repositor/i)
  })

  it("separates an empty operation set from a measured zero", () => {
    const summary = trafficSummary([], "2026-08-26T11:00:00+00:00")

    expect(summary.kind).toBe("no-operations")
  })

  it("counts a measured zero as a zero, because it was measured", () => {
    const summary = trafficSummary([operation("GetInvoices", false)], "2026-08-26T11:00:00+00:00")

    expect(summary).toEqual({ kind: "counted", confirmed: 0, total: 1 })
  })
})

describe("publishingForm: the chart form comes from the payload, never from the question", () => {
  it("draws the timeline only when there are at least two periods to compare", () => {
    expect(
      publishingForm(
        volume({
          total_changes: 5,
          timeline: [
            { period: "2026-07", count: 2, by_kind: { "endpoint-deprecated": 2 } },
            { period: "2026-08", count: 3, by_kind: { "endpoint-deprecated": 3 } },
          ],
        }),
      ),
    ).toEqual({ kind: "timeline", periods: 2 })
  })

  it("falls to the kind ranking when every change lands in one period", () => {
    // Measured against the seeded corpus: every vendor's changes arrive in one month, so a time
    // axis draws a single stacked column and a ten-member legend beside it.
    expect(
      publishingForm(
        volume({
          total_changes: 12,
          timeline: [{ period: "2026-08", count: 12, by_kind: { "event-type-added": 12 } }],
        }),
      ),
    ).toEqual({ kind: "kinds", period: "2026-08" })
  })

  it("has no period to name when the timeline is empty but changes exist", () => {
    expect(publishingForm(volume({ total_changes: 3 }))).toEqual({ kind: "kinds", period: null })
  })

  it("draws nothing at all for a counted zero, which is a sentence rather than an empty axis", () => {
    expect(publishingForm(volume({ total_changes: 0 }))).toEqual({ kind: "none" })
  })
})
