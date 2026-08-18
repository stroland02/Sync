/**
 * One vendor's card: identity, adapter tier, what the graph holds, and what it refuses to claim.
 *
 * Four distinctions land on this component at once and each is one careless `??` away from being
 * erased, so each is asserted here rather than left to a reviewer:
 *
 * - **The tier vocabulary is the registry's, not a plan's.** `sync/signals/registry.py` emits
 *   `coded`, `generated` and `mcp`; `sync/dashboard/adapters.py` adds `unregistered` for history
 *   keyed by a vendor nothing serves any more. A card that renders a tier the payload cannot carry
 *   is a claim about the deployment which nothing computed.
 * - **Never-delivered apart from zero.** `adapter_inventory` answers `null` for an adapter the
 *   graph holds no `vendor_change` row for. `0` would mean Sync read the specification and had
 *   nothing to say. The Settings adapter table holds the same line, and this card reuses its
 *   sentence rather than spelling a second one.
 * - **Absence apart from zero, on the finding count.** `/api/adapters` is deployment-wide and
 *   `/api/overview` is repository-scoped, so an adapter registered but not bound in the selected
 *   codebase has no count at all — which is a different fact from a count of nought.
 * - **Nothing-here apart from never-measured, on the adapter itself.** A vendor the overview names
 *   and the adapter inventory does not is a third state again.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: what the card says and how it derives it. Never a
 * class name, never a snapshot.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { AdapterRow } from "@/api/types"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"
import {
  ADAPTER_TIERS,
  CODED_SOURCE_NOTE,
  FRESHNESS_QUALIFICATION,
  NO_ADAPTER_ROW_NOTE,
  NO_FINDING_COUNT_NOTE,
  VendorCard,
  adapterTierLabel,
} from "@/features/vendors/vendor-card"

afterEach(cleanup)

describe("the vendor's mark", () => {
  it("shows the vendor's own mark beside the id, per decision 6", () => {
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={2} />)

    expect(screen.getByTestId("vendor-mark-image")).toBeTruthy()
  })

  /**
   * Decision 6 reversed the refusal to render a mark. It did not reverse what the refusal was
   * protecting: the id is what Sync actually holds, and the mark is an aid to finding it.
   */
  it("keeps the id as the identity rather than letting the mark stand for it", () => {
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={2} />)

    expect(screen.getByRole("heading", { name: "stripe" })).toBeTruthy()
    expect(screen.getByTestId("vendor-mark-image").getAttribute("alt")).toBe("")
  })
})

const delivered: AdapterRow = {
  vendor_id: "stripe",
  kind: "coded",
  source: null,
  changes: 12,
  operations: 5,
  last_change_at: "2026-08-16T10:04:00+00:00",
  sources: ["changelog", "oasdiff"],
}

const neverDelivered: AdapterRow = {
  vendor_id: "acme",
  kind: "generated",
  source: "acme/acme-node",
  changes: null,
  operations: null,
  last_change_at: null,
  sources: null,
}

describe("VendorCard", () => {
  it("identifies the vendor by its id, and draws no mark of its own", () => {
    const { container } = render(
      <VendorCard vendorId="stripe" adapter={delivered} openFindingCount={3} />
    )

    // Decision 6 reversed the refusal to show a mark, and kept the reason behind it: the id is the
    // identity Sync actually holds, and it is what the graph, the payload and every other screen
    // key on. What stays refused is a mark Sync renders itself — no inline svg, no drawn path.
    expect(screen.getByRole("heading", { name: "stripe" })).toBeTruthy()
    expect(container.querySelector("svg")).toBeNull()
    expect(container.querySelector("path")).toBeNull()
  })

  it("renders every tier in the registry's own vocabulary, legible as a word without colour", () => {
    expect(ADAPTER_TIERS.length).toBeGreaterThan(0)

    for (const kind of ADAPTER_TIERS) {
      cleanup()
      render(
        <VendorCard
          vendorId="acme"
          adapter={{ ...delivered, vendor_id: "acme", kind }}
          openFindingCount={0}
        />
      )
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
    const { container } = render(
      <VendorCard vendorId="acme" adapter={neverDelivered} openFindingCount={null} />
    )

    expect(screen.getByText(NEVER_DELIVERED_NOTE)).toBeTruthy()
    expect(container.textContent).not.toMatch(/\b0\b/)
  })

  it("prints a confirmed zero as a number, apart from an adapter that never delivered", () => {
    render(
      <VendorCard
        vendorId="stripe"
        adapter={{ ...delivered, changes: 0, operations: 0, last_change_at: null }}
        openFindingCount={0}
      />
    )

    expect(screen.queryByText(NEVER_DELIVERED_NOTE)).toBeNull()
    expect(screen.getAllByText("0").length).toBeGreaterThan(0)
  })

  it("says a coded adapter is written here rather than marking its source absent", () => {
    // `adapter_inventory` answers `source: null` for a coded adapter because there is no external
    // repository behind it. That is a fact about the adapter, not a gap in the record, and the
    // absence marker would claim the second.
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={3} />)
    expect(screen.getByText(CODED_SOURCE_NOTE)).toBeTruthy()

    cleanup()
    render(<VendorCard vendorId="acme" adapter={neverDelivered} openFindingCount={null} />)
    expect(screen.queryByText(CODED_SOURCE_NOTE)).toBeNull()
    expect(screen.getByText("acme/acme-node")).toBeTruthy()
  })

  it("names the newest recorded change as evidence age, never as a freshness measurement", () => {
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={3} />)

    // Nothing in Sync records an intake attempt, only its result. A card labelling this timestamp
    // "last checked" would be asserting a poll nothing wrote down.
    expect(screen.getByText(FRESHNESS_QUALIFICATION)).toBeTruthy()
    expect(screen.queryByText(/last checked/i)).toBeNull()
    expect(screen.queryByText(/up to date/i)).toBeNull()
  })

  it("renders an uncounted finding total as absence and a counted nought as a figure", () => {
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={null} />)
    expect(screen.getByText(NO_FINDING_COUNT_NOTE)).toBeTruthy()

    cleanup()
    render(<VendorCard vendorId="stripe" adapter={delivered} openFindingCount={0} />)
    expect(screen.queryByText(NO_FINDING_COUNT_NOTE)).toBeNull()
    expect(screen.getAllByText("0").length).toBeGreaterThan(0)
  })

  it("distinguishes a vendor with no adapter row from one whose adapter delivered nothing", () => {
    render(<VendorCard vendorId="twilio" adapter={null} openFindingCount={2} />)

    expect(screen.getByText(NO_ADAPTER_ROW_NOTE)).toBeTruthy()
    expect(screen.queryByText(NEVER_DELIVERED_NOTE)).toBeNull()
    // The finding count is a different query's answer and survives the adapter being unknown.
    expect(screen.getByText("2")).toBeTruthy()
  })

  it("asserts no confidence scalar, health figure, score or invented severity", () => {
    const { container } = render(
      <VendorCard vendorId="stripe" adapter={delivered} openFindingCount={3} />
    )

    const text = container.textContent ?? ""
    expect(text.length).toBeGreaterThan(0)
    expect(text).not.toMatch(/confidence|health|score|sev-\d|\d\s*\/\s*10|%/i)
  })
})
