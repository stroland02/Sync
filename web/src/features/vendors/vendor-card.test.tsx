/**
 * One integration's card: identity, the rung on its figure, what the graph holds, and what it
 * refuses to claim.
 *
 * **Rewritten with the card, 2026-08-26.** The owner ruled the screen cards-only, so this component
 * stopped being a tile beside a table and became the row itself: it took the table's four columns,
 * gained two the table had no room for, and stopped being a link into the vendor's record because
 * it is now the control that opens the drawer. Every distinction the old file asserted is still
 * asserted here — two of them moved to the field they now live on, and two moved to
 * `vendor-inspector.test.tsx` with the facts they describe. Nothing was dropped.
 *
 * The distinctions, each one careless `??` away from being erased:
 *
 * - **The tier vocabulary is the registry's, not a plan's.** `sync/signals/registry.py` emits
 *   `coded`, `generated` and `mcp`; `sync/dashboard/adapters.py` adds `unregistered`. A card that
 *   renders a tier the payload cannot carry is a claim about the deployment nothing computed.
 * - **Never-delivered apart from zero.** `null` is an adapter the graph holds no `vendor_change`
 *   row for; `0` would mean Sync read the specification and had nothing to say.
 * - **Absence apart from zero, on the coverage facts.** Operations reached is `null` where the
 *   answer named none — which the old file asserted on the finding count, a field the deck no
 *   longer carries because every row now has a measured count by construction.
 * - **Nothing-here apart from never-measured, on the adapter itself.** A catalogue that did not
 *   answer, and an inventory that answered and named no adapter, are two more states again.
 * - **The rung qualifies the figure.** The number is statically indexed call sites, and a reader
 *   who takes it for observed traffic has been misled by the rung's absence.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: what the card says and how it derives it. Never a
 * class name, never a snapshot.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { AdapterRow } from "@/api/types"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import {
  ADAPTER_TIERS,
  CATALOGUE_UNANSWERED_NOTE,
  NO_ADAPTER_ROW_NOTE,
  NO_OPERATIONS_NOTE,
  VendorCard,
  adapterTierLabel,
} from "@/features/vendors/vendor-card"
import type { DeckRow } from "@/features/vendors/vendor-deck"

afterEach(cleanup)

const delivered: AdapterRow = {
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

const neverDelivered: AdapterRow = {
  vendor_id: "acme",
  kind: "generated",
  source: "acme/acme-node",
  changes: null,
  operations: null,
  last_change_at: null,
  sources: null,
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
    lastIndexed: null,
    operations: 5,
    adapter: delivered,
    ...overrides,
  }
}

function card(overrides: Partial<DeckRow> = {}, props: { catalogueAnswered?: boolean } = {}) {
  return render(
    <VendorCard
      row={row(overrides)}
      catalogueAnswered={props.catalogueAnswered ?? true}
      totalCallSites={60}
      selected={false}
      onSelect={() => {}}
    />,
  )
}

describe("the integration's mark", () => {
  it("shows a mark beside the name, drawn rather than fetched", () => {
    // M15 Task 5, owner ruling: the neutral generated mark. This asserted an `<img>` from
    // logo.clearbit.com -- a third-party trademark, fetched from the operator's browser, telling
    // that endpoint which integrations a customer watches. The mark is now drawn here.
    card()

    expect(screen.getByTestId("vendor-mark-monogram")).toBeTruthy()
  })

  it("keeps the id on the card rather than letting the mark or the name stand for it", () => {
    // Decision 6 reversed the refusal to render a mark. It did not reverse what the refusal was
    // protecting: the id is what Sync actually holds, and it is what every payload, join and URL
    // keys on. The written name is now the heading, so the id has to be visible in its own right.
    const { container } = card()

    expect(screen.getByRole("heading", { name: "Stripe" })).toBeTruthy()
    expect(screen.getByText("stripe")).toBeTruthy()
    // Nothing is fetched for an integration's logo, from anywhere, and the console draws no mark
    // of its own -- no inline svg, no path.
    expect(container.querySelector("img")).toBeNull()
    expect(container.querySelector("svg")).toBeNull()
    expect(container.querySelector("path")).toBeNull()
  })
})

describe("the figure and its rung", () => {
  it("qualifies the call-site count with the rung that says what was counted", () => {
    // `CLAUDE.md`: the rung travels with every binding and everything derived from one. The number
    // is what the static index found -- not calls, not traffic -- and a reader who reads it as
    // traffic has been misled by the rung's absence rather than by the number.
    const { container } = card({ callSites: 3 })

    expect(screen.getByText("3")).toBeTruthy()
    expect(screen.getByText("static")).toBeTruthy()
    expect(container.textContent).toContain("of 60 call sites indexed here")
  })

  it("puts the denominator on screen rather than drawing a rate", () => {
    // `web/CLAUDE.md`: a count is not a rate, and no percentage renders without its denominator.
    // The bar is decorative; both numbers are in the line above it.
    const { container } = card({ callSites: 3 })

    expect(container.textContent).not.toContain("%")
  })
})

describe("the adapter, and the three ways it can be absent", () => {
  it("renders every tier in the registry's own vocabulary, legible as a word without colour", () => {
    expect(ADAPTER_TIERS.length).toBeGreaterThan(0)

    for (const kind of ADAPTER_TIERS) {
      cleanup()
      card({ adapter: { ...delivered, vendor_id: "acme", kind } })
      // The badge carries the word. Colour, if any ever arrives, is a second channel over this.
      expect(screen.getByText(adapterTierLabel(kind))).toBeTruthy()
      expect(adapterTierLabel(kind)).toContain(kind)
    }
  })

  it("carries no tier the adapter payload cannot emit", () => {
    // `configured` is in the information-architecture plan and in no payload. A vocabulary invented
    // by a screen is the same defect as a number nothing computed, one column over.
    expect(ADAPTER_TIERS).toEqual(["coded", "generated", "mcp", "unregistered"])
  })

  it("says nothing was received rather than printing zero, when an adapter has never delivered", () => {
    const { container } = card({
      vendorId: "acme",
      name: "Acme",
      adapter: neverDelivered,
      callSites: 3,
    })

    expect(screen.getByText(NEVER_DELIVERED_NOTE)).toBeTruthy()
    expect(container.textContent).not.toMatch(/\b0\b/)
  })

  it("prints a confirmed zero as a number, apart from an adapter that never delivered", () => {
    card({ adapter: { ...delivered, changes: 0, operations: 0, last_change_at: null } })

    expect(screen.queryByText(NEVER_DELIVERED_NOTE)).toBeNull()
    expect(screen.getAllByText("0").length).toBeGreaterThan(0)
  })

  it("distinguishes an inventory with no row for this vendor from an adapter that delivered nothing", () => {
    const { container } = card({ vendorId: "twilio", name: "Twilio", adapter: null, callSites: 2 })

    // Said once, in the header. The changes row is not drawn at all without an adapter row to
    // count -- printing the same sentence in both places reads as two facts about two things.
    expect(screen.getAllByText(NO_ADAPTER_ROW_NOTE).length).toBe(1)
    expect(screen.queryByText(NEVER_DELIVERED_NOTE)).toBeNull()
    expect(screen.queryByText("Vendor changes recorded")).toBeNull()
    // The coverage facts are a different query's answer and survive the adapter being unknown.
    expect(container.textContent).toContain("2")
  })

  it("refuses to describe the adapter at all when the catalogue did not answer", () => {
    // Shipped for weeks on the retired table: the map was built from `data?.adapters ?? []`, so an
    // errored catalogue rendered `none` on every row -- a positive claim that these vendors have no
    // adapter, from a query that answered nothing.
    card({}, { catalogueAnswered: false })

    expect(screen.getAllByText(CATALOGUE_UNANSWERED_NOTE).length).toBe(1)
    expect(screen.queryByText(NO_ADAPTER_ROW_NOTE)).toBeNull()
    expect(screen.queryByText(adapterTierLabel("coded"))).toBeNull()
    expect(screen.queryByText("Vendor changes recorded")).toBeNull()
  })
})

describe("the coverage facts say which nothing they are", () => {
  // This is the coverage the retired `callSites: null` case carried -- absence apart from zero on
  // a count. The deck derives a measured count for every row now, so the distinction lives on the
  // field that can genuinely have none.
  it("renders an answer that named no operation as absence rather than nought operations", () => {
    const { container } = card({ operations: null })

    expect(screen.getByText(NO_OPERATIONS_NOTE)).toBeTruthy()
    expect(container.textContent).not.toMatch(/\b0\b/)
  })

  it("prints a counted operation as a number", () => {
    card({ operations: 4 })

    expect(screen.queryByText(NO_OPERATIONS_NOTE)).toBeNull()
    expect(screen.getByText("4")).toBeTruthy()
  })

  it("carries no product count at all, because that count is a constant on this payload", () => {
    // Only a vendor adapter can group operations onto a product and almost none does, so the count
    // reads `1` on twenty-seven of the thirty integrations in the corpus. A constant in a data slot
    // is furniture pretending to be data -- the same argument that kept the rung chip off the
    // overview map. The drawer names the products instead, which cannot be a constant, and
    // `vendor-inspector.test.tsx` now carries the absence distinction this file used to hold.
    const { container } = card()

    expect(container.textContent).not.toContain("Products named")
  })
})

describe("the card is the control that opens the drawer", () => {
  it("selects rather than navigating, and names itself for a reader who cannot see it", () => {
    // The card used to be a `<Link>` wrapping the whole tile, which made the vendor's record one
    // click away and the drawer impossible. Selection is the console's landed idiom for a list
    // whose reader works down it; the record link moved into the drawer.
    const onSelect = vi.fn()
    render(
      <VendorCard
        row={row()}
        catalogueAnswered
        totalCallSites={60}
        selected={false}
        onSelect={onSelect}
      />,
    )

    const control = screen.getByRole("button", { name: /Stripe/ })
    expect(control.getAttribute("aria-pressed")).toBe("false")
    fireEvent.click(control)
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it("reports its own selected state rather than leaving it to colour alone", () => {
    render(
      <VendorCard row={row()} catalogueAnswered totalCallSites={60} selected onSelect={() => {}} />,
    )

    expect(screen.getByRole("button", { name: /Stripe/ }).getAttribute("aria-pressed")).toBe("true")
  })
})

describe("the card asserts nothing the payload does not hold", () => {
  it("carries no confidence scalar, health figure, score or invented severity", () => {
    const { container } = card()

    const text = container.textContent ?? ""
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toMatch(/confidence|health|score|sev-\d|\d\s*\/\s*10|%/i)
  })

  it("does not answer the Findings screen's question, which is what put it on two screens", () => {
    // Owner ruling, 2026-08-19: Errors & Incidents belongs on Findings alone. A finding fact on
    // this card would put it back, and every other test in this file would stay green.
    const { container } = card()

    expect(container.textContent).toContain("stripe")
    expect(container.textContent?.toLowerCase()).not.toContain("finding")
  })
})
