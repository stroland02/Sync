/**
 * The dependency-graph screen on the chassis: what it says about itself in every state the read
 * can be in, and which of the three answered states it decided it is looking at.
 *
 * The assertions are the honesty ones this screen was built around — a count stated in every
 * state rather than only when the picture is capped, a missing index date rendered as absence
 * while a measured nought stays a nought, and three mutually exclusive states whose prose must
 * never appear together. Scope is `web/CLAUDE.md`'s: classification, derivation and structural
 * invariants, never class names and never a snapshot.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { RepositoryGraphResponse } from "@/api/types"
import { FORCE_MAP_LABEL } from "@/features/index-graph/force-map"
import { IndexGraphPage } from "@/features/index-graph/index-graph-page"

const { graph, fetchTopology } = vi.hoisted(() => ({ graph: vi.fn(), fetchTopology: vi.fn() }))

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRepositoryGraph: () => graph(),
}))

// The KPI strip and the coupling chord both read the topology through this one function. Held
// unresolved rather than answered: nothing below asserts on either panel, and a live fetch would
// put the network inside a unit test.
vi.mock("@/features/repositories/api-topology-card", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/features/repositories/api-topology-card")>()),
  fetchTopology,
}))

/** jsdom implements no `EventSource`, and this screen opens one on mount. */
class FakeEventSource {
  static last: FakeEventSource | null = null
  readonly url: string
  onerror: (() => void) | null = null
  private handlers = new Map<string, (event: MessageEvent) => void>()

  constructor(url: string) {
    this.url = url
    FakeEventSource.last = this
  }

  addEventListener(kind: string, handler: (event: MessageEvent) => void) {
    this.handlers.set(kind, handler)
  }

  close() {}
}

beforeEach(() => {
  FakeEventSource.last = null
  vi.stubGlobal("EventSource", FakeEventSource)
  fetchTopology.mockReturnValue(new Promise(() => {}))
})

// `globals` is unset in vitest.config.ts, so nothing tears the tree down between tests on its
// own. Without this every `not.toContain` below reads the previous test's DOM and passes for the
// wrong reason.
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  graph.mockReset()
})

const BINDING = {
  vendor_id: "stripe",
  operation_id: "charge",
  path: "src/pay.ts",
  line: 4,
  symbol: "charge",
  binding_rung: "static",
}

function response(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return {
    repo_id: "org/one",
    vendors: [],
    bindings: [],
    observed_bindings: [],
    off_path: { unresolved: 0, unattributed: 0 },
    rungs: [],
    indexed_at: null,
    total_bindings: 0,
    truncated: false,
    ...over,
  } as RepositoryGraphResponse
}

/** No call site was ever written here: `indexed_at` is null and the canvas is not evidence. */
function neverRecorded(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return response(over)
}

/** The index ran, wrote here, and holds no current call site — a measurement, not a silence. */
function indexedEmpty(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return response({ indexed_at: "2026-08-20T09:00:00Z", ...over })
}

/** The index ran and there is something to draw. */
function drawnGraph(over: Partial<RepositoryGraphResponse> = {}): RepositoryGraphResponse {
  return response({
    indexed_at: "2026-08-20T09:00:00Z",
    bindings: [BINDING],
    total_bindings: 1,
    ...over,
  } as Partial<RepositoryGraphResponse>)
}

function pending() {
  return { isPending: true, isError: false, isSuccess: false, data: undefined, refetch: vi.fn() }
}

function failed() {
  return {
    isPending: false,
    isError: true,
    isSuccess: false,
    data: undefined,
    error: new Error("no"),
    refetch: vi.fn(),
  }
}

