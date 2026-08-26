/**
 * The drawer over the Findings table, and the four answers it owes a reader.
 *
 * The one that matters is the enrichment failure: the selected row's own facts came from the list
 * the reader is looking at, so a failed second read must not blank the pane. And a 404 is the API
 * answering *about the finding* — it may have been patched since the list was read — which is a
 * different sentence from a request that did not arrive. `finding-page.tsx` spells the same three
 * and this holds the drawer to them.
 *
 * The two sample-caveat tests moved here from `change-unit-groups.test.tsx` with the nested table
 * they describe. The claim is unchanged: `finding_count` is the population and the rows are a
 * bounded sample, and silence would make a truncated list look complete.
 *
 * Scope is `console-dev-loop.md`'s: derivation and structure. Never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiStatusError, NotFoundError } from "@/api/errors"
import type { ChangeUnitRow, RiskRow } from "@/api/types"
import { FindingsInspector } from "@/features/findings/findings-inspector"

const detailState: { value: unknown } = { value: null }
const workflowState: { value: unknown } = { value: null }

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useFinding: () => detailState.value,
  useWorkflow: () => workflowState.value,
}))

const pending = { isPending: true, isError: false, isSuccess: false, data: undefined, error: null }

function settled(data: unknown) {
  return { isPending: false, isError: false, isSuccess: true, data, error: null }
}

function failed(error: unknown) {
  return { isPending: false, isError: true, isSuccess: false, data: undefined, error }
}

afterEach(() => {
  cleanup()
  detailState.value = pending
  workflowState.value = pending
})

function finding(overrides: Partial<RiskRow> = {}): RiskRow {
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

function unit(overrides: Partial<ChangeUnitRow> = {}): ChangeUnitRow {
  const findings = overrides.findings ?? [finding()]
  return {
    change_unit_id: "stripe:PostCharges:removed",
    vendor_id: "stripe",
    operation_id: "PostCharges",
    change_kind: "request-parameter-removed",
    from_version: "v2320",
    to_version: "v2330",
    severity: "breaking",
    repository_count: 1,
    call_site_count: 4,
    binding_rung: "static",
    finding_count: findings.length,
    findings,
    finding_ids: findings.map((row) => row.finding_id),
    repo_ids: ["demo"],
    standing: null,
    last_checkpoint_at: null,
    ...overrides,
  }
}

function renderInspector(
  selection: React.ComponentProps<typeof FindingsInspector>["selection"],
  rowsHeld = 1,
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FindingsInspector
          selection={selection}
          repoId="demo"
          rowsHeld={rowsHeld}
          tickets={[]}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("nothing selected", () => {
  it("renders nothing, because the drawer is what says so by being shut", () => {
    const { container } = renderInspector({ kind: "none" })

    expect(container.textContent).toBe("")
  })
})

describe("a key this window does not hold", () => {
  it("prints the key and names all three things it could be", () => {
    // Not "no row selected" and not "the row is gone": the row may sit behind a chip, on another
    // page, or nowhere in the graph, and nothing here can tell those apart.
    renderInspector({ kind: "unresolved", key: "nothing-holds-this" }, 25)

    expect(screen.getByText("nothing-holds-this")).toBeTruthy()
    expect(screen.getByText(/This page holds 25 rows/)).toBeTruthy()
    expect(screen.getByText(/behind a severity chip/)).toBeTruthy()
  })
})

describe("a selected change unit", () => {
  it("renders from the row the table already holds, without a second read", () => {
    detailState.value = failed(new ApiStatusError(500, "/api/findings/f-1"))
    renderInspector({ kind: "unit", unit: unit({ call_site_count: 4, repository_count: 1 }) })

    // Every fact here came with the grouped payload, so a failing enrichment read cannot touch it.
    expect(screen.getByText("Call sites")).toBeTruthy()
    expect(screen.getByText("4")).toBeTruthy()
    expect(screen.getByText(/v2320/)).toBeTruthy()
  })

  it("says the nested rows are a sample when the unit holds more than travelled", () => {
    // Moved from `change-unit-groups.test.tsx` with the nested table. The payload caps the array
    // and states the count independently; silence would render a truncated list as the whole unit.
    renderInspector({
      kind: "unit",
      unit: unit({ finding_count: 137, findings: [finding(), finding({ finding_id: "f-2" })] }),
    })

    expect(screen.getByText(/Showing 2 of 137 findings/)).toBeTruthy()
  })

  it("says nothing about a sample when every finding travelled", () => {
    renderInspector({
      kind: "unit",
      unit: unit({ finding_count: 2, findings: [finding(), finding({ finding_id: "f-2" })] }),
    })

    // Non-vacuous: the nested rows are there and the caveat is simply not owed.
    expect(screen.getAllByRole("row").length).toBeGreaterThan(1)
    expect(screen.queryByText(/Showing/)).toBeNull()
  })

  it("tells a null standing apart from a run in flight", () => {
    const { container: none } = renderInspector({ kind: "unit", unit: unit({ standing: null }) })
    expect(none.textContent).toMatch(/no run recorded for this change/)

    cleanup()
    const { container: flight } = renderInspector({
      kind: "unit",
      unit: unit({ standing: "in_progress" }),
    })
    expect(flight.textContent).toMatch(/in flight/)
    expect(flight.textContent).not.toMatch(/no run recorded/)
  })
})

describe("a selected finding", () => {
  it("keeps the row's own facts on screen while the enrichment read is in flight", () => {
    renderInspector({ kind: "finding", row: finding() })

    expect(screen.getByText("src/billing/charge.ts:42")).toBeTruthy()
    expect(screen.getByText("createCharge")).toBeTruthy()
  })

  it("leaves the row's facts standing when the enrichment read fails, and marks only the rest", () => {
    // The failure mode this test exists for is a blank pane: the reader selected a row whose facts
    // were already on screen, and a failed second request must not take them away.
    detailState.value = failed(new ApiStatusError(500, "/api/findings/f-1"))
    renderInspector({ kind: "finding", row: finding() })

    expect(screen.getByText("src/billing/charge.ts:42")).toBeTruthy()
    expect(screen.getAllByText(/the API did not answer/).length).toBeGreaterThan(0)
  })

  it("says a 404 means the finding is not open, not that the API went silent", () => {
    // Two different failures and only one of them is silence. Rendering "the API did not answer"
    // over a 404 is a false report of the failure the reader is looking at.
    detailState.value = failed(
      new NotFoundError("no open finding f-1", "f-1", "/api/findings/f-1"),
    )
    renderInspector({ kind: "finding", row: finding() })

    expect(screen.getAllByText(/this finding is not open/).length).toBeGreaterThan(0)
    expect(screen.queryByText(/the API did not answer/)).toBeNull()
  })

  it("links out to the full finding, inside this workspace", () => {
    const { container } = renderInspector({ kind: "finding", row: finding() })

    expect(container.querySelector('a[href="/repositories/demo/findings/f-1"]')).not.toBeNull()
  })

  it("renders an enriched field the payload holds rather than the absence marker", () => {
    // Non-vacuous partner to the failure tests: with a real answer the enriched rows carry values,
    // so the assertions above are about the failure and not about an always-absent pane.
    detailState.value = settled({
      finding: { finding_id: "f-1" },
      symbol: "createCharge",
      operation: "PostCharges",
      vendor: "stripe",
      args_keys: ["amount", "currency"],
      response_fields_read: [],
      sdk_version: "12.4.0",
      known_changes: [],
      source_served: false,
      call_site_source: null,
    })
    renderInspector({ kind: "finding", row: finding() })

    expect(screen.getByText("12.4.0")).toBeTruthy()
    expect(screen.getByText("amount, currency")).toBeTruthy()
  })
})
