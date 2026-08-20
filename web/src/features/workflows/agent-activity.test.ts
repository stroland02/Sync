// The feed's two derivations, tested as functions rather than with timers: the property is
// "a terminal outcome stops the poll", not "5000ms elapsed".

import { describe, expect, it } from "vitest"

import { WORKFLOW_POLL_MS } from "@/api/queries"
import { activityPollMs, activityRowLabel } from "@/features/workflows/agent-activity"
import type { RunActivityEvent, WorkflowOutcome, WorkflowState } from "@/api/types"

function run(outcome: WorkflowOutcome | null): WorkflowState {
  return {
    nodes: [],
    outcome,
    abandon_reason: null,
    report_reason: null,
    thread_id: "t1",
    generation_count: 1,
    repo_id: null,
    generations: [],
  }
}

function event(overrides: Partial<RunActivityEvent> = {}): RunActivityEvent {
  return { seq: 1, at: "2026-08-20T12:00:00+00:00", kind: "tool", tool: "Read", summary: "s", ...overrides }
}

describe("activityPollMs", () => {
  it("polls at the workflow cadence while the run has no outcome", () => {
    expect(activityPollMs(run(null))).toBe(WORKFLOW_POLL_MS)
  })

  it("keeps polling while the workflow itself has not answered", () => {
    expect(activityPollMs(undefined)).toBe(WORKFLOW_POLL_MS)
  })

  it("stops on every terminal outcome", () => {
    for (const outcome of ["opened", "abandoned", "reported"] as const) {
      expect(activityPollMs(run(outcome))).toBe(false)
    }
  })

  it("does not read a leaked 'running' checkpoint value as terminal", () => {
    expect(activityPollMs(run("running"))).toBe(WORKFLOW_POLL_MS)
  })
})

describe("activityRowLabel", () => {
  it("names the tool on a permitted call", () => {
    expect(activityRowLabel(event({ kind: "tool", tool: "Edit" }))).toBe("Edit")
  })

  it("labels the agent's own prose as a note", () => {
    expect(activityRowLabel(event({ kind: "note", tool: null }))).toBe("note")
  })

  it("marks a refusal and still names the tool that was refused", () => {
    const label = activityRowLabel(event({ kind: "refusal", tool: "Bash" }))
    expect(label).toContain("refused")
    expect(label).toContain("Bash")
  })

  it("never renders a null tool as the string 'null'", () => {
    expect(activityRowLabel(event({ kind: "tool", tool: null }))).not.toContain("null")
    expect(activityRowLabel(event({ kind: "refusal", tool: null }))).not.toContain("null")
  })
})