function settled(data: RepositoryGraphResponse) {
  return { isPending: false, isError: false, isSuccess: true, data, refetch: vi.fn() }
}

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/repositories/org%2Fone/graph"]}>
        <Routes>
          <Route path="/repositories/:repoId/graph" element={<IndexGraphPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function statusText(): string {
  return document.querySelector('[data-band="status"]')?.textContent ?? ""
}

function contentText(): string {
  return document.querySelector('[data-band="content"]')?.textContent ?? ""
}

function segmentKinds(): string[] {
  return [...document.querySelectorAll("[data-status-segment]")].map(
    (segment) => segment.getAttribute("data-status-segment") ?? ""
  )
}

/** One figure segment as rendered, found by the label that opens it. */
function figure(label: string): string {
  const segment = [...document.querySelectorAll('[data-status-segment="figure"]')].find((node) =>
    node.textContent?.startsWith(label)
  )
  return segment?.textContent ?? ""
}

const NEVER_RECORDED_PROSE = "Nothing has ever been recorded for"
const INDEXED_EMPTY_PROSE = "Indexed, and holding no vendor call."

const ANSWERED: [string, RepositoryGraphResponse][] = [
  ["never recorded", neverRecorded()],
  ["indexed and empty", indexedEmpty()],
  ["drawn", drawnGraph()],
]

describe("the band answers in every state the read can be in", () => {
  it("names the read it is waiting on rather than publishing a blank strip", () => {
    graph.mockReturnValue(pending())
    renderScreen()

    expect(statusText()).toContain("asking for the indexed graph for org/one")
    expect(segmentKinds()).toEqual(["none"])
    // A count here would be one this screen invented: nothing has answered.
    expect(statusText()).not.toContain("Call sites drawn")
  })

  it("separates a graph that failed from one that has not answered", () => {
    graph.mockReturnValue(failed())
    renderScreen()

    expect(statusText()).toContain("the indexed graph for org/one did not answer")
    expect(statusText()).not.toContain("asking for the indexed graph")
  })
})

describe("the drawn count is stated in every answered state", () => {
  it.each(ANSWERED)("states it in the %s state, not only when the picture is capped", (_state, data) => {
    graph.mockReturnValue(settled(data))
    renderScreen()

    expect(segmentKinds()).toContain("records")
    expect(statusText()).toContain("Call sites drawn")
    // A count that appears only on truncation makes its absence mean "all of it" by inference.
    expect(statusText()).not.toContain("Call sites drawn —")
  })

  it("claims the whole set when the picture is the whole set", () => {
    graph.mockReturnValue(settled(drawnGraph()))
    renderScreen()

    expect(statusText()).toContain("This is all 1 call site.")
  })

  it("states a range over the set when the route capped the picture", () => {
    graph.mockReturnValue(settled(drawnGraph({ total_bindings: 900, truncated: true })))
    renderScreen()

    expect(statusText()).toContain("of 900 call sites")
    expect(statusText()).not.toContain("This is all")
  })
})

describe("the truncation caveat", () => {
  it("says why the rest are not drawn when the picture is capped", () => {
    graph.mockReturnValue(settled(drawnGraph({ total_bindings: 900, truncated: true })))
    renderScreen()

    expect(statusText()).toContain(
      "the picture stops being legible before the codebase stops having edges"
    )
    expect(segmentKinds()).toEqual(["records", "figure", "figure", "figure", "note"])
  })

  it("carries no caveat when the picture is not capped", () => {
    graph.mockReturnValue(settled(drawnGraph()))
    renderScreen()

    expect(statusText()).not.toContain("they are not drawn here")
    expect(segmentKinds()).toEqual(["records", "figure", "figure", "figure"])
  })
})

describe("a figure that has no answer against one that counted nought", () => {
  it("marks the missing index date absent while off path stays a counted nought", () => {
    graph.mockReturnValue(settled(neverRecorded()))
    renderScreen()

    // `formatTimestamp` answers null exactly when `indexed_at` is null. Rendering 0 or a date
    // here would be the collapse the scope beside it exists to refuse.
    expect(figure("Last indexed")).toContain("—")
    expect(figure("Last indexed")).not.toContain("0")

    expect(figure("Off path")).toContain("0")
    expect(figure("Off path")).not.toContain("—")
  })

  it("says which nothing the missing date is", () => {
    graph.mockReturnValue(settled(neverRecorded()))
    renderScreen()

    expect(figure("Last indexed")).toContain(
      "nothing records an index attempt, only its result"
    )
    expect(figure("Last indexed")).not.toContain("a retracted call site still proves it ran")
  })

  it("swaps to the staleness scope once a date exists", () => {
    graph.mockReturnValue(settled(indexedEmpty()))
    renderScreen()

    expect(figure("Last indexed")).toContain("when the index last wrote a call site here")
    expect(figure("Last indexed")).not.toContain("nothing records an index attempt")
  })
})

// `force-map` renders this when it IS mounted with nothing to draw. The label assertion alone
// cannot tell "the page did not mount the map" from "the map mounted and drew nothing", because
// an empty map has no labelled <svg> either -- so it passes with the state gate deleted.
const MAP_EMPTY = "Nothing was passed to this map."

describe("the three states are mutually exclusive and each keeps its prose", () => {
  it("refuses to call a never-recorded graph a finding about the codebase", () => {
    graph.mockReturnValue(settled(neverRecorded()))
    renderScreen()

    expect(contentText()).toContain(NEVER_RECORDED_PROSE)
    expect(contentText()).toContain("It is not a finding that this codebase calls no vendor.")
    expect(contentText()).not.toContain(INDEXED_EMPTY_PROSE)
    expect(screen.queryByLabelText(FORCE_MAP_LABEL)).toBeNull()
    expect(contentText()).not.toContain(MAP_EMPTY)
  })

  it("calls an indexed empty graph a measurement", () => {
    graph.mockReturnValue(settled(indexedEmpty()))
    renderScreen()

    expect(contentText()).toContain(INDEXED_EMPTY_PROSE)
    expect(contentText()).toContain("This is a measurement rather than an absence of one")
    expect(contentText()).not.toContain(NEVER_RECORDED_PROSE)
    expect(screen.queryByLabelText(FORCE_MAP_LABEL)).toBeNull()
    expect(contentText()).not.toContain(MAP_EMPTY)
  })

  it("draws the map and states neither nothing when there is something to draw", () => {
    graph.mockReturnValue(settled(drawnGraph()))
    renderScreen()

    expect(screen.getByLabelText(FORCE_MAP_LABEL)).toBeTruthy()
    expect(contentText()).not.toContain(NEVER_RECORDED_PROSE)
    expect(contentText()).not.toContain(INDEXED_EMPTY_PROSE)
  })

  it.each(ANSWERED)("reports off-path evidence in the %s state too", (_state, data) => {
    graph.mockReturnValue(settled(data))
    renderScreen()

    // A repository whose call sites were all retracted still holds observed traffic, so an
    // empty state that dropped this would understate what the graph is holding.
    expect(contentText()).toContain("Nothing is off the path here")
  })
})

describe("the stream's own count, on its own clock", () => {
  it("counts a stream that has said nothing as nought and names the window", () => {
    graph.mockReturnValue(settled(drawnGraph()))
    renderScreen()

    expect(figure("Indexed since you opened this")).toContain("0")
    expect(figure("Indexed since you opened this")).toContain("not the run's total")
    // Nothing to offer while the connection is live, so no band and no reserved height.
    expect(document.querySelector('[data-band="controls"]')).toBeNull()
  })

  it("names the count frozen and offers the settled read when the stream drops", () => {
    graph.mockReturnValue(settled(drawnGraph()))
    renderScreen()

    act(() => {
      FakeEventSource.last?.onerror?.()
    })

    expect(figure("Indexed since you opened this")).toContain(
      "frozen when the live connection ended"
    )
    const controls = document.querySelector('[data-band="controls"]')
    expect(controls?.textContent).toContain("Load the settled graph")
    // Zoom acts on the canvas's own transform and stays on the canvas, unlike the file tree's.
    expect(controls?.textContent).not.toContain("Zoom")
  })
})
