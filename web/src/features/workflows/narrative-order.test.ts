/**
 * Where the run's outcome sits among the node entries, which is a placement with a wrong answer.
 *
 * The Solution Workflow renders the outcome as an entry inside the sequence rather than as a banner
 * above it, and the whole value of doing that is the position: an abandoned run's reason belongs
 * between the node that failed and the nodes that were never reached. Off by one in either
 * direction and the claim inverts — the reason lands under a node that never ran, or the four
 * never-reached entries sit above their own cause and read as an unexplained gap again.
 *
 * So this is derivation, not appearance, and it is tested here rather than measured in Chrome.
 * `briefs/2026-08-07-substrate-workflow.md`'s ruling 3 is the argument.
 */

import { describe, expect, it } from "vitest"

import type { NodeStanding, WorkflowNode } from "@/api/types"
import { closingEntryIndex } from "@/features/workflows/narrative-order"

function run(...standings: NodeStanding[]): WorkflowNode[] {
  return standings.map((standing, index) => ({
    name: `node_${index}`,
    status: standing === "ran" ? "done" : standing === "due" ? "current" : "pending",
    standing,
    evidence: {},
  }))
}

describe("where the closing entry goes", () => {
  it("puts it last on a run that reached every node", () => {
    expect(closingEntryIndex(run("ran", "ran", "ran"))).toBe(3)
  })

  it("puts it after the node the run stopped at, above the ones it never reached", () => {
    // The seeded abandoned generation: locate, prepare, patch and static_verify ran, and the four
    // behind them never did. The reason belongs at 4 — under static_verify's own evidence and above
    // replay's "the run ended before the graph got here".
    const nodes = run("ran", "ran", "ran", "ran", "never_reached", "never_reached")

    expect(closingEntryIndex(nodes)).toBe(4)
  })

  it("counts a node the graph still owes a visit as reached", () => {
    // A live run's `due` node is where the run is, so the in-flight statement sits under it rather
    // than above it. `due_again` is the same claim on a node that has already produced evidence.
    expect(closingEntryIndex(run("ran", "due", "not_reached_yet"))).toBe(2)
    expect(closingEntryIndex(run("ran", "due_again", "not_reached_yet"))).toBe(2)
  })

  it("puts it first on a run that reached nothing", () => {
    // A `reported` run decides against a patch before any node this view renders has run. Its
    // decision is the first thing that happened, so it sits above the seven entries it explains
    // rather than beneath them.
    expect(closingEntryIndex(run("never_reached", "never_reached"))).toBe(0)
  })

  it("follows the last thing that actually happened, not the first gap", () => {
    // Nothing in the payload forbids a reached node behind an unreached one, and a graph that loops
    // can produce it. Reading the first gap would file the outcome above evidence the run really
    // produced.
    expect(closingEntryIndex(run("ran", "never_reached", "ran"))).toBe(3)
  })

  it("has somewhere to go when the payload carries no nodes at all", () => {
    expect(closingEntryIndex([])).toBe(0)
  })
})
