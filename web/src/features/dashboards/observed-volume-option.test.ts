/**
 * Dashboard 7's derivation — observed-call volume per operation.
 *
 * Four things this must not erase, each asserted: telemetry never attached is not a volume of
 * zero, a rung travels with every row, an aggregate over one page is not a total, and an error
 * count is a count rather than a rate.
 *
 * The fixture is typed rather than cast. `CI-W379` is why: a fixture typed `unknown` hand-wrote
 * three fields the payload does not carry, and the suite went green against a shape the API
 * never produces. A cast here would buy the same silence.
 */

import { describe, expect, it } from "vitest"

import type { ObservedCallRow, ObservedTelemetryResponse } from "@/api/types"
import { observedVolumeByOperation } from "@/features/dashboards/observed-volume-option"

const call = (over: Partial<ObservedCallRow> = {}): ObservedCallRow => ({
  repo_id: "org/payments",
  vendor_id: "stripe",
  operation_id: "PostCharges",
  binding_rung: "observed",
  server_address: "api.stripe.com",
  http_method: "post",
  trace_id: "t1",
  url_template: "/v1/charges",
  call_count: 1,
  distinct_targets: 1,
  repeated_calls: 0,
  max_resend_count: 0,
  error_count: 0,
  first_seen: "2026-08-16T10:00:00Z",
  last_seen: "2026-08-16T10:00:00Z",
  ...over,
})

const payload = (
  items: ObservedCallRow[],
  over: Partial<{ attachedAt: string | null; total: number }> = {},
): ObservedTelemetryResponse => ({
  repo_id: "org/payments",
  telemetry_attached_at: over.attachedAt === undefined ? "2026-08-15T00:00:00Z" : over.attachedAt,
  calls: { items, total: over.total ?? items.length, next_offset: null },
  shapes: { items: [], total: 0, next_offset: null },
  error_windows: { items: [], total: 0, next_offset: null },
})

describe("observedVolumeByOperation", () => {
  it("sums call volume per operation across the rows that name it", () => {
    const result = observedVolumeByOperation(
      payload([
        call({ trace_id: "a", call_count: 3 }),
        call({ trace_id: "b", call_count: 4 }),
        call({ trace_id: "c", operation_id: "GetCharges", call_count: 1 }),
      ]),
    )

    expect(result.operations.map((o) => [o.operationId, o.calls])).toEqual([
      ["PostCharges", 7],
      ["GetCharges", 1],
    ])
  })

  it("ranks by volume, breaking ties on the operation id so the order is total", () => {
    const result = observedVolumeByOperation(
      payload([call({ operation_id: "B" }), call({ operation_id: "A", trace_id: "b" })]),
    )

    expect(result.operations.map((o) => o.operationId)).toEqual(["A", "B"])
  })

  /**
   * B157's distinction, and the reason this dashboard was specified with it. Telemetry never
   * attached means nobody looked; it is not a measured volume of nought.
   */
  it("reports never-measured when telemetry was never attached", () => {
    const result = observedVolumeByOperation(payload([], { attachedAt: null }))

    expect(result.telemetryAttached).toBe(false)
    expect(result.operations).toEqual([])
  })

  it("reports a measured nought when telemetry is attached and no traffic arrived", () => {
    const result = observedVolumeByOperation(payload([]))

    expect(result.telemetryAttached).toBe(true)
    expect(result.operations).toEqual([])
  })

  /** A rung is a column, not a join. An operation seen at two rungs reports both. */
  it("carries every rung an operation's rows arrived at, never just the strongest", () => {
    const result = observedVolumeByOperation(
      payload([
        call({ trace_id: "a", binding_rung: "observed" }),
        call({ trace_id: "b", binding_rung: "unresolved" }),
      ]),
    )

    expect(result.operations[0].rungs).toEqual(["observed", "unresolved"])
  })

  /**
   * `calls` is a page. Summing one page and printing it as the operation's volume is a false
   * total, so the derivation reports what it counted over and whether that was everything.
   */
  it("says when it aggregated a page rather than the whole set", () => {
    const partial = observedVolumeByOperation(payload([call()], { total: 90 }))
    expect(partial.countedRows).toBe(1)
    expect(partial.totalRows).toBe(90)
    expect(partial.complete).toBe(false)

    expect(observedVolumeByOperation(payload([call()])).complete).toBe(true)
  })

  it("keeps errors as a count beside the volume, never as a rate", () => {
    const result = observedVolumeByOperation(
      payload([call({ call_count: 10, error_count: 3 })]),
    )

    expect(result.operations[0].errors).toBe(3)
    expect(result.operations[0]).not.toHaveProperty("errorRate")
  })

  it("buckets volume by the day a row was first seen", () => {
    const result = observedVolumeByOperation(
      payload([
        call({ trace_id: "a", call_count: 2, first_seen: "2026-08-16T01:00:00Z" }),
        call({ trace_id: "b", call_count: 5, first_seen: "2026-08-16T22:00:00Z" }),
        call({ trace_id: "c", call_count: 1, first_seen: "2026-08-17T03:00:00Z" }),
      ]),
    )

    expect(result.operations[0].series).toEqual([
      { day: "2026-08-16", calls: 7 },
      { day: "2026-08-17", calls: 1 },
    ])
  })

  /** One point is not a trend. The card must be able to refuse to draw a line. */
  it("marks a series too short to read a direction from", () => {
    const one = observedVolumeByOperation(payload([call()]))
    expect(one.operations[0].drawable).toBe(false)

    const two = observedVolumeByOperation(
      payload([
        call({ trace_id: "a", first_seen: "2026-08-16T01:00:00Z" }),
        call({ trace_id: "b", first_seen: "2026-08-17T01:00:00Z" }),
      ]),
    )
    expect(two.operations[0].drawable).toBe(true)
  })
})
