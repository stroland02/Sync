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
  useRuns: () => settled({ items: [], total: 0, next_offset: null, by_disposition: {}, unfiltered_total: 0 }),
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

    // The claim, not its wording. It moved from a bordered paragraph to a `ScopeChip` reading
    // "all workspaces" in the 2026-08-19 sweep, and pinning the old sentence failed a change
    // that broke nothing -- which `test-discipline.md` names directly: assert the property the
    // code promises, never an incidental string.
    //
    // What must hold is that a reader who never hovers can tell the figures are not this
    // workspace's. Deleting that leaves a fleet-wide count under one workspace's breadcrumb,
    // which is the `codebases-panel` defect exactly.
    expect(text).toMatch(/all workspaces|not narrowed to this workspace/i)
  })

  /**
   * The "why it cannot be narrowed" guard retired with the owner's ⓘ ruling of 2026-08-19.
   *
   * It required `migration_outcome` and "stores no repository" in the rendered text. That is the
   * *argument* for the scope rather than the scope itself, and the amendment moves exactly that
   * behind the hover: the claim stays visible in the fewest honest words, the reasoning does not.
   *
   * **The concern it recorded is still met.** Its comment said a bare "this is fleet-wide"
   * invites a bug report asking for a repository filter — the `ScopeChip`'s hover answers that,
   * naming the table and the schema decision, one hover away rather than one paragraph down. The
   * claim itself is asserted above.
   */

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
    // Asserted as the property rather than the sentence: one row is one attempt, and it counts
    // once as a finding. The wording moved in the sweep; the grain did not.
    expect(text).toMatch(/attempt/i)
    expect(text).toMatch(/counts once/i)
  })
})
