/**
 * The Findings tab: what this run settled, and what the payload cannot settle.
 *
 * Structural and derivational only. The claim under test is the split — which nodes are transcript
 * and which are settled output — plus the sentence naming the three things a reference incident
 * view carries here that our payload does not hold.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { SETTLED_NODES, SettledOutput } from "@/features/workflows/settled-output"

afterEach(cleanup)

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return { name: "locate", status: "done", standing: "ran", evidence: {}, ...over }
}

function state(nodes: WorkflowNode[], over: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes,
    outcome: "opened",
    abandon_reason: null,
    report_reason: null,
    thread_id: "finding-1:abc:0",
    generation_count: 1,
    repo_id: "org/svc",
    generations: [],
    ...over,
  }
}

function renderTab(data: WorkflowState) {
  return render(
    <MemoryRouter>
      <SettledOutput findingId="finding-1" state={data} />
    </MemoryRouter>,
  )
}

describe("what the Findings tab counts as settled", () => {
  it("names a closed set of nodes rather than deciding per render", () => {
    expect(SETTLED_NODES.length).toBeGreaterThan(0)
    expect(SETTLED_NODES).toContain("open_pr")
    expect(SETTLED_NODES).not.toContain("locate")
  })

  it("renders a card per settled node that produced evidence, with the node named", () => {
    renderTab(
      state([
        node({ name: "static_verify", evidence: { verify_ok: true } }),
        node({ name: "open_pr", evidence: { pr_number: 4120 } }),
      ]),
    )

    const cards = screen.getAllByRole("heading", { name: /static_verify|open_pr/ })
    expect(cards.length).toBe(2)
  })

  it("leaves the transcript nodes to the Activity tab", () => {
    renderTab(
      state([
        node({ name: "locate", evidence: { tier: "Tier 2" } }),
        node({ name: "open_pr", evidence: { pr_number: 4120 } }),
      ]),
    )

    expect(screen.queryByRole("heading", { name: "locate" })).toBeNull()
    expect(screen.getByRole("heading", { name: "open_pr" })).not.toBeNull()
  })

  it("states the absence when no settled node has produced anything, rather than showing an empty list", () => {
    renderTab(state([node({ name: "locate", evidence: { tier: "Tier 2" } })], { outcome: null }))

    expect(screen.getByText(/has settled nothing yet/i)).not.toBeNull()
  })
})

describe("what this payload cannot settle", () => {
  it("says plainly that it carries no summary, no root cause and no diff", () => {
    renderTab(state([node({ name: "open_pr", evidence: { pr_number: 4120 } })]))

    const sentence = screen.getByText(/no authored summary, no root-cause statement and no diff/i)
    expect(sentence).not.toBeNull()
  })

  it("points at the finding for the provenance rung, which this database does not hold", () => {
    renderTab(state([node({ name: "open_pr", evidence: { pr_number: 4120 } })]))

    expect(screen.getByText(/provenance rung/i)).not.toBeNull()
  })
})
