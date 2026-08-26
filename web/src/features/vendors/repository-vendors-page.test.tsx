/**
 * The integrations attached to one repository — the deck the owner asked for.
 *
 * **Rewritten with the screen, 2026-08-26.** The owner ruled *"Vendors should fully switch to
 * cards"*, so the four-column table behind the card grid is gone and the screen is
 * `ScreenFrame layout="locked"`. Every assertion the old file carried survives; four of them had to
 * change their reach because what they reached for no longer exists:
 *
 * - the row count was `tbody tr` and is now one card per integration;
 * - the per-card `<Link>` to the vendor's record became the drawer's link, because the card is now
 *   the control that opens the drawer rather than a link wrapping a tile;
 * - "does not show an empty table" is now "does not draw a table at all", which is the stronger
 *   form of the same claim and the one the ruling actually asks for;
 * - the two catalogue-did-not-answer tests reach the cards instead of the rows.
 *
 * **The scoped-answer discipline is the substance here.** The coverage route echoes the `repo_id`
 * it was computed for precisely so a caller cannot render another repository's integrations under
 * this one's name. `codebases-panel.tsx` had that exact defect once — it printed the fleet-wide
 * `total_findings` under every card — so this screen asserts the scope it renders, not just the
 * rows.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
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
      by_service: Object.keys(byVendor).map((vendor_id) => ({
        vendor_id,
        service_id: `${vendor_id}-payments`,
        call_sites: byVendor[vendor_id],
        operations: 1,
        last_indexed: "2026-08-20T00:00:00+00:00",
      })),
      by_operation: Object.keys(byVendor).map((vendor_id) => ({
        vendor_id,
        service_id: `${vendor_id}-payments`,
        operation_id: `${vendor_id}.create`,
        call_sites: byVendor[vendor_id],
        last_indexed: "2026-08-20T00:00:00+00:00",
      })),
      by_binding_status: {},
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

/** Every card on the deck. */
function cards(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll('[data-testid="vendor-card"]')] as HTMLElement[]
}

describe("the integrations attached to one repository", () => {
  it("draws one card per integration the scoped answer returned, busiest first", () => {
    coverage("org/one", { stripe: 3, openai: 5 })

    const { container } = renderAt("org/one")

    expect(cards(container).length).toBe(2)
    // The ordering is the screen's, not the payload's: `by_vendor` is an object and object key
    // order is not a fact a reader should have to trust.
    expect(within(cards(container)[0]).getByText("openai")).not.toBeNull()
    expect(within(cards(container)[1]).getByText("stripe")).not.toBeNull()
  })

  it("draws no table anywhere, which is the ruling rather than a consequence of it", () => {
    // Owner ruling, 2026-08-26: *"Vendors should fully switch to cards."* The screen carried a
    // card grid AND a four-column table of the same rows behind a constant that could only ever be
    // "cards" -- one edit from being reachable. This is the assertion that keeps it gone.
    coverage("org/one", { stripe: 3, openai: 5 })

    const { container } = renderAt("org/one")

    expect(container.querySelector("table")).toBeNull()
    expect(container.querySelector("tbody")).toBeNull()
  })

  it("locks the screen so the deck scrolls inside its pane rather than the page", () => {
    // `ScreenFrame layout="locked"` stamps `data-screen="locked"`, which is what flips `main` to
    // `overflow-hidden`. Measured 2026-08-26: eighteen of twenty-one screens were still `flow`,
    // one long scrolling column, which is how a console changes palette and stays the old console.
    coverage("org/one", { stripe: 3 })

    const { container } = renderAt("org/one")

    expect(container.querySelector('[data-screen="locked"]')).not.toBeNull()
  })

  it("opens the integration's record from the drawer, carrying the repository as the scope", () => {
    coverage("org/one", { stripe: 4 })

    const { container } = renderAt("org/one")
    fireEvent.click(within(cards(container)[0]).getByRole("button"))

    // The scope travels in the path, because a vendor's record is reachable both inside a
    // repository and fleet-wide and the payload distinguishes the two.
    const link = screen.getByRole("link", { name: /Open the full record/i })
    expect(link.getAttribute("href")).toBe("/repositories/org%2Fone/vendors/stripe")
  })

  it("does not answer the Findings screen's question, which is what put it on two screens", () => {
    coverage("org/one", { stripe: 4 })

    const { container } = renderAt("org/one")

    // Owner ruling, 2026-08-19: Errors & Incidents belongs on Findings alone. A finding card fact,
    // a per-integration findings ranking or a facet would each put it back here, and every other
    // test in this file would stay green.
    // Non-vacuous: the card rendered, with the fact this screen does own.
    expect(container.textContent).toContain("stripe")
    expect(container.textContent).not.toContain("open findings")
  })

  it("says no integration is bound rather than drawing an empty deck", () => {
    coverage("org/one", {})

    const { container } = renderAt("org/one")

    expect(cards(container).length).toBe(0)
    expect(container.textContent).toContain("No integration is bound to this repository")
  })

  it("refuses to draw cards under a repository the answer was not computed for", () => {
    // The defect this exists to stop, which has happened here before: another scope's answer
    // rendered under one repository's name. The coverage route echoes its own scope so the screen
    // can check.
    coverage("org/other", { stripe: 4 })

    const { container } = renderAt("org/one")

    expect(cards(container).length).toBe(0)
    expect(container.textContent).toContain("computed for a different scope")
  })
})

