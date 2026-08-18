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
          <Route path="/vendors/:vendorId" element={<VendorPage />} />
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
 * Decision 29 settles this page's order: exposure first, the vendor's history below it as the
 * reason findings appeared. The mock draws it the other way round and the decision wins.
 *
 * Asserted on document order rather than on which components exist, because both orders render
 * exactly the same set of cards.
 */
describe("VendorPage's order, per decision 29", () => {
  it("leads with what this vendor costs, before what it has done", () => {
    renderVendor("/vendors/stripe")

    const exposure = screen.getByTestId("vendor-exposure")
    const history = screen.getByTestId("vendor-history")

    // DOCUMENT_POSITION_FOLLOWING: history comes after exposure in document order.
    expect(exposure.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })
})
