/**
 * Runs: what the remediation pipeline attempted, and the one thing this screen cannot narrow.
 *
 * Decision 30 gives Runs its own destination. What is asserted here is the part that is easy to
 * get wrong and impossible to see afterwards: **every figure on this screen is fleet-wide, and the
 * screen says so.** The route can be narrowed to a repository (`sync.dashboard.fleet.runs` accepts
 * `repo_id`, B149) and this screen chooses not to be, because `repo_id` is null on any run whose
 * finding the graph no longer holds — so a narrowed page would silently drop exactly the runs whose
 * finding was patched or retracted.
 *
 * That collides with the workspace mandate, which scopes every page and forbids a show-all. The
 * owner ruled to state the scope on screen rather than print fleet figures under one workspace's
 * name. The statement is therefore load-bearing rather than decorative, and it is what these tests
 * guard: a later tidy that deletes it turns this screen into exactly the false claim
 * `codebases-panel` used to make.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants, never class names and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { RunRow, RunsPage as RunsPagePayload } from "@/api/types"
import { RunsPage } from "@/features/runs/runs-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const OPEN_RUN: RunRow = {
  thread_id: "finding-open-1:prod-run-9:0",
  finding_id: "finding-open-1",
  finding_name: "stripe-postcharges-4b1c9e",
  liveness: null,
  last_heartbeat_at: null,
  repo_id: "org/one",
  run_id: "prod-run-9",
  current_node: null,
  outcome: "opened",
  abandon_reason: null,
  last_checkpoint_at: "2026-08-05T12:00:00Z",
}

const state: { items: RunRow[] } = { items: [] }

const settled = (data: unknown) => ({
  isPending: false,
  isError: false,
  isSuccess: true,
  isFetching: false,
  dataUpdatedAt: 0,
  data,
})

function payload(items: RunRow[]): RunsPagePayload {
  return {
    items,
    total: items.length,
    next_offset: null,
    by_disposition: {},
    unfiltered_total: items.length,
  }
}

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRuns: () => settled(payload(state.items)),
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
    </QueryClientProvider>,
  )
}

describe("the runs screen", () => {
  /**
   * The "mounts both of the cards that were built and mounted nowhere" guard moved rather than
   * retired.
   *
   * `AbandonReasonsPane` and `TierOutcomesPane` no longer render here: the Runs rebuild locks this
   * screen to the viewport and two chart cards under a stream are two things a reader would have to
   * scroll a locked screen to reach. They moved to Corpus, which is not locked and already carries
   * the corpus scope claim, so its `/abandon/i` and `/tier/i` assertions moved with them to
   * `features/dashboards/precedent-page.test.tsx`.
   *
   * **The concern it recorded is unchanged and still met.** Lane I finished both cards, tested
   * them, and had no screen to put them on; a finished card nobody mounts is not shipped, and
   * nothing else in the console catches that, because both files typecheck, lint and pass their own
   * tests unmounted. The guard now sits over the screen that mounts them.
   */

  it("states that its figures are not narrowed to the workspace, because they cannot be honestly", () => {
    const { container } = renderRuns()
    const text = container.textContent ?? ""

    // The claim, not its wording. It moved from a bordered paragraph to a `ScopeChip` reading
    // "all workspaces" in the 2026-08-19 sweep, and pinning the old sentence failed a change
    // that broke nothing -- which `test-discipline.md` names directly: assert the property the
    // code promises, never an incidental string.
    //
    // What must hold is that a reader who never hovers can tell the figures are not this
    // workspace's. Deleting that leaves a fleet-wide count under one workspace's breadcrumb,
    // which is the `codebases-panel` defect exactly. The chip survived the rebuild by moving into
    // the controls band rather than leaving with the corpus cards.
    expect(text).toMatch(/all workspaces|not narrowed to this workspace/i)
  })

  it("names itself once, at the page step", () => {
    renderRuns()

    // Owner answer 7 -- the breadcrumb and the rail name this destination, so the page need not --
    // is superseded by the Stitch specification of 2026-08-24, which titles every screen. The
    // trail rendered that name as an `h1` at 13px, under the 18px `h2` of its own sections, and
    // an inverted hierarchy is what actually retired the ruling. One heading still, relocated.
    const headings = screen.getAllByRole("heading", { level: 1 })
    expect(headings).toHaveLength(1)
    expect(headings[0].className).toContain("text-page")
  })

  it("keeps one attempt as one attempt, and never reads a row count as a finding count", () => {
    const { container } = renderRuns()
    const text = container.textContent ?? ""

    // `CLAUDE.md`'s grain rule, on the screen that is most likely to break it: one checkpoint
    // thread is one *attempt*, not one finding. A finding retried three times is three rows here
    // and one finding everywhere else, and a reader comparing this screen against the Overview
    // will otherwise conclude one of them is wrong.
    //
    // Asserted as the property rather than the sentence: one row is one attempt, and it counts
    // once as a finding. The claim moved into the controls band with the rebuild; the grain did
    // not move at all. If this goes red the placement is what is wrong, not the test.
    expect(text).toMatch(/attempt/i)
    expect(text).toMatch(/counts once/i)
  })
})

describe("the run record drawer", () => {
  it("opens the run the address names, and links it to a workspace-scoped workflow", () => {
    state.items = [OPEN_RUN]
    renderRuns("/repositories/org%2Fone/runs?runs_open=finding-open-1%3Aprod-run-9%3A0")

    // Ported from the deleted `runs-table.test.tsx`: `/findings/:id/workflow` is not a route the
    // router serves -- the workflow lives under `/repositories/:repoId/findings/:findingId/
    // workflow`. The payload has carried `repo_id` all along; only the TypeScript type omitted it,
    // so the link was built without it. The link moved from the table cell into this drawer when
    // the stream took one line per row, and the guard moved with it.
    const link = screen.getByRole("link", { name: /workflow/i })
    const href = link.getAttribute("href") ?? ""
    expect(href).toContain("/repositories/")
    expect(href).toContain("/workflow")
  })

  it("states the finding without linking when the run names no repository", () => {
    state.items = [{ ...OPEN_RUN, repo_id: null }]
    renderRuns("/repositories/org%2Fone/runs?runs_open=finding-open-1%3Aprod-run-9%3A0")

    // A run whose repository is unknown cannot be given a scoped address, and guessing one would
    // send a reader to another workspace's finding. The id is still shown -- absence of a link is
    // not absence of the fact.
    expect(screen.queryByRole("link", { name: /workflow/i })).toBeNull()
    expect(screen.getByText("finding-open-1")).toBeTruthy()
  })

  it("says the selected run is not on this page rather than closing itself", () => {
    state.items = [OPEN_RUN]
    renderRuns("/repositories/org%2Fone/runs?runs_open=finding-gone-7%3Aprod-run-2%3A0")

    // A bookmarked address, or a reader who paged while a row was open. Dropping a selection the
    // URL still carries makes the address and the screen disagree, and the reader is left believing
    // they closed something they did not.
    expect(screen.getByText(/not on this page/i)).toBeTruthy()
  })
})
