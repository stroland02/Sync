/**
 * The vendor record screen's structure, which is the thing the rebuild is.
 *
 * Three per-page breadcrumb tests stood here and in `codebase-page.test.tsx`, and went with the
 * page header that carried them (`M14-W391`, owner decision 7). What they guaranteed -- what
 * contains what, ending on the subject -- is asserted in `layouts/scope-switchers.test.tsx` against
 * the trail that survived.
 *
 * What is held here instead is what a token swap cannot produce and what a reskin loses first: that
 * the screen is bounded rather than one scrolling column, that it draws four panes rather than a
 * stack of cards, that only the pressed record mounts, and that the address names the record. None
 * of it asserts a class name or a snapshot.
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

/** Every pane the screen composes, by the heading `PanelPane` gives its label. */
function paneLabels(): string[] {
  return screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent ?? "")
}

describe("the vendor record is a locked composition, not a column", () => {
  it("owns its own scrollbars rather than handing them to the chassis", () => {
    const { container } = renderVendor("/repositories/seed-console/vendors/stripe")

    // `data-screen="locked"` is what flips `main` to `overflow-hidden` through `:has()`. A screen
    // that lost it would go back to being one scrolling column and nothing else would say so.
    expect(container.querySelector('[data-band="content"]')?.getAttribute("data-screen")).toBe(
      "locked"
    )
  })

  it("draws the four panes the composition is made of", () => {
    renderVendor("/repositories/seed-console/vendors/stripe")

    expect(paneLabels()).toEqual([
      "Operations this codebase calls",
      "Where the record comes from",
      "What this integration publishes",
      "The vendor's own record",
    ])
  })

  it("names the subject and both scopes without waiting for a payload", () => {
    renderVendor("/repositories/seed-console/vendors/stripe")

    const identity = screen.getByTestId("vendor-identity")
    // The id is the key every URL and join uses; the two scopes are why the figures on this screen
    // are allowed to disagree. All three come from the address, so a failed read cannot remove them.
    expect(identity.textContent).toContain("stripe")
    expect(identity.textContent).toContain("seed-console")
    expect(identity.textContent).toMatch(/in every repository/i)
  })
})

describe("the record chips are the address, and only the pressed one mounts", () => {
  it("offers both records and opens on the changes feed", () => {
    renderVendor("/repositories/seed-console/vendors/stripe")

    const chips = screen.getByRole("group", { name: /which record/i })
    expect([...chips.querySelectorAll("button")].map((button) => button.textContent)).toEqual([
      "Changes published",
      "Open findings",
    ])
    expect(chips.querySelector('[aria-pressed="true"]')?.textContent).toBe("Changes published")
  })

  it("reads the open record from the address, so a shared link opens where the sender was", () => {
    renderVendor("/repositories/seed-console/vendors/stripe?record=findings")

    const chips = screen.getByRole("group", { name: /which record/i })
    expect(chips.querySelector('[aria-pressed="true"]')?.textContent).toBe("Open findings")
  })

  it("falls back to the default record on a value nothing declares", () => {
    // A mistyped shared address lands on the default record, never on a head with no table.
    renderVendor("/repositories/seed-console/vendors/stripe?record=nonsense")

    const chips = screen.getByRole("group", { name: /which record/i })
    expect(chips.querySelector('[aria-pressed="true"]')?.textContent).toBe("Changes published")
  })

  it("asks for the pressed record only, so the other one issues no request", () => {
    // Three data-fetching tables mounted to show one is the cost `page-tabs.tsx` documents, and it
    // is what the tab shape was chosen to avoid. Each record names its own read while it is in
    // flight, which is what makes the mount observable without a server.
    renderVendor("/repositories/seed-console/vendors/stripe")
    expect(screen.getByText(/loading the changes stripe published/i)).toBeTruthy()
    expect(screen.queryByText(/loading open findings for stripe/i)).toBeNull()

    cleanup()
    renderVendor("/repositories/seed-console/vendors/stripe?record=findings")
    expect(screen.getByText(/loading open findings for stripe/i)).toBeTruthy()
    expect(screen.queryByText(/loading the changes stripe published/i)).toBeNull()
  })
})
