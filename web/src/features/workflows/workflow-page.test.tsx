/**
 * The Solution Workflow's shape: a persistent fact rail beside two tabs over one run.
 *
 * The owner's sentence redefined what this screen is for — it is where a human intervenes in work
 * that is still in progress, not a record of what an agent did. So the structure under test is that
 * split: the run's identity holds still in the rail while the main pane carries `Activity` (the
 * turn-by-turn transcript, ending in the reply box) and `Findings` (the settled output).
 *
 * Structure and derivation only — heading order, which pane a region lands in, which tab is
 * selected. Never class names, never a snapshot: this console is being actively restyled and a
 * snapshot here would go red on every correct change.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { MemoryRouter, Route, Routes } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { WorkflowPage } from "@/features/workflows/workflow-page"

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useWorkflow: vi.fn(),
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

function mockWorkflow() {
  vi.mocked(queries.useWorkflow).mockReturnValue({
    data: mockState,
    isPending: false,
    isError: false,
    error: null,
    isSuccess: true,
    dataUpdatedAt: Date.now(),
    isFetching: false,
    refetch: vi.fn(),
  } as any)
}

/** Radix activates a tab on pointer-down, so a click alone leaves the selection where it was. */
function selectTab(name: string) {
  fireEvent.mouseDown(screen.getByRole("tab", { name }))
}

describe("the persistent fact rail", () => {
  it("carries the run's identity as a label/value list, ahead of the transcript", () => {
    mockWorkflow()

    const { container } = renderScreen("finding-123")

    const labels = Array.from(container.querySelectorAll("dt")).map((el) => el.textContent ?? "")
    expect(labels.length).toBeGreaterThan(0)
    for (const expected of ["Finding", "Repository", "Tier", "Strategy", "Waiting on"]) {
      expect(labels).toContain(expected)
    }
  })
})

describe("two tabs over one run", () => {
  it("offers Activity and Findings, with Activity selected on arrival", () => {
    mockWorkflow()

    renderScreen("finding-123")

    const tabs = screen.getAllByRole("tab")
    expect(tabs.map((tab) => tab.textContent)).toEqual(["Activity", "Findings"])
    expect(screen.getByRole("tab", { name: "Activity" }).getAttribute("aria-selected")).toBe("true")
  })

  it("reads transcript, then checkpoint timeline, then the reply box at the bottom of Activity", () => {
    mockWorkflow()

    renderScreen("finding-123")

    const panel = screen.getByRole("tabpanel")
    const headings = within(panel)
      .getAllByRole("heading")
      .map((el) => el.textContent ?? "")

    expect(headings.length).toBeGreaterThan(0)
    const sequence = headings.findIndex((text) => text.includes("Node by node"))
    const timeline = headings.findIndex((text) => text.includes("Checkpoint timeline"))
    const reply = headings.findIndex((text) => text.includes("Reply to this run"))

    expect(sequence).toBeGreaterThanOrEqual(0)
    expect(timeline).toBeGreaterThan(sequence)
    expect(reply).toBeGreaterThan(timeline)
  })

  it("swaps the transcript for the settled output when Findings is selected", () => {
    mockWorkflow()

    renderScreen("finding-123")
    selectTab("Findings")

    expect(screen.getByRole("heading", { name: "Settled output" })).not.toBeNull()
    expect(screen.queryByRole("heading", { name: "Reply to this run" })).toBeNull()
  })
})

describe("the sentences this screen may not lose", () => {
  it("keeps the Node-by-node intro describing what a standing does and does not say", () => {
    mockWorkflow()

    renderScreen("finding-123")

    expect(
      screen.getByText(
        "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing.",
      ),
    ).not.toBeNull()
  })

  it("keeps the timeline's own account of where its rows come from", () => {
    mockWorkflow()

    renderScreen("finding-123")

    expect(
      screen.getByText(
        "Assembled at read time from the checkpointer. Nothing writes a timeline row.",
      ),
    ).not.toBeNull()
  })
})