describe("the search narrows the deck without claiming a new scope", () => {
  it("keeps only the cards whose id or written name matches", () => {
    coverage("org/one", { stripe: 3, openai: 5 })

    const { container } = renderAt("org/one")
    fireEvent.change(screen.getByLabelText(/Search the integrations/i), {
      target: { value: "stri" },
    })

    expect(cards(container).length).toBe(1)
    expect(within(cards(container)[0]).getByText("stripe")).not.toBeNull()
  })

  it("says the deck was narrowed rather than that nothing is bound", () => {
    // A narrowed view that reads as empty is the defect `filters.tsx` records: an operator sees a
    // short list and no reason for it. The two emptinesses are different answers and say so.
    coverage("org/one", { stripe: 3, openai: 5 })

    const { container } = renderAt("org/one")
    fireEvent.change(screen.getByLabelText(/Search the integrations/i), {
      target: { value: "zzz" },
    })

    expect(cards(container).length).toBe(0)
    expect(container.textContent).toContain("No integration on this deck matches the search")
    expect(container.textContent).not.toContain("No integration is bound to this repository")
  })
})

describe("a catalogue that did not answer is not an integration without an adapter", () => {
  // Shipped for weeks: the map was built from `data?.adapters ?? []`, so an errored catalogue
  // rendered the badge `none` on every row -- a positive claim that these vendors have no adapter,
  // from a query that answered nothing -- and zeroed every tier count, which removed the whole
  // facet rather than saying why it was gone.
  it("refuses to print `none` on a card the catalogue never described", () => {
    coverage("org/one", { stripe: 3 })
    adaptersFailed()

    renderAt("org/one")

    expect(screen.queryByText("none")).toBeNull()
    // One per card: every integration is undescribed when the catalogue does not answer, and each
    // card says so rather than one banner standing in for all of them.
    expect(screen.getAllByText(/the adapter catalogue did not answer/i).length).toBeGreaterThan(0)
  })

  it("says nothing was counted rather than printing a tier it never read", () => {
    // The tier facet this used to assert went with the owner's ruling of 2026-08-25 -- every
    // attached vendor was generated, so the control offered one answer twice. What it guaranteed
    // is not dropped: the card still refuses to name a tier the catalogue never described, and
    // says which nothing it is. `M14-W273`'s precedent -- a test whose subject retires may go,
    // but not the coverage it carried.
    coverage("org/one", { stripe: 3 })
    adaptersFailed()

    renderAt("org/one")

    expect(screen.getAllByText(/the adapter catalogue did not answer/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/adapter: generated/i)).toBeNull()
  })
})
