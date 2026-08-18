/**
 * The run's identity, derived from what the checkpointer payload actually holds.
 *
 * Every field here is read off `WorkflowState` or it is null. The two that a reference incident
 * view would invent — a confidence figure and an elapsed wall time for a run parked on somebody
 * else's CI — are not derivable and are not derived: the span below is the distance between the
 * first and last checkpoint this run wrote, which is a measurement, and it is labelled as one.
 *
 * Every case that iterates or indexes a collection asserts the collection is non-empty first, so a
 * derivation that silently returned nothing cannot pass by having nothing to be wrong about.
 */

import { describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { formatSpan, runIdentity } from "@/features/workflows/run-identity"

function node(over: Partial<WorkflowNode> = {}): WorkflowNode {
  return { name: "locate", status: "done", standing: "ran", evidence: {}, ...over }
}

function state(over: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes: [],
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

describe("the tier the cascade routed to", () => {
  it("is read off locate's own evidence", () => {
    const subject = state({
      nodes: [node({ name: "locate", evidence: { tier: "Tier 1 — deterministic transform" } })],
    })

    expect(subject.nodes.length).toBeGreaterThan(0)
    expect(runIdentity(subject).tier).toBe("Tier 1 — deterministic transform")
  })

  it("is absent when locate ran and recorded no tier, rather than guessed at", () => {
    const subject = state({ nodes: [node({ name: "locate", evidence: {} })] })

    expect(subject.nodes.length).toBeGreaterThan(0)
    expect(runIdentity(subject).tier).toBeNull()
  })
})

describe("the strategy that produced the edit", () => {
  it("is read off patch's own evidence, not off locate's", () => {
    const subject = state({
      nodes: [
        node({ name: "locate", evidence: { tier: "Tier 2" } }),
        node({ name: "patch", evidence: { attempt_strategy: "codemod" } }),
      ],
    })

    expect(subject.nodes.length).toBeGreaterThan(1)
    expect(runIdentity(subject).strategy).toBe("codemod")
  })

  it("is absent when patch has not run", () => {
    const subject = state({
      nodes: [node({ name: "patch", standing: "not_reached_yet", evidence: {} })],
    })

    expect(subject.nodes.length).toBeGreaterThan(0)
    expect(runIdentity(subject).strategy).toBeNull()
  })
})

describe("when the run started, and how long its checkpoints span", () => {
  it("takes the earliest stamp rather than the first node in the array", () => {
    const subject = state({
      nodes: [
        node({ name: "locate", first_seen_at: "2026-08-08T10:05:00+00:00" }),
        node({ name: "prepare", first_seen_at: "2026-08-08T10:00:00+00:00" }),
      ],
    })

    expect(subject.nodes.length).toBeGreaterThan(1)
    expect(runIdentity(subject).startedAt).toBe("2026-08-08T10:00:00+00:00")
  })

  it("measures the span from the earliest first stamp to the latest last stamp", () => {
    const subject = state({
      nodes: [
        node({
          name: "locate",
          first_seen_at: "2026-08-08T10:00:00+00:00",
          last_seen_at: "2026-08-08T10:00:30+00:00",
        }),
        node({
          name: "patch",
          first_seen_at: "2026-08-08T10:01:00+00:00",
          last_seen_at: "2026-08-08T10:02:00+00:00",
        }),
      ],
    })

    expect(subject.nodes.length).toBeGreaterThan(1)
    expect(runIdentity(subject).checkpointSpanSeconds).toBe(120)
  })

  it("reports no span at all when no node has stamped, rather than zero", () => {
    const subject = state({
      nodes: [node({ name: "locate", first_seen_at: null, last_seen_at: null })],
    })

    expect(subject.nodes.length).toBeGreaterThan(0)
    const identity = runIdentity(subject)
    expect(identity.startedAt).toBeNull()
    expect(identity.checkpointSpanSeconds).toBeNull()
  })
})

describe("what the run is waiting on", () => {
  it("names the node the graph owes a visit while the run is unfinished", () => {
    const subject = state({
      nodes: [
        node({ name: "locate", standing: "ran" }),
        node({ name: "await_ci", status: "current", standing: "due" }),
      ],
      outcome: null,
    })

    expect(subject.nodes.length).toBeGreaterThan(1)
    expect(runIdentity(subject).waitingOn).toBe("await_ci")
  })

  it("names it under a due_again standing too, because a retry is still owed a visit", () => {
    const subject = state({
      nodes: [node({ name: "patch", status: "current", standing: "due_again" })],
      outcome: "running",
    })

    expect(subject.nodes.length).toBeGreaterThan(0)
    expect(runIdentity(subject).waitingOn).toBe("patch")
  })

  it("waits on nothing once the run has a terminal outcome, whatever a node still reads", () => {
    const subject = state({
      nodes: [node({ name: "patch", status: "current", standing: "due" })],
      outcome: "abandoned",
    })

    expect(subject.nodes.length).toBeGreaterThan(0)
    expect(runIdentity(subject).waitingOn).toBeNull()
  })
})

describe("the span as words", () => {
  it("stays in seconds under a minute", () => {
    expect(formatSpan(45)).toBe("45s")
  })

  it("reads minutes and seconds under an hour", () => {
    expect(formatSpan(125)).toBe("2m 5s")
  })

  it("reads hours and minutes above one", () => {
    expect(formatSpan(3900)).toBe("1h 5m")
  })
})
