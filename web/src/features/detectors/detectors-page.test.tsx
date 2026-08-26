/**
 * The catalogue screen's structural invariants and its three empty branches.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots. What is held here is what a token swap cannot
 * produce and what a tidy-up most easily loses — the screen owning its own scrollbars, and each of
 * the three nothings saying which nothing it is rather than borrowing another's sentence.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { DetectorsPage } from "@/features/detectors/detectors-page"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const settled = (data: unknown) => ({ isPending: false, isError: false, isSuccess: true, data })
const failed = { isPending: false, isError: true, isSuccess: false, data: undefined, error: new Error("no") }

const { useDetectors, useOverview, useTickets } = vi.hoisted(() => ({
  useDetectors: vi.fn(),
  useOverview: vi.fn(),
  useTickets: vi.fn(),
}))
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useDetectors,
  useOverview,
  useTickets,
}))

function detectors(rows: { detector: string; total: number }[], by_rung: Record<string, number> = {}) {
  useDetectors.mockReturnValue(
    settled({
      repo_id: "org/one",
      detectors: rows.map((row) => ({
        ...row,
        by_rung: { static: row.total },
        by_claim: { "field-removed:/x": row.total },
        by_severity: { breaking: row.total },
      })),
      by_rung,
      total_open_findings: rows.reduce((sum, row) => sum + row.total, 0),
    }),
  )
  useTickets.mockReturnValue(settled({ tickets: [] }))
}

/** The corpus read answered, and says whether anything has ever read this repository. */
function corpus({ indexedAt, hasRun }: { indexedAt: string | null; hasRun: boolean }) {
  useOverview.mockReturnValue(
    settled({
      repo_id: "org/one",
      indexed_at: indexedAt,
      last_index_run: hasRun
        ? { started_at: null, finished_at: "2026-08-26T10:00:00+00:00", outcome: "completed", call_sites: 4 }
        : null,
      bindings_by_rung: {},
      severity_counts: {},
      vendors: [],
      total_findings: 0,
      total_findings_bound: 1000,
      total_findings_bound_reached: false,
    }),
  )
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fone/detectors"]}>
        <Routes>
          <Route path="/repositories/:repoId/detectors" element={<DetectorsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("the detector catalogue", () => {
  it("locks the screen, so its panes scroll rather than the page", () => {
    // `ScreenFrame layout="locked"` stamps `data-screen="locked"`, which is what flips `main` to
    // `overflow-hidden`. Measured 2026-08-26: eighteen of twenty-one screens were still `flow`,
    // one long scrolling column, which is how a console changes palette and stays the old console.
    detectors([{ detector: "a", total: 3 }], { static: 3, resolved: 0 })
    corpus({ indexedAt: "2026-08-26T10:00:00+00:00", hasRun: true })

    const { container } = renderPage()

    expect(container.querySelector('[data-screen="locked"]')).not.toBeNull()
  })

  it("says nothing has read the repository rather than that no detector found anything", () => {
    // The two states return the same empty list. A screen that renders never-indexed as a counted
    // zero tells the reader the corpus was checked, which is the console's own worst failure told
    // about itself.
    detectors([])
    corpus({ indexedAt: null, hasRun: false })

    renderPage()

    expect(screen.getByText(/Nothing has ever read this repository/i)).not.toBeNull()
    expect(screen.queryByText(/counted zero/i)).toBeNull()
  })

  it("calls an empty catalogue over a read corpus a counted zero, and says so", () => {
    detectors([])
    corpus({ indexedAt: "2026-08-26T10:00:00+00:00", hasRun: true })

    renderPage()

    expect(screen.getByText(/A counted zero/i)).not.toBeNull()
    expect(screen.queryByText(/Nothing has ever read this repository/i)).toBeNull()
  })

  it("refuses to choose between them while the corpus read has not answered", () => {
    detectors([])
    useOverview.mockReturnValue(failed)
    useTickets.mockReturnValue(settled({ tickets: [] }))

    renderPage()

    expect(screen.getByText(/did not answer/i)).not.toBeNull()
    expect(screen.queryByText(/A counted zero/i)).toBeNull()
    expect(screen.queryByText(/Nothing has ever read this repository/i)).toBeNull()
  })

  it("keeps the registry qualification on the empty screen, where it bites hardest", () => {
    // It was the intro's third paragraph once, so it appeared over a full screen and an empty one
    // alike. The empty screen is where "no detector raised anything" and "no detector is
    // installed" are hardest to tell apart.
    detectors([])
    corpus({ indexedAt: "2026-08-26T10:00:00+00:00", hasRun: true })

    renderPage()

    expect(screen.getByText(/keeps no registry of which detectors are installed/i)).not.toBeNull()
  })

  it("says the last index pass is unrecorded rather than printing a date it does not have", () => {
    detectors([{ detector: "a", total: 3 }], { static: 3 })
    corpus({ indexedAt: "2026-08-26T10:00:00+00:00", hasRun: false })

    renderPage()

    expect(screen.getByText(/no pass recorded/i)).not.toBeNull()
  })

  it("keeps a key the roll-up does not hold on screen rather than reading it as no selection", () => {
    detectors([{ detector: "a", total: 3 }], { static: 3 })
    corpus({ indexedAt: "2026-08-26T10:00:00+00:00", hasRun: true })

    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/repositories/org%2Fone/detectors?detector=gone"]}>
          <Routes>
            <Route path="/repositories/:repoId/detectors" element={<DetectorsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(screen.getByText(/No detector in this roll-up carries that name/i)).not.toBeNull()
    expect(screen.getByText(/the graph keeps no registry, so this screen cannot tell you which/i)).not.toBeNull()
  })
})
