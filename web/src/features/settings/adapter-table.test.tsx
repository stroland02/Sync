/**
 * The adapter table renders never-measured apart from zero, and the rest is arrangement.
 *
 * This is the one rule on the screen that a correct-looking implementation gets wrong silently.
 * `sync/dashboard/adapters.py` answers `null` for an adapter the graph holds no row for and a
 * number for one it does, and every renderer in JavaScript's path from that null to a cell has a
 * way of turning it into `0` — a `?? 0`, a `Number()`, a template literal on a nullable. Each of
 * those reads as tidy and each erases the case the screen exists to show: an adapter that has
 * silently stopped delivering renders as one that ran and found nothing.
 *
 * `CLAUDE.md` names absence-apart-from-zero as one of four distinctions the console renders rather
 * than assumes, and never-measured apart from nothing-here as another. This table is where both
 * land at once, so both are asserted here rather than left to a reviewer.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: what the cell says, never how it is styled.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { AdapterRow } from "@/api/types"
import { AdapterTable, NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"

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

function rowFor(vendorId: string) {
  const cell = screen.getByText(vendorId)
  const row = cell.closest("tr")
  if (row === null) throw new Error(`no row rendered for ${vendorId}`)
  return row
}

describe("AdapterTable", () => {
  it("says an adapter has never delivered rather than printing zero", () => {
    render(<AdapterTable adapters={[neverDelivered]} />)

    const row = rowFor("acme")
    expect(within(row).getByText(NEVER_DELIVERED_NOTE)).toBeTruthy()
    expect(row.textContent).not.toMatch(/\b0\b/)
  })

  it("prints the counts an adapter that has delivered actually carries", () => {
    render(<AdapterTable adapters={[delivered]} />)

    const row = rowFor("stripe")
    expect(within(row).getByText("12")).toBeTruthy()
    expect(within(row).getByText("5")).toBeTruthy()
  })

  it("distinguishes zero from never, when the graph reports a genuine zero", () => {
    // Not reachable from `adapter_inventory` today -- a vendor with rows has at least one change.
    // Asserted anyway, because the direction that loses information is a renderer that cannot tell
    // them apart, and that renderer passes every other test in this file.
    render(<AdapterTable adapters={[{ ...delivered, changes: 0, operations: 0 }]} />)

    const row = rowFor("stripe")
    expect(within(row).queryByText(NEVER_DELIVERED_NOTE)).toBeNull()
    expect(within(row).getAllByText("0").length).toBeGreaterThan(0)
  })

  it("names what registered each adapter, and what it reads", () => {
    render(<AdapterTable adapters={[delivered, neverDelivered]} />)

    expect(within(rowFor("acme")).getByText("acme/acme-node")).toBeTruthy()
    expect(within(rowFor("stripe")).getByText("coded")).toBeTruthy()
  })

  it("lists the intake sources a delivered adapter's rows carry", () => {
    render(<AdapterTable adapters={[delivered]} />)

    expect(within(rowFor("stripe")).getByText(/changelog/)).toBeTruthy()
    expect(within(rowFor("stripe")).getByText(/oasdiff/)).toBeTruthy()
  })

  it("does not offer a column for a decline reason nothing records", () => {
    // The mock draws a Cloudflare row explaining why a catalogue declined. No field behind it
    // exists, and a column blank on every row reads as "no adapter has ever declined" -- a claim
    // nothing measured, on the screen whose whole argument is that it does not make those.
    render(<AdapterTable adapters={[delivered, neverDelivered]} />)

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent ?? "")
    expect(headers.join(" ").toLowerCase()).not.toContain("decline")
  })

  it("says nothing at all when the deployment registers no adapter and holds no history", () => {
    render(<AdapterTable adapters={[]} />)

    expect(screen.getByText(/no adapter/i)).toBeTruthy()
  })
})
