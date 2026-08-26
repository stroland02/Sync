/**
 * The evidence pane: what the run read and did, and which nothing an empty run is.
 *
 * Structure and derivation only. The two claims worth a test are the two a tidy-up would break: an
 * empty node list is a measured nothing rather than a run that has not started, and the outcome
 * appears exactly once in this pane — it is the narrative's closing entry and nothing else on this
 * side may repeat it.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import * as queries from "@/api/queries"
import type { WorkflowNode, WorkflowState } from "@/api/types"
import { EvidencePane } from "@/features/workflows/evidence-pane"

vi.mock("@/api/queries", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/queries")>()),
  useRunActivity: vi.fn(),
}))

afterEach(cleanup)

function noActivity() {
  vi.mocked(queries.useRunActivity).mockReturnValue({
    data: { events: [] },
    isPending: false,
    isError: false,
  } as never)
}

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return { name: "locate", status: "done", standing: "ran", evidence: {}, ...over }
}

function state(nodes: WorkflowNode[], over: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes,
    outcome: null,
    abandon_reason: null,
    report_reason: null,
    thread_id: "finding-1:abc:0",
    generation_count: 1,
    repo_id: "org/svc",
    generations: [],
    ...over,
  }
}

function renderPane(data: WorkflowState) {
  noActivity()
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <EvidencePane repoId="org/one" findingId="finding-1" data={data} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("a run the checkpointer answered for with no nodes", () => {
  it("says that is a measured nothing rather than drawing an empty list", () => {
    const { container } = renderPane(state([]))

    expect(
      screen.getByText(
        "The checkpointer answered for this run and listed no nodes. That is a measured nothing, not a run that has not started.",
      ),
    ).not.toBeNull()
    // Before this guard an empty `nodes` array rendered a bare ordered list with a marker rule and
    // no explanation, which reads as a run that has not started. It is not one.
    expect(container.querySelector("ol")).toBeNull()
  })

  it("still opens with what arrived, because the route boundary is true either way", () => {
    renderPane(state([]))

    expect(screen.getByRole("heading", { name: "What arrived" })).not.toBeNull()
    expect(screen.getByText(/the checkpointer holds the run, not the finding/i)).not.toBeNull()
  })
})

describe("the outcome", () => {
  it("appears exactly once, as the narrative's closing entry", () => {
    // `SettledOutput` used to render `RunOutcome` a second time on the other side of the screen.
    // That was one fact at two weights and it is why that component was deleted rather than moved.
    const { container } = renderPane(
      state([node({ name: "locate" })], { outcome: "abandoned", abandon_reason: "not safe" }),
    )

    expect(within(container).getAllByText("Sync abandoned this run.")).toHaveLength(1)
  })
})

describe("the pane's reading order", () => {
  it("reads node by node, then the checkpoint timeline, then agent activity", () => {
    const { container } = renderPane(state([node({ name: "locate" })]))

    const headings = within(container)
      .getAllByRole("heading")
      .map((el) => el.textContent ?? "")

    const sequence = headings.findIndex((text) => text.includes("Node by node"))
    const timeline = headings.findIndex((text) => text.includes("Checkpoint timeline"))
    const activity = headings.findIndex((text) => text.includes("Agent activity"))

    expect(sequence).toBeGreaterThanOrEqual(0)
    expect(timeline).toBeGreaterThan(sequence)
    expect(activity).toBeGreaterThan(timeline)
  })

  it("accounts for the top bar's Generations figure instead of ending in a blank", () => {
    renderPane(state([node({ name: "locate" })]))

    expect(
      screen.getByText("This is the only generation the checkpointer holds for this finding."),
    ).not.toBeNull()
  })
})
