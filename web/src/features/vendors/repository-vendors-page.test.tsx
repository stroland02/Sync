/**
 * The vendors attached to one repository — the list screen the owner asked for.
 *
 * *"the vendors page that list all the vendors part of that codebase"*. This is the list;
 * `vendor-page.tsx` remains the detail.
 *
 * **The list is what the index bound, from 2026-08-19.** It was built on `overview.vendors` — a
 * `GROUP BY` over open findings — so a vendor this codebase calls cleanly was absent from the page
 * asking which vendors it uses, and the page could not answer its own question without the Errors
 * & Incidents payload the owner has now ruled off it. Coverage answers it directly.
 *
 * **The scoped-answer discipline is the substance here.** The coverage route echoes the `repo_id`
 * it was computed for precisely so a caller cannot render another repository's vendors under this
 * one's name. `codebases-panel.tsx` had that exact defect once — it printed the fleet-wide
 * `total_findings` under every card — so this screen asserts the scope it renders, not just the
 * rows.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RepositoryVendorsPage } from "@/features/vendors/repository-vendors-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })

const { useRepositoryCoverage, useAdapters } = vi.hoisted(() => ({
  useRepositoryCoverage: vi.fn(),
  useAdapters: vi.fn(),
}))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryCoverage,
  useAdapters,
}))

/** The catalogue answered, and holds these adapters. */
function adapters(items: { vendor_id: string; kind: string }[] = []) {
  useAdapters.mockReturnValue(settled({ adapters: items }))
}

/** The catalogue did not answer -- distinct from answering that a vendor has no adapter. */
function adaptersFailed() {
  useAdapters.mockReturnValue({ isPending: false, isError: true, isSuccess: false, data: undefined })
}

/** The coverage answer, in the scope it was computed for. */
function coverage(repoId: string, byVendor: Record<string, number>) {
  adapters()
  useRepositoryCoverage.mockReturnValue(
    settled({
      repo_id: repoId,
      by_vendor: byVendor,
      last_indexed: {},
      total_call_sites: Object.values(byVendor).reduce((sum, n) => sum + n, 0),
      by_service: [],
      by_operation: [],
    })
  )
}

function renderAt(repoId: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/${encodeURIComponent(repoId)}/vendors`]}>
        <Routes>
          <Route path="/repositories/:repoId/vendors" element={<RepositoryVendorsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the vendors attached to one repository", () => {
  it("lists one row per vendor the scoped answer returned", () => {
    coverage("org/one", { stripe: 3, openai: 5 })

    const { container } = renderAt("org/one")

    const rows = container.querySelectorAll("tbody tr")
    expect(rows.length).toBe(2)
    // Busiest first: the ordering is the screen's, not the payload's, because `by_vendor` is an
    // object and object key order is not a fact a reader should have to trust.
    expect(within(rows[0] as HTMLElement).getByText("openai")).not.toBeNull()
    expect(within(rows[1] as HTMLElement).getByText("stripe")).not.toBeNull()
  })

  it("links each vendor to its detail, carrying the repository as the scope", () => {
    coverage("org/one", { stripe: 4 })

    renderAt("org/one")

    // The scope travels in the query string, because a vendor's detail is reachable both inside a
    // repository and fleet-wide and the payload distinguishes the two.
    const link = screen.getByRole("link", { name: /stripe/i })
    expect(link.getAttribute("href")).toBe("/repositories/org%2Fone/vendors/stripe")
  })

  it("does not answer the Findings screen's question, which is what put it on two screens", () => {
    coverage("org/one", { stripe: 4 })

    const { container } = renderAt("org/one")

    // Owner ruling, 2026-08-19: Errors & Incidents belongs on Findings alone. A finding column,
    // a per-integration findings ranking, or a card fact would each put it back here, and every
    // other test in this file would stay green.
    // Non-vacuous: the row rendered, with the column this screen does own.
    expect(screen.getByRole("columnheader", { name: /call sites/i })).toBeTruthy()
    expect(screen.queryByRole("columnheader", { name: /open findings/i })).toBeNull()
    expect(container.textContent).not.toContain("open findings")
  })

  it("says no vendor is attached rather than showing an empty table", () => {
    coverage("org/one", {})

    const { container } = renderAt("org/one")

    expect(container.querySelectorAll("tbody tr").length).toBe(0)
    expect(container.textContent).toContain("No vendor is attached to this repository")
  })

  it("refuses to render rows under a repository the answer was not computed for", () => {
    // The defect this exists to stop, which has happened here before: another scope's answer
    // rendered under one repository's name. The coverage route echoes its own scope so the screen
    // can check.
    coverage("org/other", { stripe: 4 })

    const { container } = renderAt("org/one")

    expect(container.querySelectorAll("tbody tr").length).toBe(0)
    expect(container.textContent).toContain("computed for a different scope")
  })
})

describe("a catalogue that did not answer is not a vendor without an adapter", () => {
  // Shipped for weeks: the map was built from `data?.adapters ?? []`, so an errored catalogue
  // rendered the badge `none` on every row -- a positive claim that these vendors have no adapter,
  // from a query that answered nothing -- and zeroed every tier count, which removed the whole
  // facet rather than saying why it was gone.
  it("refuses to print `none` on a row the catalogue never described", () => {
    coverage("org/one", { stripe: 3 })
    adaptersFailed()

    renderAt("org/one")

    expect(screen.queryByText("none")).toBeNull()
    // One per row: every vendor is undescribed when the catalogue does not answer, and each
    // row says so rather than one banner standing in for all of them.
    expect(screen.getAllByText(/the adapter catalogue did not answer/i).length).toBeGreaterThan(0)
  })

  it("says the tiers are uncounted rather than removing the control", () => {
    coverage("org/one", { stripe: 3 })
    adaptersFailed()

    renderAt("org/one")

    expect(screen.getByText(/Tiers are unavailable/i)).toBeTruthy()
  })
})
