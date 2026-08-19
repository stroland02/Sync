/**
 * Findings: what is broken in this workspace, as a destination rather than a drill-down.
 *
 * The console had five nav routes and no findings list. A finding was reachable only by going
 * through a vendor, a signal or a detector first, so the one question the product exists to answer
 * -- *what is broken here* -- had no screen. This is that screen.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants, never class names and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FindingsPage } from "@/features/findings/findings-page"
import type { RiskRow, VendorFindingsPage } from "@/api/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function row(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    file: "src/billing/charge.ts",
    line: 42,
    symbol: "createCharge",
    operation: "PostCharges",
    vendor: "stripe",
    change_kind: "removed",
    severity: "breaking",
    finding_id: "f-91ac",
    binding_source: "resolved",
    ...overrides,
  }
}

const mockState: { page: unknown } = { page: null }

const settled = (data: unknown) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  data,
  error: null,
  refetch: () => undefined,
})

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useWorkspaceFindings: () => settled(mockState.page),
  // The page gates its body on this too -- an unmocked detector roll-up stays pending and the
  // table never renders, so every assertion below fails on a loading state rather than on its
  // subject. The names matter: the triage header reports which detectors stood behind a zero.
  useDetectors: () => settled({ detectors: [{ detector: "vendor_change", total: 1 }], by_rung: {}, total_open_findings: 1 }),
}))

function page(items: RiskRow[], overrides: Partial<VendorFindingsPage> = {}) {
  return {
    items,
    total: items.length,
    next_offset: null,
    repo_id: "org/one",
    vendor_id: null,
    severity_counts: { breaking: 1 },
    severity_total: items.length,
    order: "severity",
    severity_order: ["breaking", "behavioural"],
    indexed_at: null,
    feed_fetched_at: null,
    binding_source: "resolved",
    context_savings: 0,
    ...overrides,
  } as unknown as VendorFindingsPage
}

function renderFindings(entry = "/repositories/org%2Fone/findings") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/repositories/:repoId/findings" element={<FindingsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the findings screen", () => {
  it("links each row to the finding, inside this workspace", () => {
    mockState.page = page([row()])
    const { container } = renderFindings()

    // The whole point of the screen, and the thing W436 found broken everywhere else: the link has
    // to carry the workspace, because `/findings/:id` is not a route the router serves.
    const link = container.querySelector('a[href="/repositories/org%2Fone/findings/f-91ac"]')
    expect(link).not.toBeNull()
  })

  it("builds the operation link from the row's own vendor, not from a page-level one", () => {
    mockState.page = page([row({ vendor: "shopify", operation: "GetOrder" })])
    const { container } = renderFindings()

    // A workspace-wide list holds several vendors at once, so a page-level vendor would put every
    // row's operation under one vendor's binding surface. Each row carries its own.
    const link = container.querySelector(
      'a[href="/repositories/org%2Fone/bindings/vendors/shopify/operations/GetOrder"]'
    )
    expect(link).not.toBeNull()
  })

  it("shows the rung on every row, because a finding that cannot be attributed cannot be fixed", () => {
    mockState.page = page([row({ binding_source: "static" })])
    const { container } = renderFindings()

    // `CLAUDE.md`: every binding carries the rung it came from, and so does every artifact derived
    // from it. The rung is never a hideable column.
    expect(container.textContent).toMatch(/static/i)
  })

  it("says the count is this workspace's, and never states it unscoped", () => {
    mockState.page = page([row(), row({ finding_id: "f-2" })])
    const { container } = renderFindings()
    const text = container.textContent ?? ""

    // Asserting that "org/one" appears anywhere is not this assertion: the breadcrumb prints it,
    // so a figure that had lost its scope entirely still passed that version of this test. It has
    // to be the *figure* that names the workspace, which is what this phrasing pins.
    expect(text).toContain("findings in org/one")
    // The `codebases-panel` defect in its general form: a figure printed without the scope it was
    // counted over reads as a claim about everything.
    expect(text).not.toMatch(/across every repository/i)
  })

  it("distinguishes an empty workspace from one nothing has looked at", () => {
    // Absence apart from zero, which is one of the four distinctions this console exists for.
    // "No open findings" on its own reads as a clean bill of health, so the screen has to say
    // which nothing it is -- and the test now asserts *both* sides, which is what its name
    // promised. It previously ran one fixture and asserted the other branch's wording, so it
    // failed against a screen that was right.
    mockState.page = page([], { indexed_at: null })
    const before = renderFindings().container.textContent ?? ""
    expect(before).toMatch(/nothing has checked/i)
    expect(before).not.toMatch(/no open findings under/i)

    cleanup()

    mockState.page = page([], { indexed_at: "2026-08-18T00:00:00Z" })
    const after = renderFindings().container.textContent ?? ""
    expect(after).toMatch(/no open findings under/i)
    expect(after).not.toMatch(/nothing has checked/i)
  })

  it("carries no page header, because density is dense", () => {
    mockState.page = page([row()])
    renderFindings()

    expect(screen.queryByRole("heading", { level: 1 })).toBeNull()
  })
})
