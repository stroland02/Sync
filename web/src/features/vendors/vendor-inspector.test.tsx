/**
 * The drawer behind one card, and the two distinctions that moved here from the retired table.
 *
 * `CODED_SOURCE_NOTE` and `FRESHNESS_QUALIFICATION` were asserted on the card until 2026-08-26.
 * Both describe the adapter's record rather than this repository's calls, so they moved into the
 * drawer with the record and their coverage moved with them — the precedent is `M14-W273`: a test
 * whose subject relocates goes with it, and does not evaporate.
 *
 * What is new here is the intake attempt. `last_attempt_at` is the field `last_change_at` says it
 * is not, and a `null` on it is the record's limit rather than a claim that nobody has asked. That
 * is the sentence this file exists to hold.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { AdapterRow } from "@/api/types"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import {
  CATALOGUE_UNANSWERED_NOTE,
  CODED_SOURCE_NOTE,
  FRESHNESS_QUALIFICATION,
  NO_ADAPTER_ROW_NOTE,
} from "@/features/vendors/vendor-card"
import type { DeckRow } from "@/features/vendors/vendor-deck"
import {
  NO_INTAKE_RECORD_NOTE,
  NO_PRODUCTS_NOTE,
  VendorInspector,
} from "@/features/vendors/vendor-inspector"

afterEach(cleanup)

const coded: AdapterRow = {
  vendor_id: "stripe",
  kind: "coded",
  source: null,
  changes: 12,
  operations: 5,
  last_change_at: "2026-08-16T10:04:00+00:00",
  sources: ["changelog", "oasdiff"],
  last_attempt_at: null,
  last_attempt_outcome: null,
  last_attempt_reason: null,
  last_attempt_changes: null,
  attempts: {},
}

function row(overrides: Partial<DeckRow> = {}): DeckRow {
  return {
    vendorId: "stripe",
    name: "Stripe",
    callSites: 3,
    lastIndexed: "2026-08-20T00:00:00+00:00",
    operations: 5,
    adapter: coded,
    ...overrides,
  }
}

function drawer(
  overrides: Partial<DeckRow> = {},
  props: { catalogueAnswered?: boolean; products?: string[] } = {},
) {
  return render(
    <MemoryRouter>
      <VendorInspector
        row={row(overrides)}
        repoId="org/one"
        catalogueAnswered={props.catalogueAnswered ?? true}
        products={props.products ?? ["payments"]}
      />
    </MemoryRouter>,
  )
}

describe("what this codebase calls", () => {
  it("qualifies its figures as static evidence rather than as traffic", () => {
    // The count is what the static index found. Telemetry is on Signals, beside this and never
    // blended into it -- the same line `vendor-exposure-card.tsx` holds for the same reason.
    const { container } = drawer()

    expect(container.textContent).toContain("static index")
    expect(container.textContent).toContain("Signals")
  })

  it("names the products it calls, and says which nothing it is when none are grouped", () => {
    drawer({}, { products: ["payments", "billing"] })
    expect(screen.getByText("payments")).toBeTruthy()
    expect(screen.getByText("billing")).toBeTruthy()

    cleanup()
    const { container } = drawer({}, { products: [] })
    expect(screen.getByText(NO_PRODUCTS_NOTE)).toBeTruthy()
    // Nothing grouped is not nought products, and a bare `0` in that slot would say the second.
    expect(container.textContent).not.toMatch(/Products named\s*0/)
  })
})

describe("what the integration has published", () => {
  it("says a coded adapter is written here rather than marking its source absent", () => {
    // `adapter_inventory` answers `source: null` for a coded adapter because there is no external
    // repository behind it. That is a fact about the adapter, not a gap in the record, and the
    // absence marker would claim the second.
    drawer()
    expect(screen.getByText(CODED_SOURCE_NOTE)).toBeTruthy()

    cleanup()
    drawer({ adapter: { ...coded, kind: "generated", source: "acme/acme-node" } })
    expect(screen.queryByText(CODED_SOURCE_NOTE)).toBeNull()
    expect(screen.getByText("acme/acme-node")).toBeTruthy()
  })

  it("names the newest recorded change as evidence age, never as a freshness measurement", () => {
    // Nothing in Sync records an intake attempt, only its result. A drawer labelling this timestamp
    // "last checked" would be asserting a poll nothing wrote down.
    const { container } = drawer()

    expect(screen.getByText(FRESHNESS_QUALIFICATION)).toBeTruthy()
    expect(container.textContent).not.toMatch(/last checked/i)
    expect(container.textContent).not.toMatch(/up to date/i)
  })

  it("says nothing was received rather than printing zero for an adapter that never delivered", () => {
    drawer({
      adapter: { ...coded, changes: null, operations: null, last_change_at: null, sources: null },
    })

    expect(screen.getAllByText(NEVER_DELIVERED_NOTE).length).toBeGreaterThan(0)
    // The qualification belongs to a timestamp that exists; there is none here to qualify.
    expect(screen.queryByText(FRESHNESS_QUALIFICATION)).toBeNull()
  })

  it("keeps an inventory with no row apart from a catalogue that did not answer", () => {
    drawer({ adapter: null })
    expect(screen.getByText(NO_ADAPTER_ROW_NOTE)).toBeTruthy()

    cleanup()
    drawer({}, { catalogueAnswered: false })
    expect(screen.getByText(CATALOGUE_UNANSWERED_NOTE)).toBeTruthy()
    expect(screen.queryByText(NO_ADAPTER_ROW_NOTE)).toBeNull()
  })
})

describe("the intake attempt", () => {
  it("says the record holds no attempt, not that nobody has asked", () => {
    // The attempt table began when it began. A drawer reading `null` as "never asked" would make
    // a claim about the adapter out of a limit of the record.
    drawer()

    expect(screen.getByText(NO_INTAKE_RECORD_NOTE)).toBeTruthy()
  })

  it("reports a recorded attempt in its own closed vocabulary", () => {
    drawer({
      adapter: {
        ...coded,
        last_attempt_at: "2026-08-25T09:00:00+00:00",
        last_attempt_outcome: "declined",
        last_attempt_reason: "no-spec-published",
      },
    })

    expect(screen.queryByText(NO_INTAKE_RECORD_NOTE)).toBeNull()
    expect(screen.getByText("declined")).toBeTruthy()
    expect(screen.getByText("no-spec-published")).toBeTruthy()
  })
})

describe("where the drawer sends a reader", () => {
  it("carries the integration's record and its call sites, both scoped to this repository", () => {
    drawer({ callSites: 4 })

    expect(
      screen.getByRole("link", { name: /Open the full record/i }).getAttribute("href"),
    ).toBe("/repositories/org%2Fone/vendors/stripe")
    expect(screen.getByRole("link", { name: /call sites/i }).getAttribute("href")).toBe(
      "/repositories/org%2Fone/call-sites?call_sites_vendor=stripe",
    )
  })

  it("asserts no confidence scalar, health figure or score", () => {
    const { container } = drawer()

    const text = container.textContent ?? ""
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toMatch(/confidence|health|score|sev-\d|\d\s*\/\s*10|%/i)
  })
})
