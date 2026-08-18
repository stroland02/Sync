/**
 * Runs: what the remediation pipeline attempted, and the one thing this screen cannot narrow.
 *
 * Decision 30 gives Runs its own destination. What is asserted here is the part that is easy to
 * get wrong and impossible to see afterwards: **every figure on this screen is fleet-wide, and the
 * screen says so.** `migration_outcome` stores no `repo_id` at all — a schema decision that makes
 * the table safe to aggregate across customers (`src/sync/api/app.py:20-22`) — so `/api/runs` and
 * `/api/corpus/abandonment` cannot be narrowed to a workspace even in principle.
 *
 * That collides with the workspace mandate, which scopes every page and forbids a show-all. The
 * owner ruled to mount the cards with an explicit not-narrowed statement rather than hold two
 * finished cards off the ship or print fleet figures under one workspace's name. The statement is
 * therefore load-bearing rather than decorative, and it is what these tests guard: a later tidy
 * that deletes it turns this screen into exactly the false claim `codebases-panel` used to make.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants, never class names and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RunsPage } from "@/features/runs/runs-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRuns: () => settled({ items: [], total: 0 }),
  useAbandonment: () => settled({ groups: [] }),
}))

function renderRuns(entry = "/repositories/org%2Fone/runs") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      {/* Mounted under the real route pattern rather than bare: `RunsPage` reads `:repoId` from
          the address, and a bare mount silently hands it `undefined` and renders the 404 -- which
          passes nothing and looks like a page defect rather than a harness one. */}
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/repositories/:repoId/runs" element={<RunsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the runs screen", () => {
  it("mounts both of the cards that were built and mounted nowhere", () => {
    const { container } = renderRuns()

    // Lane I finished `AbandonReasonsCard` and `TierOutcomesCard`, tested them, and had no screen
    // to put them on. A finished card nobody mounts is not shipped, and nothing else in the console
    // would have caught that -- both files typecheck, lint and pass their own tests unmounted.
    expect(container.textContent).toMatch(/abandon/i)
    expect(container.textContent).toMatch(/tier/i)
  })

  it("states that its figures are not narrowed to the workspace, because they cannot be", () => {
    const { container } = renderRuns()
    const text = container.textContent ?? ""

    // The whole reason this screen is allowed to exist inside a scoped hierarchy. Deleting this
    // sentence leaves a fleet-wide count sitting under one workspace's breadcrumb, which is the
    // `codebases-panel` defect exactly -- one figure printed under every card it did not describe.
    expect(text).toContain("not narrowed to this workspace")
  })

  it("says why it cannot be narrowed, so the limit reads as a schema fact and not an oversight", () => {
    const { container } = renderRuns()
    const text = container.textContent ?? ""

    // "This number is fleet-wide" invites somebody to file a bug asking for a repo filter. Naming
    // the cause closes that: `migration_outcome` carries no repository at all, deliberately, and
    // that is what makes the corpus safe to aggregate across customers in the first place.
    expect(text).toContain("migration_outcome")
    expect(text).toMatch(/no repository|records no repository|stores no repository/i)
  })

  it("carries no page header, because density is dense", () => {
    renderRuns()

    // Owner answer 7, applied to every screen. The breadcrumb and the rail name this destination.
    expect(screen.queryByRole("heading", { level: 1 })).toBeNull()
  })

  it("keeps one attempt as one attempt, and never reads a row count as a finding count", () => {
    const { container } = renderRuns()
    const text = container.textContent ?? ""

    // `CLAUDE.md`'s grain rule, on the screen that is most likely to break it: one
    // `migration_outcome` row is one *attempt*, not one finding. A finding retried three times is
    // three rows here and one finding everywhere else, and a reader comparing this screen against
    // the Overview will otherwise conclude one of them is wrong.
    expect(text).toMatch(/attempt/i)
    expect(text).toContain("counts once")
  })
})
