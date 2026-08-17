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

describe("VendorPage's breadcrumb", () => {
  it("names what contains this vendor, ending on the vendor itself", () => {
    renderVendor("/vendors/stripe")

    const trail = screen.getByLabelText("Breadcrumb")
    expect(trail.textContent).toContain("Repositories")
    expect(trail.textContent).toContain("stripe")
    // The current level is a destination, not a link: it carries aria-current instead of an href.
    expect(trail.querySelector('[aria-current="page"]')?.textContent).toBe("stripe")
  })

  it("names the repository it was narrowed by when one is in scope", () => {
    renderVendor("/vendors/stripe?repo_id=org%2Fpayments")

    const trail = screen.getByLabelText("Breadcrumb")
    expect(trail.textContent).toContain("org/payments")
  })
})
