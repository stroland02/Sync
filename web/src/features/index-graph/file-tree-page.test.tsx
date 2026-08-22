/**
 * The file tree screen on the chassis: what it says about itself in every state the graph has.
 *
 * The assertions are the honesty ones the migration keeps going wrong on — a read that has not
 * answered against a read that answered nought, a whole-set claim over a picture the route
 * truncated, and a qualifier naming a census that did not run. Scope is
 * `.claude/rules/console-dev-loop.md`'s: structure and classification, never class names.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import { FileTreePage } from "@/features/index-graph/file-tree-page"
import type { RepositoryGraphResponse } from "@/api/types"

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  graph.mockReset()
})

const { graph, fetchFacts } = vi.hoisted(() => ({ graph: vi.fn(), fetchFacts: vi.fn() }))

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryGraph: () => graph(),
}))

vi.mock("@/features/repositories/codebase-facts-card", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/repositories/codebase-facts-card")>()),
  fetchFacts,
}))

function drawn(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return {
    repo_id: "org/one",
    vendors: [],
    bindings: [
      { vendor_id: "stripe", operation_id: "charge", path: "src/pay.ts", line: 4, symbol: "charge", binding_rung: "static" },
    ],
    observed_bindings: [],
    off_path: { unresolved: 0, unattributed: 0 },
    rungs: [],
    indexed_at: null,
    total_bindings: 1,
    truncated: false,
    ...over,
  } as RepositoryGraphResponse
}

function statusText(): string {
  return document.querySelector('[data-band="status"]')?.textContent ?? ""
}

/** The census read that never answers, so the band has no census to qualify anything with. */
const CENSUS_PENDING = Symbol("census pending")

function renderScreen(census: string | null | typeof CENSUS_PENDING = "git ls-files") {
  if (census === CENSUS_PENDING) fetchFacts.mockReturnValue(new Promise(() => {}))
  else
    fetchFacts.mockResolvedValue({
      repo_id: "org/one",
      facts:
        census === null
          ? null
          : {
              census,
              total_files: 2,
              binary_files: 0,
              languages: [],
              git: {
                commit_count: null,
                first_commit_at: null,
                last_commit_at: null,
                contributor_count: null,
              },
              dependencies: { by_ecosystem: {}, unreadable_manifests: [] },
              toolchain: [],
              computed_at: "2026-08-20T00:00:00Z",
            },
    })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fone/file-tree"]}>
        <Routes>
          <Route path="/repositories/:repoId/file-tree" element={<FileTreePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe("the file tree screen", () => {
  it("states why nothing counts while the graph is still being asked", () => {
    graph.mockReturnValue({ isPending: true, isError: false, isSuccess: false, data: undefined })
    renderScreen()

    expect(statusText()).toContain("asking for the file tree")
    // Not the same nothing as a graph that answered and held none.
    expect(statusText()).not.toContain("Call sites")
  })

  it("separates a graph that failed from one that has not answered", () => {
    graph.mockReturnValue({
      isPending: false,
      isError: true,
      isSuccess: false,
      data: undefined,
      error: new Error("nope"),
      refetch: vi.fn(),
    })
    renderScreen()

    expect(statusText()).toContain("the file tree did not answer")
  })

  it("prints a counted nought rather than the absence marker", () => {
    // The read succeeded and the answer is zero: a codebase whose call sites were searched for
    // and not found is a measurement, and the absence glyph here would draw it as one that
    // never happened.
    graph.mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: drawn({ bindings: [], total_bindings: 0, truncated: false }),
    })
    renderScreen()

    expect(statusText()).toContain("Call sites 0")
    expect(statusText()).not.toContain("Call sites —")
  })

  it("names the whole set only when the picture is the whole set", () => {
    graph.mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: drawn(),
    })
    renderScreen()

    expect(statusText()).toContain("every call site the index recorded for this codebase")
  })

  it("says the picture is a subset when the route truncated it", () => {
    graph.mockReturnValue({
      isPending: false,
      isError: false,
      isSuccess: true,
      data: drawn({ total_bindings: 900, truncated: true }),
    })
    renderScreen()

    expect(statusText()).toContain("of 900 the index holds")
    expect(statusText()).not.toContain("every call site the index recorded for this codebase")
  })

  it("hoists zoom and fold out of the canvas onto the controls band", () => {
    graph.mockReturnValue({ isPending: false, isError: false, isSuccess: true, data: drawn() })
    renderScreen()

    const controls = document.querySelector('[data-band="controls"]')
    expect(controls).not.toBeNull()
    expect(controls?.textContent).toContain("Zoom in")
    expect(controls?.textContent).toContain("Fit")
    // No depth control: the level of detail is derived from the window, never dialled.
    expect(controls?.textContent).not.toContain("Depth")
  })

  it("renders no controls band while there is no tree to drive", () => {
    graph.mockReturnValue({ isPending: true, isError: false, isSuccess: false, data: undefined })
    renderScreen()

    expect(document.querySelector('[data-band="controls"]')).toBeNull()
  })

  it("qualifies the census with git ls-files only when git ls-files ran", async () => {
    graph.mockReturnValue({ isPending: false, isError: false, isSuccess: true, data: drawn() })
    renderScreen()

    await screen.findByText(/git ls-files and a newline count over bytes/)
  })

  it("names the walk rather than git when the tracked-file list was not available", async () => {
    graph.mockReturnValue({ isPending: false, isError: false, isSuccess: true, data: drawn() })
    renderScreen("filesystem walk")

    await screen.findByText(/come from a filesystem walk rather than git ls-files/)
  })

  it("makes no census claim at all until the census read answers", () => {
    graph.mockReturnValue({ isPending: false, isError: false, isSuccess: true, data: drawn() })
    renderScreen(CENSUS_PENDING)

    expect(statusText()).not.toContain("git ls-files")
    expect(statusText()).not.toContain("filesystem walk")
  })
})
