/**
 * The shared findings table, and the two columns only some of its surfaces ask for.
 *
 * Six consumers render this table and four of them — the fleet and vendor surfaces — have no
 * solutions workflow, and only one has an inspector. What is under test is the structural switch,
 * twice: a column exists exactly when the surface passed the prop that owns it, and is not merely
 * empty otherwise. A column that rendered everywhere would put a write control on screens that
 * never earned it, and an Inspect button on screens with nothing to inspect into.
 *
 * Scope is `web/CLAUDE.md`'s: structural invariants, never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { RiskRow, Ticket } from "@/api/types"
import { FindingsTable } from "@/features/findings/findings-table"

afterEach(cleanup)

function row(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    name: "stripe-postcharges-4b1c9e",
    file: "src/billing/charge.ts",
    line: 42,
    symbol: "createCharge",
    operation: "PostCharges",
    vendor: "stripe",
    change_kind: "removed",
    severity: "breaking",
    finding_id: "f-1",
    binding_source: "static",
    ...overrides,
  }
}

function renderTable(
  props: {
    tickets?: readonly Ticket[] | null
    selectedId?: string | null
    onSelect?: (findingId: string) => void
  } = {},
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FindingsTable repoId="demo" rows={[row()]} {...props} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("the Solution column", () => {
  it("renders last when the surface passes tickets, one cell per row", () => {
    renderTable({ tickets: [] })

    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent)
    expect(headers[headers.length - 1]).toBe("Solution")
    // The cell is live, not a placeholder: an empty ticket list means this finding was never
    // sent, so the row offers the send.
    expect(screen.getByRole("button", { name: /Send to workflow/ })).toBeTruthy()
  })

  it("keeps the column while the ticket read is still in flight", () => {
    renderTable({ tickets: null })

    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent)
    expect(headers[headers.length - 1]).toBe("Solution")
    // In flight is its own claim — not "nothing was sent", which would offer the button.
    expect(screen.getByText(/not read yet/)).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("stays off entirely for the surfaces that never asked", () => {
    renderTable({})

    expect(screen.queryByText("Solution")).toBeNull()
    // Structural, not textual: the header row carries exactly the original seven columns, so
    // the four fleet and vendor consumers render today's table unchanged.
    expect(screen.getAllByRole("columnheader")).toHaveLength(7)
    expect(screen.queryByRole("button")).toBeNull()
  })
})

describe("the Inspect column", () => {
  it("stays off for every surface that passed no `onSelect`", () => {
    // The vendor level and the inspector's own constituent list render today's table unchanged:
    // eight columns when tickets are passed, seven when they are not. An unconditional column
    // would put a control on both with nothing behind it.
    renderTable({ tickets: [] })

    expect(screen.queryByRole("button", { name: "Inspect" })).toBeNull()
    expect(screen.getAllByRole("columnheader")).toHaveLength(8)
  })

  it("sits after Solution rather than displacing it", () => {
    renderTable({ tickets: [], onSelect: () => {} })

    const headers = screen.getAllByRole("columnheader").map((th) => th.textContent)
    expect(headers).toHaveLength(9)
    expect(headers[headers.length - 2]).toBe("Solution")
    expect(headers[headers.length - 1]).toBe("Inspect")
  })

  it("publishes the pressed row's id rather than navigating", () => {
    // The name Link is still the route to the finding. Inspect selects into the drawer, which is a
    // different question -- what does this row hold -- asked without leaving the table.
    const onSelect = vi.fn()
    renderTable({ onSelect })

    fireEvent.click(screen.getByRole("button", { name: "Inspect" }))

    expect(onSelect).toHaveBeenCalledWith("f-1")
  })

  it("marks the row the inspector is showing", () => {
    renderTable({ onSelect: () => {}, selectedId: "f-1" })

    expect(screen.getByRole("button", { name: "Inspect" }).getAttribute("aria-pressed")).toBe("true")
  })
})
