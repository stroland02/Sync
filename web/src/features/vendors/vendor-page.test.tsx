/**
 * A level says what contains it.
 *
 * Seven of nine routes rendered a breadcrumb and these two did not, so a reader who arrived at a
 * vendor from a repository had no rendered answer to "what is above this". The trail is the
 * answer, and it is asserted here as structure — the crumbs and their order — rather than as
 * markup, per `.claude/rules/console-dev-loop.md`.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { VendorPage } from "@/features/vendors/vendor-page"

afterEach(cleanup)

function renderVendor(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/repositories/:repoId/vendors/:vendorId" element={<VendorPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Three per-page breadcrumb tests stood here and in `codebase-page.test.tsx`, and went with the
// page header that carried them (`M14-W391`, owner decision 7). The console drew two trails for one
// question; the page's was the duplicate. What they guaranteed -- what contains what, ending on the
// subject -- is now asserted in `layouts/scope-switchers.test.tsx` against the trail that survived,
// which also carries the page's name and the page's only `h1`.

/**
 * The owner's settled shape, 2026-08-19 (second re-ruling that day, superseding decision 29 and
 * the morning's inversion): the API-calls table is the page's fixed top answer, and the vendor's
 * other three records — changes, findings, sources — are tabs beneath it, one mounted at a time.
 */
describe("VendorPage's shape: API calls on top, everything else in tabs", () => {
  it("leads with the API-calls table, tabs following", () => {
    renderVendor("/repositories/seed-console/vendors/stripe")

    const exposure = screen.getByTestId("vendor-exposure")
    const panels = screen.getByTestId("vendor-panels")

    expect(exposure.compareDocumentPosition(panels) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it("offers the three records as a strip and opens on Changes", () => {
    renderVendor("/repositories/seed-console/vendors/stripe")

    const strip = screen.getByRole("navigation", { name: /vendor records/i })
    const labels = [...strip.querySelectorAll("button")].map((b) => b.textContent)
    expect(labels).toEqual(["Changes", "Findings", "Sources"])
    expect(
      strip.querySelector('[aria-pressed="true"]')?.textContent
    ).toBe("Changes")
  })

  it("reads the open tab from the address, so a shared link opens where the sender was", () => {
    renderVendor("/repositories/seed-console/vendors/stripe?panel=sources")

    const strip = screen.getByRole("navigation", { name: /vendor records/i })
    expect(strip.querySelector('[aria-pressed="true"]')?.textContent).toBe("Sources")
  })

  it("falls back to the default tab on a panel value nothing declares", () => {
    // A mistyped shared address lands on the default table, never on a strip with no table.
    renderVendor("/repositories/seed-console/vendors/stripe?panel=nonsense")

    const strip = screen.getByRole("navigation", { name: /vendor records/i })
    expect(strip.querySelector('[aria-pressed="true"]')?.textContent).toBe("Changes")
  })
})
