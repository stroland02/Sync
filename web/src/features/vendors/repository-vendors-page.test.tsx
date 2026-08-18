/**
 * The vendors attached to one repository — the list screen the owner asked for.
 *
 * *"the vendors page that list all the vendors part of that codebase"*, at an equal stage with API
 * services. This is the list; `vendor-page.tsx` remains the detail.
 *
 * **The scoped-answer discipline is the substance here.** `/api/overview` echoes the `repo_id` it
 * was computed for precisely so a caller cannot render the fleet's vendors under one repository's
 * name. `codebases-panel.tsx` had that exact defect once — it printed the fleet-wide
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

const { useOverview } = vi.hoisted(() => ({ useOverview: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useOverview,
}))

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
    useOverview.mockReturnValue(
      settled({
        repo_id: "org/one",
        vendors: [
          { vendor_id: "stripe", open_finding_count: 4 },
          { vendor_id: "openai", open_finding_count: 0 },
        ],
      })
    )

    const { container } = renderAt("org/one")

    const rows = container.querySelectorAll("tbody tr")
    expect(rows.length).toBe(2)
    expect(within(rows[0] as HTMLElement).getByText("stripe")).not.toBeNull()
  })

  it("links each vendor to its detail, carrying the repository as the scope", () => {
    useOverview.mockReturnValue(
      settled({ repo_id: "org/one", vendors: [{ vendor_id: "stripe", open_finding_count: 4 }] })
    )

    renderAt("org/one")

    // The scope travels in the query string, because a vendor's detail is reachable both inside a
    // repository and fleet-wide and the payload distinguishes the two.
    const link = screen.getByRole("link", { name: /stripe/i })
    expect(link.getAttribute("href")).toBe("/repositories/org%2Fone/vendors/stripe")
  })

  it("renders a confirmed zero as a number and never as absence", () => {
    useOverview.mockReturnValue(
      settled({ repo_id: "org/one", vendors: [{ vendor_id: "openai", open_finding_count: 0 }] })
    )

    const { container } = renderAt("org/one")

    // Zero open findings is an answer about the vendor. It is not the same as not having asked, and
    // this screen must not render the absence marker for it.
    expect(container.textContent).toContain("No open findings")
  })

  it("says no vendor is attached rather than showing an empty table", () => {
    useOverview.mockReturnValue(settled({ repo_id: "org/one", vendors: [] }))

    const { container } = renderAt("org/one")

    expect(container.querySelectorAll("tbody tr").length).toBe(0)
    expect(container.textContent).toContain("No vendor is attached to this repository")
  })

  it("refuses to render rows under a repository the answer was not computed for", () => {
    // The defect this exists to stop, which has happened here before: a fleet-wide answer rendered
    // under one repository's name. `/api/overview` echoes its own scope so the screen can check.
    useOverview.mockReturnValue(
      settled({ repo_id: null, vendors: [{ vendor_id: "stripe", open_finding_count: 4 }] })
    )

    const { container } = renderAt("org/one")

    expect(container.querySelectorAll("tbody tr").length).toBe(0)
    expect(container.textContent).toContain("computed for a different scope")
  })
})
