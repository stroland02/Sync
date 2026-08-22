/**
 * One band over three sets, and the one way it goes quietly wrong.
 *
 * This level's whole argument is that `telemetry_attached_at` separates *watched and quiet* from
 * *never watched*, and the payload hands back `total: 0` for all three sets in both cases. So the
 * defect is not a crash: it is a status band reading "No observed calls." under a repository
 * nothing ever looked at, which is a measured quiet asserted over traffic nobody measured (B157).
 * `signals-kpis.tsx`, `not-attached-state.tsx` and `roles.ts` all refuse that collapse in their own
 * register; the band is the fourth surface that has to, and the only one with no prose around it to
 * qualify a bare number.
 *
 * The counted nought is held in the same file and in the same breath, because the refusal is only
 * worth anything if it is not simply "never print zero": an attached source that saw nothing must
 * still say so.
 */

import { describe, expect, it } from "vitest"

import type { ObservedTelemetryResponse } from "@/api/types"
import { signalsStatus, type ObservedState } from "@/features/signals/signals-page"

const NOOP = () => {}

const CALLS = { key: "calls", label: "Observed calls", singular: "observed call", plural: "observed calls" } as const
const SHAPES = {
  key: "shapes",
  label: "Response shapes",
  singular: "response shape",
  plural: "response shapes",
} as const

function set(spec: typeof CALLS | typeof SHAPES, offset = 0) {
  return { ...spec, offset, onOffsetChange: NOOP }
}

function answered(
  telemetry_attached_at: string | null,
  totals: { calls?: number; shapes?: number } = {},
): ObservedState {
  const page = (total: number) => ({
    items: Array.from({ length: Math.min(total, 50) }, (_, index) => index),
    total,
    next_offset: total > 50 ? 50 : null,
  })
  const data = {
    repo_id: "org/one",
    telemetry_attached_at,
    calls: page(totals.calls ?? 0),
    shapes: page(totals.shapes ?? 0),
    error_windows: page(0),
    traffic: [],
    unattributed: [],
    series: [],
    totals: {
      requests: 0,
      errors: 0,
      unstatused: 0,
      unattributed_requests: 0,
      operations_observed: 0,
      operations_indexed: 0,
    },
  } as unknown as ObservedTelemetryResponse
  return { kind: "answered", data, fetching: false }
}

function texts(segments: ReturnType<typeof signalsStatus>): string {
  return segments
    .map((segment) => {
      if (segment.kind === "records") return `${segment.label} ${segment.text ?? ""}`
      if (segment.kind === "listing") return `${segment.label} ${segment.text}`
      if (segment.kind === "figure") return `${segment.label} ${segment.value ?? ""} ${segment.scope ?? ""}`
      if (segment.kind === "note") return segment.text
      return segment.why
    })
    .join(" | ")
}

describe("the Signals status band", () => {
  it("says never attached rather than a nought when nothing ever watched", () => {
    const segments = signalsStatus(set(CALLS), answered(null), "org/one")

    expect(texts(segments)).toContain("never attached")
    // The three totals are genuinely `0` in this payload. Printing one here is the collapse the
    // whole level exists to refuse, so the assertion is on the digit rather than on a sentence.
    expect(texts(segments)).not.toContain("0")
    expect(segments.some((segment) => segment.kind === "records" && segment.paging !== undefined)).toBe(
      false,
    )
  })

  it("still prints the counted nought when a source was attached and saw nothing", () => {
    const segments = signalsStatus(set(CALLS), answered("2026-08-16T12:00:00Z"), "org/one")

    expect(texts(segments)).toContain("No observed calls.")
    expect(texts(segments)).not.toContain("never attached")
  })

  it("counts and pages the set the bar selected, not the first one", () => {
    const segments = signalsStatus(
      set(SHAPES, 50),
      answered("2026-08-16T12:00:00Z", { calls: 4, shapes: 120 }),
      "org/one",
    )
    const records = segments.find((segment) => segment.kind === "records")

    expect(records?.kind === "records" && records.label).toBe("Response shapes")
    // The range separator is an en dash the formatter owns; the numbers, their order and the
    // plural are what this test is for.
    expect(records?.kind === "records" && records.text).toMatch(
      /^Showing 51.100 of 120 response shapes\.$/,
    )
    expect(records?.kind === "records" && records.paging?.total).toBe(120)
  })

  it("names which silence a read that has not answered is in", () => {
    expect(texts(signalsStatus(set(CALLS), { kind: "pending" }, "org/one"))).toContain("asking")
    expect(texts(signalsStatus(set(CALLS), { kind: "errored" }, "org/one"))).toContain(
      "did not answer",
    )
    for (const state of [{ kind: "pending" } as const, { kind: "errored" } as const]) {
      expect(texts(signalsStatus(set(CALLS), state, "org/one"))).not.toContain("0")
    }
  })
})
