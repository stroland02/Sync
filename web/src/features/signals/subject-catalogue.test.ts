/**
 * The vendor role's catalogue is a join, and a join is where a rendering quietly loses a row.
 *
 * `index_coverage` answers with two maps — `by_vendor` and `last_indexed` — keyed the same way by
 * construction. The catalogue draws one card per key of the first and reads the second for that
 * card's timestamp, so the two ways this goes wrong are a vendor that has a count and no timestamp,
 * and an order that depends on whatever order the API happened to serialise its object in. Neither
 * shows up as a broken screen: the first renders a card with a blank where a date belongs, and the
 * second renders every card, in an order that changes between deploys.
 *
 * The absent timestamp is a real branch rather than a defensive one. `index-coverage-card.tsx`
 * records why it guards the same access: the console's dev API process can be older than the code
 * it serves while a deploy is mid-flight, and a stale response must not take the page down.
 */

import { describe, expect, it } from "vitest"

import { attachedVendors } from "@/features/signals/subject-catalogue"

const INDEXED = "2026-08-06T19:35:30.492421+00:00"

describe("attachedVendors", () => {
  it("draws one entry per vendor the index holds a call site for", () => {
    const entries = attachedVendors({
      repo_id: "r",
      by_vendor: { stripe: 3, twilio: 2 },
      last_indexed: { stripe: INDEXED, twilio: INDEXED },
      total_call_sites: 5,
      by_service: [],
    })
    expect(entries.map((entry) => entry.vendorId)).toEqual(["stripe", "twilio"])
    expect(entries.map((entry) => entry.callSites)).toEqual([3, 2])
  })

  it("orders by vendor name rather than by the order the payload arrived in", () => {
    const entries = attachedVendors({
      repo_id: "r",
      by_vendor: { twilio: 2, stripe: 3 },
      last_indexed: {},
      total_call_sites: 5,
      by_service: [],
    })
    expect(entries.map((entry) => entry.vendorId)).toEqual(["stripe", "twilio"])
  })

  it("carries an absent timestamp through rather than dropping the vendor", () => {
    const entries = attachedVendors({
      repo_id: "r",
      by_vendor: { stripe: 3 },
      last_indexed: {},
      total_call_sites: 3,
      by_service: [],
    })
    expect(entries).toHaveLength(1)
    expect(entries[0]?.lastIndexed).toBeUndefined()
  })

  it("has nothing to draw when the index holds no call site", () => {
    expect(
      attachedVendors({
        repo_id: "r",
        by_vendor: {},
        last_indexed: {},
        total_call_sites: 0,
        by_service: [],
      }),
    ).toEqual([])
  })
})
