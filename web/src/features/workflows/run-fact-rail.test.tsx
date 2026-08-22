/**
 * The persistent fact rail: the run's identity, and the three things it cannot do.
 *
 * Structure and derivation only — which facts are listed, in what order, and which of them the
 * payload can actually answer. Never class names, never a snapshot.
 *
 * The rail is where a reference incident view puts its confidence scalar. Ours puts the tier the
 * cascade routed to and the strategy that produced the edit — two recorded values from the run's
 * own evidence — and renders the absence marker for the vendor, which this payload does not carry
 * at all.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { RunFactRail } from "@/features/workflows/run-fact-rail"

afterEach(cleanup)

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return { name: "locate", status: "done", standing: "ran", evidence: {}, ...over }
}

function state(over: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes: [
      node({
        name: "locate",
        evidence: { tier: "Tier 2" },
        first_seen_at: "2026-08-08T10:00:00+00:00",
        last_seen_at: "2026-08-08T10:00:20+00:00",
      }),
      node({
        name: "patch",
        status: "current",
        standing: "due_again",
        evidence: { attempt_strategy: "model" },
        first_seen_at: "2026-08-08T10:01:00+00:00",
        last_seen_at: "2026-08-08T10:02:00+00:00",
      }),
    ],
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

function renderRail(data: WorkflowState | undefined) {
  return render(
    <MemoryRouter>
      <RunFactRail repoId="org/one" findingId="finding-1" data={data} failure={null} />
    </MemoryRouter>,
  )
}

function labels(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("dt")).map((el) => el.textContent ?? "")
}

describe("the run's fact rail", () => {
  it("lists the run's identity, in the order a reviewer reads it", () => {
    const { container } = renderRail(state())

    const listed = labels(container)
    expect(listed.length).toBeGreaterThan(0)
    expect(listed).toEqual([
      "Finding",
      "Vendor",
      "Repository",
      "Tier",
      "Strategy",
      "Started",
      "Checkpoint span",
      "Waiting on",
      "Run",
      "Generations",
    ])
  })

  it("reads the tier off locate and the strategy off patch, rather than off a label", () => {
    renderRail(state())

    expect(screen.getByText("Tier 2")).not.toBeNull()
    expect(screen.getByText("model")).not.toBeNull()
  })

  it("marks the vendor absent and says this payload does not carry it", () => {
    renderRail(state())

    expect(screen.getByText(/not on this payload/i)).not.toBeNull()
  })

  it("names the node the graph owes a visit while the run is unfinished", () => {
    renderRail(state())

    expect(screen.getByText("patch")).not.toBeNull()
  })

  it("waits on nothing once the run has ended, whatever a node's standing still reads", () => {
    renderRail(state({ outcome: "abandoned" }))

    expect(screen.getByText(/the run reached a terminal outcome/i)).not.toBeNull()
  })
})

describe("the rail's actions", () => {
  it("names all three, and draws a control for none of them", () => {
    renderRail(state())

    // Owner ruling, 2026-08-21: these were three disabled buttons naming routes that do not exist.
    // A control drawn for a capability the product does not have reads as a feature merely switched
    // off, so the three are named in prose along with what each would need.
    const actions = [/copy the agent prompt/i, /give feedback/i, /restart the run/i]
    expect(actions.length).toBeGreaterThan(0)
    const text = document.body.textContent ?? ""
    for (const name of actions) {
      expect(name.test(text)).toBe(true)
    }
    expect(screen.queryAllByRole("button")).toHaveLength(0)
  })

  it("says what each of the three would need, so the gap is a work item", () => {
    renderRail(state())

    const text = document.body.textContent ?? ""
    expect(text).toContain("which no checkpoint channel records")
    expect(text).toContain("a write route that accepts a reviewer's judgement of a run")
    expect(text).toContain("a route that starts remediation, which would mutate the graph")
  })

  it("states why they cannot act rather than hiding them", () => {
    renderRail(state())

    expect(screen.getByText(/read-only/i)).not.toBeNull()
  })
})
