/**
 * The deck's derivation, which is where a nought would be invented if one ever were.
 *
 * The card renders what this returns. Every `null` here is a different nothing — the answer named
 * no operation, nothing has grouped the vendor's operations onto a product, the coverage answer
 * carries no timestamp — and each is one `?? 0` away from becoming a measured zero on screen. That
 * is exactly the class of rule `web/CLAUDE.md` scopes these tests to: classification and derivation.
 */

import { describe, expect, it } from "vitest"

import type { AdapterRow, IndexCoverageResponse } from "@/api/types"
import { deckRows, matchesSearch, newestIndexed, productsFor } from "@/features/vendors/vendor-deck"

const adapter: AdapterRow = {
  vendor_id: "stripe",
  kind: "coded",
  source: null,
  changes: 12,
  operations: 5,
  last_change_at: "2026-08-16T10:04:00+00:00",
  sources: ["changelog"],
  last_attempt_at: null,
  last_attempt_outcome: null,
  last_attempt_reason: null,
  last_attempt_changes: null,
  attempts: {},
}

function answer(overrides: Partial<IndexCoverageResponse> = {}): IndexCoverageResponse {
  return {
    repo_id: "org/one",
    by_vendor: { stripe: 3, openai: 5 },
    last_indexed: { stripe: "2026-08-20T00:00:00+00:00", openai: "2026-08-24T00:00:00+00:00" },
    total_call_sites: 8,
    by_service: [],
    by_operation: [],
    by_binding_status: {},
    ...overrides,
  }
}

describe("deckRows", () => {
  it("orders busiest first and breaks ties on the id, never on object key order", () => {
    const rows = deckRows(answer({ by_vendor: { stripe: 3, openai: 5, twilio: 3 } }), null)

    expect(rows.map((row) => row.vendorId)).toEqual(["openai", "stripe", "twilio"])
  })

  it("writes the vendor's own spelling beside the id it keys on", () => {
    const rows = deckRows(answer({ by_vendor: { openai: 1 } }), null)

    expect(rows[0].vendorId).toBe("openai")
    expect(rows[0].name).toBe("OpenAI")
  })

  it("counts distinct operations rather than rows", () => {
    // `by_operation` holds one row per (vendor, operation, service), so a operation reached through
    // two products would be counted twice by a length.
    const rows = deckRows(
      answer({
        by_vendor: { stripe: 4 },
        by_operation: [
          operation("stripe", "charges.create"),
          operation("stripe", "charges.create"),
          operation("stripe", "refunds.create"),
        ],
      }),
      null,
    )

    expect(rows[0].operations).toBe(2)
  })

  it("answers null, not nought, when the answer named no operation for the vendor", () => {
    const rows = deckRows(answer({ by_vendor: { stripe: 4 }, by_operation: [] }), null)

    expect(rows[0].operations).toBeNull()
  })

  it("carries no adapter at all when the catalogue did not answer", () => {
    // `null` for the whole inventory is the caller saying nothing was read. An empty array would
    // be the caller saying it was read and named nobody, which is a different claim on every row.
    const rows = deckRows(answer({ by_vendor: { stripe: 4 } }), null)

    expect(rows[0].adapter).toBeNull()
  })

  it("attaches the inventory's row where it has one and leaves the rest null", () => {
    const rows = deckRows(answer({ by_vendor: { stripe: 4, twilio: 1 } }), [adapter])

    expect(rows.find((row) => row.vendorId === "stripe")?.adapter).toEqual(adapter)
    expect(rows.find((row) => row.vendorId === "twilio")?.adapter).toBeNull()
  })

  it("leaves lastIndexed null rather than inventing a time the answer did not carry", () => {
    const rows = deckRows(answer({ by_vendor: { twilio: 1 }, last_indexed: {} }), null)

    expect(rows[0].lastIndexed).toBeNull()
  })
})

describe("matchesSearch", () => {
  const rows = deckRows(answer({ by_vendor: { openai: 1, stripe: 1 } }), null)
  const openai = rows.find((row) => row.vendorId === "openai")!

  it("admits everything on an empty or blank query", () => {
    expect(matchesSearch(openai, "")).toBe(true)
    expect(matchesSearch(openai, "   ")).toBe(true)
  })

  it("matches the id and the written name, because the two spellings differ", () => {
    // A reader typing "OpenAI" is looking for `openai`. Matching only the id would make the box
    // look broken on the exact vendors whose name a rule cannot derive.
    expect(matchesSearch(openai, "openai")).toBe(true)
    expect(matchesSearch(openai, "OpenAI")).toBe(true)
    expect(matchesSearch(openai, "stripe")).toBe(false)
  })
})

describe("newestIndexed", () => {
  it("takes the newest timestamp across the deck", () => {
    const rows = deckRows(answer(), null)

    expect(newestIndexed(rows)).toBe("2026-08-24T00:00:00+00:00")
  })

  it("answers null when no row carries a timestamp, rather than picking one", () => {
    const rows = deckRows(answer({ last_indexed: {} }), null)

    expect(newestIndexed(rows)).toBeNull()
  })
})

describe("productsFor", () => {
  it("names the vendor's products and drops the ungrouped rows", () => {
    const coverage = answer({
      by_vendor: { stripe: 4 },
      by_service: [service("stripe", "payments"), service("stripe", null), service("twilio", "sms")],
    })

    expect(productsFor(coverage, "stripe")).toEqual(["payments"])
  })

  it("answers an empty list for a vendor nothing has grouped, which the drawer names as absence", () => {
    const coverage = answer({ by_vendor: { stripe: 4 }, by_service: [service("stripe", null)] })

    expect(productsFor(coverage, "stripe")).toEqual([])
  })
})

function service(vendor_id: string, service_id: string | null) {
  return { vendor_id, service_id, call_sites: 1, operations: 1, last_indexed: "2026-08-20T00:00:00+00:00" }
}

function operation(vendor_id: string, operation_id: string) {
  return {
    vendor_id,
    service_id: null,
    operation_id,
    call_sites: 1,
    last_indexed: "2026-08-20T00:00:00+00:00",
  }
}
