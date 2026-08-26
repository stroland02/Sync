/**
 * The Solution Workflow's shape: two panes over one run, both visible at once, no tabs.
 *
 * **This file used to test a different screen.** Three of its cases described a tab strip and a
 * fourth a narrow fact rail; the screen is now a locked evidence/remediation split, and the
 * question it answers — *does the evidence support the change?* — needs both halves on screen
 * together rather than one behind a control. The concerns those cases carried did not go with
 * them: the rail's facts are held by `run-identity-header.test.tsx`, the settled output's
 * confidence refusal by `remediation-pane.test.tsx`, and the tab strip's absence is now asserted
 * directly, because a controls band on a screen with nothing to narrow is the regression.
 *
 * Structure and derivation only — which pane a region lands in, in what order, and what the status
 * band says. Never class names, never a snapshot: this console is being actively restyled and a
 * snapshot here would go red on every correct change.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { PatchResponse, WorkflowState } from "@/api/types"
import { WorkflowPage } from "@/features/workflows/workflow-page"

// Both panes render at once now, so both of their queries fire on every mount. Before the rebuild
// only `useWorkflow` needed a stub because the remediation half was behind a tab.
vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useWorkflow: vi.fn(),
  usePatch: vi.fn(),
  useRunActivity: vi.fn(),
}))

afterEach(cleanup)

function renderScreen(findingId = "finding-123") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/repositories/org%2Fone/findings/${findingId}/workflow`]}>
        <Routes>
          <Route
            path="/repositories/:repoId/findings/:findingId/workflow"
            element={<WorkflowPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const mockState: WorkflowState = {
  nodes: [
    {
      name: "locate",
      status: "done",
      standing: "ran",
      evidence: { tier: "Tier 1" },
      first_seen_at: "2026-08-08T10:00:00.000000+00:00",
      last_seen_at: "2026-08-08T10:00:05.000000+00:00",
    },
    { name: "prepare", status: "done", standing: "ran", evidence: {} },
    { name: "patch", status: "current", standing: "due", evidence: {} },
    { name: "static_verify", status: "pending", standing: "not_reached_yet", evidence: {} },
    { name: "replay", status: "pending", standing: "not_reached_yet", evidence: {} },
    { name: "push_branch", status: "pending", standing: "not_reached_yet", evidence: {} },
    { name: "await_ci", status: "pending", standing: "not_reached_yet", evidence: {} },
    { name: "open_pr", status: "pending", standing: "not_reached_yet", evidence: {} },
  ],
  outcome: null,
  abandon_reason: null,
  report_reason: null,
  thread_id: "finding-123:abc:0",
  generation_count: 1,
  repo_id: "org/svc",
  generations: [],
}

const mockPatch: PatchResponse = {
  diff: null,
  strategy: null,
  rationale: null,
  stat: null,
  target: { repo_id: "org/svc", branch: null, pr_url: null, pr_number: null },
  absent_because: "This run has not written a patch yet.",
}

function mockPanes() {
  vi.mocked(queries.usePatch).mockReturnValue({
    data: mockPatch,
    isPending: false,
    isError: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  } as never)
  vi.mocked(queries.useRunActivity).mockReturnValue({
    data: { events: [] },
    isPending: false,
    isError: false,
  } as never)
}

function mockWorkflow(over: Partial<WorkflowState> = {}) {
  mockPanes()
  vi.mocked(queries.useWorkflow).mockReturnValue({
    data: { ...mockState, ...over },
    isPending: false,
    isError: false,
    error: null,
    isSuccess: true,
    dataUpdatedAt: Date.now(),
    isFetching: false,
    refetch: vi.fn(),
  } as never)
}

function headingsIn(name: string): string[] {
  return within(screen.getByRole("region", { name }))
    .getAllByRole("heading")
    .map((el) => el.textContent ?? "")
}

function orderIn(name: string, expected: string[]): void {
  const headings = headingsIn(name)
  const positions = expected.map((text) => headings.findIndex((h) => h.includes(text)))
  expect(positions.every((index) => index >= 0)).toBe(true)
  expect([...positions].sort((a, b) => a - b)).toEqual(positions)
}

describe("two panes over one run", () => {
  it("renders evidence and remediation at once, each addressable as a region", () => {
    mockWorkflow()

    renderScreen()

    expect(screen.getByRole("region", { name: "Evidence" })).not.toBeNull()
    expect(screen.getByRole("region", { name: "Remediation" })).not.toBeNull()
  })

  it("reads node by node, then the checkpoint timeline, then agent activity on the left", () => {
    mockWorkflow()

    renderScreen()

    orderIn("Evidence", ["Node by node", "Checkpoint timeline", "Agent activity"])
  })

  it("reads the change, then what checked it, then where it went, then the reviewer's turn", () => {
    mockWorkflow()

    renderScreen()

    orderIn("Remediation", [
      "The change this run wrote",
      "What checked it",
      "Where it went",
      "A reviewer's turn",
    ])
  })

  it("puts the reply box in the remediation pane, reachable without pressing anything", () => {
    // It used to sit at the bottom of an Activity tab, so reading the patch and replying to the run
    // were two different views of one screen.
    mockWorkflow()

    renderScreen()

    const remediation = screen.getByRole("region", { name: "Remediation" })
    expect(within(remediation).getByRole("heading", { name: "Reply to this run" })).not.toBeNull()
    expect(screen.queryAllByRole("tab")).toHaveLength(0)
  })
})

describe("the screen's bands", () => {
  function band(container: HTMLElement, name: "controls" | "status"): HTMLElement | null {
    return container.querySelector(`[data-band="${name}"]`)
  }

  it("reserves no controls band on a loaded run, because nothing here narrows anything", () => {
    // The tab strip was the band's only occupant. `ScreenFrame` omits the element entirely rather
    // than drawing an empty bar, and a bar rendered to say "there is nothing here" is chrome
    // asserting an absence nobody asked about.
    mockWorkflow()

    const { container } = renderScreen()

    expect(band(container, "controls")).toBeNull()
  })

  it("counts the graph's nodes and the timeline's entries, and says what the timeline omits", () => {
    mockWorkflow()

    const { container } = renderScreen()

    // One node in `mockState` stamped a checkpoint and the run has no outcome, so the timeline
    // holds one entry against eight nodes. The seven without a stamp are a stated absence rather
    // than a shorter list a reader is left to subtract.
    const text = band(container, "status")?.textContent ?? ""
    expect(text).toMatch(/Nodes\s*8\b/)
    expect(text).toMatch(/Timeline entries\s*1\b/)
    expect(text).toContain(
      "7 nodes wrote no checkpoint timestamp and have no entry — absence, not zero",
    )
  })

  it("carries the run's own disposition as a segment, where the reference draws a severity chip", () => {
    // The finding's change kind is not on this payload and fetching it would put the header's
    // focal point behind a route that 404s for every patched or abandoned finding. The outcome is
    // a value from a closed vocabulary, legible without colour, and permanently visible.
    mockWorkflow({ outcome: "opened" })

    const { container } = renderScreen()

    const text = band(container, "status")?.textContent ?? ""
    expect(text).toMatch(/Outcome\s*opened/)
    expect(text).toContain("the checkpointer's last word")
  })

  it("says which nothing it is while the run has not answered, rather than a blank strip", () => {
    mockPanes()
    vi.mocked(queries.useWorkflow).mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      error: null,
      isSuccess: false,
      dataUpdatedAt: 0,
      isFetching: true,
      refetch: vi.fn(),
    } as never)

    const { container } = renderScreen()

    expect(band(container, "status")?.textContent ?? "").toContain(
      "asking the checkpointer for this run",
    )
    expect(band(container, "controls")).toBeNull()
  })
})

describe("the sentences this screen may not lose", () => {
  it("keeps the Node-by-node intro describing what a standing does and does not say", () => {
    mockWorkflow()

    renderScreen()

    expect(
      screen.getByText(
        "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing.",
      ),
    ).not.toBeNull()
  })

  it("keeps the timeline's own account of where its rows come from", () => {
    mockWorkflow()

    renderScreen()

    expect(
      screen.getByText(
        "Assembled at read time from the checkpointer. Nothing writes a timeline row.",
      ),
    ).not.toBeNull()
  })
})
