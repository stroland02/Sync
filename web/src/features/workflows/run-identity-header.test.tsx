/**
 * The run's identity header — the five facts that say *which run this is*.
 *
 * Ported from `run-fact-rail.test.tsx`, which was deleted with the rail it covered. The rail's ten
 * facts did not vanish: four are top-bar tiles, one is a clause in the evidence pane's opening
 * entry, three are prose in the remediation pane's closing panel, and these five are here. Every
 * assertion below was carried across rather than rewritten, because each held a real classification
 * — most of all the last one, which is the difference between a finished run and one still owing a
 * node a visit.
 *
 * Structure and derivation only. Never class names, never a snapshot.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { RunIdentityHeader } from "@/features/workflows/run-identity-header"

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

function renderHeader(data: WorkflowState) {
  return render(
    <MemoryRouter>
      <RunIdentityHeader
        repoId="org/one"
        findingId="finding-1"
        data={data}
        trailing={<span>fetched</span>}
      />
    </MemoryRouter>,
  )
}

function labels(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("dt")).map((el) => el.textContent ?? "")
}

describe("what the header identifies", () => {
  it("names the five facts that address the run, in the order a reviewer reads them", () => {
    const { container } = renderHeader(state())

    const listed = labels(container)
    expect(listed.length).toBeGreaterThan(0)
    expect(listed).toEqual(["Run", "Finding", "Repository", "Started", "Waiting on"])
  })

  it("links the finding, which is the address a reviewer can send on", () => {
    renderHeader(state())

    const link = screen.getByRole("link", { name: "finding-1" })
    expect(link.getAttribute("href")).toBe("/repositories/org%2Fone/findings/finding-1")
  })

  it("says which nothing it is when the run recorded no repository", () => {
    renderHeader(state({ repo_id: null }))

    expect(screen.getByText(/the run recorded no repository/i)).not.toBeNull()
  })

  it("says which nothing it is when no node has stamped a checkpoint", () => {
    renderHeader(state({ nodes: [node({ first_seen_at: null, last_seen_at: null })] }))

    expect(screen.getByText(/no node has stamped a checkpoint yet/i)).not.toBeNull()
  })
})

describe("waiting on", () => {
  it("names the node the graph owes a visit while the run is unfinished", () => {
    const { container } = renderHeader(state())

    const waiting = Array.from(container.querySelectorAll("dd")).at(-1)
    expect(waiting?.textContent).toBe("patch")
  })

  it("says the run finished rather than marking the slot absent, whatever a standing still reads", () => {
    // The classification the rail carried and the one most easily lost: a run that reached a
    // terminal outcome owes nothing further, and the absence marker here would let a finished run
    // read as one still owing a node a visit.
    renderHeader(state({ outcome: "abandoned" }))

    expect(screen.getByText("Nothing — the run reached a terminal outcome.")).not.toBeNull()
  })

  it("marks it absent when the run is live and no node is due", () => {
    renderHeader(state({ nodes: [node({ standing: "ran" })] }))

    expect(screen.getByText(/no node is marked due in the newest checkpoint/i)).not.toBeNull()
  })
})

describe("the qualifications the top bar can only hover", () => {
  it("says on screen that a checkpoint span is not a run duration", () => {
    // The claim, not the argument: a reader who never hovers must still be able to tell what the
    // top bar's `Checkpoint span` figure covers. Why the distinction exists is behind the ⓘ, which
    // is the owner's prose ruling of 2026-08-19 rather than a shortening for its own sake.
    renderHeader(state())

    expect(
      screen.getByText(/Checkpoint span is first checkpoint to last, not a run duration/i),
    ).not.toBeNull()
  })

  it("says this is the newest of several runs only when there are several", () => {
    const { container } = renderHeader(state({ generation_count: 3 }))
    expect(container.textContent).toContain("This is the most recent of 3 runs")

    cleanup()

    const single = renderHeader(state({ generation_count: 1 }))
    expect(single.container.textContent).not.toContain("most recent of")
  })
})

describe("what the header does not carry", () => {
  it("renders no confidence figure, which is what a reference view puts in this position", () => {
    const { container } = renderHeader(state())

    const text = container.textContent ?? ""
    expect(text).not.toMatch(/confidence/i)
    expect(text).not.toMatch(/\b\d{1,2}\s*\/\s*(?:5|10)\b/)
  })

  it("renders no outcome row — the outcome is the band's segment and the narrative's last entry", () => {
    const { container } = renderHeader(state({ outcome: "opened" }))

    expect(labels(container)).not.toContain("Outcome")
    expect(within(container).queryByText("opened")).toBeNull()
  })
})
