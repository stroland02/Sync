/**
 * Corpus: the screen that mounts the corpus charts and the quality-axis ledger.
 *
 * **This file exists because of a guard that had to move.** `runs-page.test.tsx` carried
 * "mounts both of the cards that were built and mounted nowhere": Lane I finished
 * `AbandonReasonsCard` and `TierOutcomesCard`, tested them, and had no screen to put them on — and
 * a finished card nobody mounts is not shipped. Nothing else in the console catches that, because
 * both files typecheck, lint and pass their own tests while rendering on no screen at all.
 *
 * The Runs rebuild of 2026-08-26 locked that screen to the viewport and moved both cards here.
 * The Corpus rebuild later the same day locked *this* screen too, and the two cards became
 * `AbandonReasonsPane` and `TierOutcomesPane` beside the page that mounts them. The guard is
 * unchanged in substance and now anchors on all four panes rather than two: a dropped pane must
 * fail rather than pass quietly.
 *
 * Scope is `console-dev-loop.md`'s: structure, not class names and not a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PrecedentPage } from "@/features/dashboards/precedent-page"
import type { Axis } from "@/features/dashboards/axis-ledger"

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
  axes: [] as Axis[],
}

const UNMEASURED_AXIS: Axis = {
  name: "merge_rate_by_tier",
  display_name: "Merge Rate by Repair Tier",
  status: "unmeasured",
  has_samples: false,
  sample_count: 0,
  // The payload writes this word when nothing was sampled; the ledger must not render it as a
  // class of evidence that was found.
  provenance: "unmeasured",
  value: null,
  groups: {},
  unit: "ratio",
  denominator_description: "pull requests opened with decided outcome, grouped by repair tier",
}

function renderPage(axes: Axis[] = []) {
  useAbandonment.mockReturnValue({
    isPending: false,
    isError: false,
    isSuccess: true,
    data: { groups: [] },
  })
  const health = {
    ...HEALTH,
    summary: { ...HEALTH.summary, total_axes: axes.length, axes_unmeasured_count: axes.length },
    axes,
  }
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => health } as unknown as Response),
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
  it("mounts every pane the screen is composed of", async () => {
    const { container } = renderPage()

    // Migrated verbatim in substance from `runs-page.test.tsx` with the cards themselves. A
    // finished surface nobody mounts is not shipped, and this is the only assertion in the console
    // that would notice.
    await waitFor(() => {
      expect(container.textContent).toMatch(/abandon/i)
    })
    expect(container.textContent).toMatch(/tier/i)
    expect(screen.getByText("Quality axes")).toBeTruthy()
    expect(screen.getByText("What has been attempted, by change kind")).toBeTruthy()
  })

  it("keeps one attempt as one attempt, on the screen that now carries the corpus grain", async () => {
    const { container } = renderPage()

    // The grain claim travelled with the panes it qualifies: a corpus total is a count of
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

  /**
   * The structural difference between this rebuild and the reskin it replaced. Eighteen of
   * twenty-one screens rendered the default `flow` layout when the brief was written; a token swap
   * cannot change this attribute, which is why it is the assertion.
   */
  it("owns its own scrollbars rather than growing a page", async () => {
    const { container } = renderPage()

    await waitFor(() => {
      expect(screen.getByText("Quality axes")).toBeTruthy()
    })
    expect(container.querySelector('[data-band="content"]')?.getAttribute("data-screen")).toBe(
      "locked",
    )
  })

  /**
   * The refusal this screen exists to make. An axis with no sample is a measurement nobody could
   * take, and a competing tool would render it as nought, as a rate, or as a warning.
   */
  it("reports an unmeasured axis as unmeasured, never as nought and never as a rate", async () => {
    const { container } = renderPage([UNMEASURED_AXIS])

    await waitFor(() => {
      expect(screen.getByText("Merge Rate by Repair Tier")).toBeTruthy()
    })
    // A regex, because `Absent` prefixes its own glyph: the rendered cell reads "— not measured
    // yet", and the glyph is half the claim rather than decoration around it.
    expect(screen.getByText(/not measured yet/)).toBeTruthy()
    expect(container.textContent).not.toMatch(/%/)
    expect(container.textContent).toMatch(/measurement nobody could take/i)
  })

  /** A ratio is rendered with its denominator, always — as a column, never behind a tooltip. */
  it("puts the denominator beside the axis rather than behind a hover", async () => {
    renderPage([UNMEASURED_AXIS])

    await waitFor(() => {
      expect(
        screen.getByText("pull requests opened with decided outcome, grouped by repair tier"),
      ).toBeTruthy()
    })
  })

  /**
   * `provenance` arrives as the literal string "unmeasured" when nothing was sampled. Printing it
   * would name a class of evidence that was never found.
   */
  it("does not print the payload's placeholder provenance as a provenance", async () => {
    renderPage([UNMEASURED_AXIS])

    await waitFor(() => {
      expect(screen.getByText("Merge Rate by Repair Tier")).toBeTruthy()
    })
    expect(screen.queryByText("unmeasured")).toBeNull()
  })
})
