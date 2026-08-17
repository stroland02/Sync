/**
 * The route's region order, against mock screen 07's two-pane trajectory shape.
 *
 * The rail carries the run facts and then the sequence, under a "Node by node" panel; the content
 * column carries the fetched-at line, then the activity timeline, then any superseded generations.
 * This only asserts structure — heading order and which column a region lands in — never styling,
 * per `.claude/rules/console-dev-loop.md`'s scope for this runner.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen } from "@testing-library/react"
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
      <MemoryRouter initialEntries={[`/findings/${findingId}/workflow`]}>
        <Routes>
          <Route path="/findings/:findingId/workflow" element={<WorkflowPage />} />
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

describe("WorkflowPage's region order", () => {
  it("reads page header, then Node by node, then Activity, top to bottom", () => {
    mockWorkflow()

    const { container } = renderScreen("finding-123")

    const headings = Array.from(container.querySelectorAll("h1, h2")).map(
      (el) => el.textContent ?? "",
    )
    const headerIndex = headings.findIndex((text) => text.includes("Run 1"))
    const nodeByNodeIndex = headings.findIndex((text) => text.includes("Node by node"))
    const activityIndex = headings.findIndex((text) => text.includes("Activity"))

    expect(headerIndex).toBeGreaterThanOrEqual(0)
    expect(nodeByNodeIndex).toBeGreaterThan(headerIndex)
    expect(activityIndex).toBeGreaterThan(nodeByNodeIndex)
  })

  it("renders the run facts in the rail before the node sequence", () => {
    mockWorkflow()

    const { container } = renderScreen("finding-123")

    const marks = Array.from(container.querySelectorAll("dt, h2, h3")).map(
      (el) => el.textContent ?? "",
    )
    const findingFactIndex = marks.findIndex((text) => text.includes("Finding"))
    const nodeByNodeIndex = marks.findIndex((text) => text.includes("Node by node"))
    const firstNodeIndex = marks.findIndex((text) => text === "locate")

    expect(findingFactIndex).toBeGreaterThanOrEqual(0)
    expect(nodeByNodeIndex).toBeGreaterThan(findingFactIndex)
    expect(firstNodeIndex).toBeGreaterThan(nodeByNodeIndex)
  })

  it("keeps the Node-by-node intro sentence describing what a standing does and does not say", () => {
    mockWorkflow()

    renderScreen("finding-123")

    expect(
      screen.getByText(
        "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing.",
      ),
    ).not.toBeNull()
  })
})
