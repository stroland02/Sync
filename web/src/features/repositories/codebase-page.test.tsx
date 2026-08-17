/**
 * A level says what contains it.
 *
 * The companion to `vendors/vendor-page.test.tsx`: these were the two routes of nine that rendered
 * no breadcrumb. Structure and order are what is asserted, never markup.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { CodebasePage } from "@/features/repositories/codebase-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

// Only the one hook this page calls directly is replaced; the rest of the module is kept, because
// `lib/routes.ts` reaches other exports through the same import graph.
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryObserved: () => ({ isPending: true, isError: false, data: undefined }),
}))

function renderCodebase(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/repositories/:repoId" element={<CodebasePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("CodebasePage's breadcrumb", () => {
  it("names what contains this repository, ending on the repository itself", () => {
    renderCodebase("/repositories/org%2Fpayments")

    const trail = screen.getByLabelText("Breadcrumb")
    expect(trail.textContent).toContain("Repositories")
    expect(trail.querySelector('[aria-current="page"]')?.textContent).toBe("org/payments")
  })
})
