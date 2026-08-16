/**
 * The two classifiers `.claude/rules/console-dev-loop.md` named as the standing violation:
 * classification in TypeScript with nothing testing it. Their own docstrings say what a wrong
 * answer costs — reading a live run as terminal "stops the poll on a live run, which freezes the
 * screen on a stale answer" — and until this file nothing held that.
 *
 * Both are polling predicates, so the failure they guard against is silent by construction: a
 * screen that has stopped asking looks exactly like a screen whose answer has not changed.
 */

import { describe, expect, it } from "vitest"

import { hasLiveRun, isRunTerminal } from "@/api/queries"
import type { RunRow, RunsPage, WorkflowOutcome, WorkflowState } from "@/api/types"

function workflow(outcome: WorkflowOutcome | null): WorkflowState {
  return {
    nodes: [],
    outcome,
    abandon_reason: null,
    report_reason: null,
    thread_id: "f".repeat(32) + ":abc123def456:0",
    generation_count: 1,
    repo_id: null,
    generations: [],
  }
}

function run(outcome: RunRow["outcome"]): RunRow {
  return {
    thread_id: `${"f".repeat(32)}:abc123def456:0`,
    finding_id: "f".repeat(32),
    current_node: outcome === null ? "await_ci" : null,
    outcome,
    abandon_reason: null,
    last_checkpoint_at: "2026-08-06T09:00:00Z",
  }
}

function page(items: RunRow[]): RunsPage {
  return { items, total: items.length, next_offset: null }
}

describe("isRunTerminal", () => {
  it("reads the three finished outcomes as terminal", () => {
    expect(isRunTerminal(workflow("opened"))).toBe(true)
    expect(isRunTerminal(workflow("abandoned"))).toBe(true)
    expect(isRunTerminal(workflow("reported"))).toBe(true)
  })

  it("does not read a run still in flight as terminal", () => {
    // The transport reports null for a run in flight. This is the case that costs a frozen
    // screen: read as terminal, the poll stops and the last answer stands forever.
    expect(isRunTerminal(workflow(null))).toBe(false)
  })

  it("does not read the checkpoint's own `running` value as terminal", () => {
    // `locate` writes `outcome: "running"` on the first hop of every run. The transport filters
    // it out today, so this is belt and braces against a value that reaches the client anyway —
    // which is exactly the case a test has to hold, because nothing on screen would show it.
    expect(isRunTerminal(workflow("running"))).toBe(false)
  })

  it("does not claim terminality for a payload that has not arrived", () => {
    expect(isRunTerminal(undefined)).toBe(false)
  })
})

describe("hasLiveRun", () => {
  it("finds nothing live on an empty page", () => {
    // An empty page is a real answer — the checkpointer holds no runs — and polling it forever
    // would be a request every five seconds for a set that changes when a run starts, which
    // this page cannot learn about anyway.
    expect(hasLiveRun(page([]))).toBe(false)
  })

  it("finds nothing live on a page where every run finished", () => {
    expect(hasLiveRun(page([run("opened"), run("abandoned"), run("reported")]))).toBe(false)
  })

  it("finds the one live run on a mixed page", () => {
    // One in-flight row is enough: the fleet stops polling only once every row it can see is
    // done, so this must not be a majority or a first-row test.
    expect(hasLiveRun(page([run("opened"), run(null), run("reported")]))).toBe(true)
  })

  it("finds a live run in the last position", () => {
    expect(hasLiveRun(page([run("opened"), run("abandoned"), run(null)]))).toBe(true)
  })

  it("does not claim a live run for a page that has not arrived", () => {
    expect(hasLiveRun(undefined)).toBe(false)
  })
})
