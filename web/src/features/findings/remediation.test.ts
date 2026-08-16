/**
 * What the Finding level may say about remediation, given one thread out of however many exist.
 *
 * Three ways to get this wrong, and each is reachable against seeded data.
 *
 * **A run that is not the only run.** `GET /api/workflows/{finding_id}` answers with the newest
 * generation and `generation_count` says how many there are. `9f176dea…` in the console fixture has
 * two: an abandoned first attempt and a second that opened a pull request. A rail reading the
 * outcome and calling it "the run" states the finding was abandoned when the finding was fixed.
 *
 * **A pull request read off the wrong field.** `open_pr` carries `pr_url` in its evidence and
 * `isRunTerminal`'s own comment records why a node is not the place to ask: *"`open_pr` reads `done`
 * on a run that went on to be abandoned"*. The outcome is the only field that describes how the run
 * this payload names actually ended.
 *
 * **A failed poll mistaken for no run.** `useWorkflow` re-asks every five seconds while a run is in
 * flight. A refetch that fails leaves the last good answer in `data` and sets the error at the same
 * time, and `features/pullrequests/pull-request-page.tsx` already spells the resolution — the data
 * wins. A classifier that checked the error first would flip a live run to "no run recorded" the
 * moment the network hiccuped, and back again five seconds later.
 */

import { describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowState } from "@/api/types"
import { describeRemediation, reachedPullRequest } from "@/features/findings/remediation"

function openPrNode(): WorkflowNode {
  return {
    name: "open_pr",
    status: "done",
    standing: "ran",
    evidence: { pr_url: "https://github.com/example/repo/pull/101", pr_number: 101 },
  }
}

function state(overrides: Partial<WorkflowState> = {}): WorkflowState {
  return {
    nodes: [],
    outcome: "opened",
    abandon_reason: null,
    report_reason: null,
    thread_id: "9f176dea:seed-console:1",
    generation_count: 1,
    repo_id: null,
    generations: [],
    ...overrides,
  }
}

describe("describeRemediation", () => {
  it("is pending while the query has neither an answer nor a failure", () => {
    expect(
      describeRemediation({ data: undefined, missing: false, failed: false }),
    ).toEqual({ kind: "pending" })
  })

  it("separates a checkpointer holding no run from an API that did not answer", () => {
    expect(
      describeRemediation({ data: undefined, missing: true, failed: true }),
    ).toEqual({ kind: "none" })
    expect(
      describeRemediation({ data: undefined, missing: false, failed: true }),
    ).toEqual({ kind: "unavailable" })
  })

  it("keeps the last good answer when a poll fails under it", () => {
    // The five-second re-ask failed; the run it described did not stop existing.
    expect(
      describeRemediation({ data: state(), missing: false, failed: true }),
    ).toMatchObject({ kind: "run", standing: "opened" })
  })

  it("reads a run in flight from a null outcome and from the value a checkpoint writes", () => {
    expect(
      describeRemediation({ data: state({ outcome: null }), missing: false, failed: false }),
    ).toMatchObject({ standing: "in-flight" })
    expect(
      describeRemediation({
        data: state({ outcome: "running" }),
        missing: false,
        failed: false,
      }),
    ).toMatchObject({ standing: "in-flight" })
  })

  it("carries each terminal outcome through under its own standing", () => {
    for (const outcome of ["opened", "abandoned", "reported"] as const) {
      expect(
        describeRemediation({
          data: state({ outcome }),
          missing: false,
          failed: false,
        }),
      ).toMatchObject({ standing: outcome, outcome })
    }
  })

  it("names an outcome the console has never heard of rather than folding it into a known one", () => {
    const grown = state({ outcome: "escalated" as WorkflowState["outcome"] })
    expect(
      describeRemediation({ data: grown, missing: false, failed: false }),
    ).toMatchObject({ standing: "unrecognised", outcome: "escalated" })
  })

  it("reports how many threads the finding has, so the rail never implies one", () => {
    expect(
      describeRemediation({
        data: state({ generation_count: 1 }),
        missing: false,
        failed: false,
      }),
    ).toMatchObject({ generations: 1, retried: false })
    expect(
      describeRemediation({
        data: state({ outcome: "opened", generation_count: 2 }),
        missing: false,
        failed: false,
      }),
    ).toMatchObject({ generations: 2, retried: true })
  })
})

describe("reachedPullRequest", () => {
  it("is true only for a run whose outcome is opened", () => {
    const opened = describeRemediation({
      data: state({ outcome: "opened" }),
      missing: false,
      failed: false,
    })
    expect(reachedPullRequest(opened)).toBe(true)

    for (const outcome of ["abandoned", "reported", "running", null] as const) {
      const other = describeRemediation({
        data: state({ outcome }),
        missing: false,
        failed: false,
      })
      expect(reachedPullRequest(other)).toBe(false)
    }
  })

  it("is false on a run still in flight whose open_pr node already carries a pr_url", () => {
    // The trap. A node's evidence says a pull request exists on some thread; the outcome says this
    // run has not finished. Offering the link here claims a destination that may never exist.
    const inFlight = describeRemediation({
      data: state({ outcome: null, nodes: [openPrNode()] }),
      missing: false,
      failed: false,
    })
    expect(reachedPullRequest(inFlight)).toBe(false)
  })

  it("is false for every state that is not a run", () => {
    expect(
      reachedPullRequest(
        describeRemediation({ data: undefined, missing: false, failed: false }),
      ),
    ).toBe(false)
    expect(
      reachedPullRequest(
        describeRemediation({ data: undefined, missing: true, failed: true }),
      ),
    ).toBe(false)
    expect(
      reachedPullRequest(
        describeRemediation({ data: undefined, missing: false, failed: true }),
      ),
    ).toBe(false)
  })
})
