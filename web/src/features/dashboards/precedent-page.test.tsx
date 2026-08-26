/**
 * Corpus: the screen that now mounts the two corpus charts.
 *
 * **This file exists because of a guard that had to move.** `runs-page.test.tsx` carried
 * "mounts both of the cards that were built and mounted nowhere": Lane I finished
 * `AbandonReasonsCard` and `TierOutcomesCard`, tested them, and had no screen to put them on — and
 * a finished card nobody mounts is not shipped. Nothing else in the console catches that, because
 * both files typecheck, lint and pass their own tests while rendering on no screen at all.
 *
 * The Runs rebuild of 2026-08-26 locked that screen to the viewport and moved both cards here,
 * which is where they can be tall and where the corpus scope claim is already made. Without this
 * file the cards would have gone back to being mounted nowhere and passing everything — there was
 * no test for this page, which is exactly how that could have happened quietly.
 *
 * Scope is `console-dev-loop.md`'s: structure, not class names and not a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PrecedentPage } from "@/features/dashboards/precedent-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const { useAbandonment } = vi.hoisted(() => ({ useAbandonment: vi.fn() }))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useAbandonment,
}))

/** The health payload's shape, with nothing measured — this deployment's real state. */
const HEALTH = {
  summary: {
    total_runs: 0,
    distinct_findings: 0,
    pull_requests_opened: 0,
    pull_requests_merged: 0,
    findings_abandoned: 0,
    production_attempts: 0,
    rehearsal_attempts: 0,
    axes_measured_count: 0,
    axes_unmeasured_count: 0,
    total_axes: 0,
    has_any_samples: false,
  },
  axes: [],
}

function renderPage() {
  useAbandonment.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: { groups: [] },
  })
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => HEALTH } as unknown as Response),
  )
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fone/precedent"]}>
        <Routes>
          <Route path="/repositories/:repoId/precedent" element={<PrecedentPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("the corpus screen", () => {
  it("mounts both of the cards that were built and mounted nowhere", async () => {
    const { container } = renderPage()

    // Migrated verbatim from `runs-page.test.tsx` with the cards themselves. A finished card
    // nobody mounts is not shipped, and this is the only assertion in the console that would
    // notice.
    await waitFor(() => {
      expect(container.textContent).toMatch(/abandon/i)
    })
    expect(container.textContent).toMatch(/tier/i)
  })

  it("keeps one attempt as one attempt, on the screen that now carries the corpus grain", async () => {
    const { container } = renderPage()

    // The grain claim travelled with the cards it qualifies: a corpus total is a count of
    // attempts, larger than the finding count on every other screen, and neither is wrong.
    await waitFor(() => {
      expect(container.textContent).toMatch(/counts once/i)
    })
    expect(container.textContent).toMatch(/all workspaces/i)
  })

  it("names itself once, at the page step", async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1)
    })
  })
})
