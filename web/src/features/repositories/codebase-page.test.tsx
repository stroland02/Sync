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

// Three per-page breadcrumb tests stood here and in `vendor-page.test.tsx`, and went with the
// page header that carried them (`M14-W391`, owner decision 7). The console drew two trails for
// one question; the page's was the duplicate. What they guaranteed -- what contains what, ending
// on the subject -- is now asserted in `layouts/scope-switchers.test.tsx` against the trail that
// survived, which also carries the page's name and the page's only `h1`.
describe("CodebasePage's outbound links", () => {
  /**
   * `/repositories/:repoId/vendors` is routed and built, and nothing in the application linked to
   * it: the sidebar renders it as unlinkable text until an address binds `repoId`, which means it
   * was reachable only by typing the URL. This repository's own screen is where a link to it can
   * exist, because this is where `repoId` is already bound.
   */
  it("links to this repository's own vendors list", () => {
    renderCodebase("/repositories/org%2Fpayments")

    const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href"))
    expect(hrefs.length).toBeGreaterThan(0)
    expect(hrefs).toContain("/repositories/org%2Fpayments/vendors")
  })
})

describe("CodebasePage's scope", () => {
  /**
   * Four cards on this console have no importer. Two of them name this screen as their
   * destination — `RunsCard` and `CorpusSummaryCard` — and neither payload can be narrowed to a
   * repository: `RunRow` carries no `repo_id` and `/api/corpus` accepts no repository parameter
   * (`B149`). Mounting either would put every repository's runs under one repository's name,
   * which is the attribution `M14-W265` removed from the repository cards.
   *
   * The two loading strings are asserted rather than the panels' captions because a payload never
   * arrives under jsdom: mounting either card makes its own `what` visible immediately, so this
   * guard goes red on the mount rather than on the fetch.
   */
  it("renders no fleet-wide runs or repair record under one repository's name", () => {
    renderCodebase("/repositories/org%2Fpayments")

    // Non-vacuous: the screen rendered, and it states the scope every figure on it was computed in.
    expect(document.body.textContent).toContain("This repository alone.")

    expect(document.body.textContent).not.toContain("the fleet's runs")
    expect(document.body.textContent).not.toContain("One row per checkpoint thread")
    expect(document.body.textContent).not.toContain("the repair record")
    expect(document.body.textContent).not.toContain("Every repair attempt the graph has recorded")
  })
})
