/**
 * What a run row says about itself, tested without rendering one.
 *
 * These four judgements were spelled inside `features/fleet/runs-table.tsx` and could only be
 * reached through a rendered card that also owned a query. They are classification and derivation,
 * which is exactly what the console's test charter scopes vitest to, so they are tested here as
 * functions.
 */

import { describe, expect, it } from "vitest"

import type { RunDisposition, RunRow } from "@/api/types"
import {
  DISPOSITION_OPTIONS,
  describeOutcome,
  isRehearsal,
  recordLine,
} from "@/features/runs/run-row"

function run(overrides: Partial<RunRow> = {}): RunRow {
  return {
    thread_id: "finding-1:prod-run-1:0",
    finding_id: "finding-1",
    finding_name: "stripe-postcharges-4b1c9e",
    liveness: null,
    last_heartbeat_at: null,
    repo_id: "org/one",
    run_id: "prod-run-1",
    current_node: null,
    outcome: "opened",
    abandon_reason: null,
    last_checkpoint_at: "2026-08-05T12:00:00Z",
    ...overrides,
  }
}

describe("the disposition vocabulary", () => {
  it("names every member the API accepts, plus the in-flight bucket", () => {
    // The guard that catches today's omission. `RunDisposition` and Python's `DISPOSITIONS` both
    // carry `parked` -- a run that stopped and is waiting on a human -- and the rail this replaced
    // offered four options, which claimed the value does not exist. Written against the closed set
    // rather than against `by_disposition`'s keys, because the payload omits a disposition no run
    // has reached and a zero count is a real answer worth pressing.
    const vocabulary: RunDisposition[] = ["opened", "abandoned", "reported", "parked"]
    const offered = DISPOSITION_OPTIONS.map((option) => option.value)

    for (const member of vocabulary) expect(offered).toContain(member)
    expect(offered).toContain("in-flight")
    expect(offered).toHaveLength(vocabulary.length + 1)
  })

  it("reads the in-flight count out of the payload's null bucket", () => {
    // JSON has no null key, so `sync.dashboard.fleet.runs` folds every unfinished run under the
    // string `"null"`. A chip reading `by_disposition["in-flight"]` would show zero forever.
    const inFlight = DISPOSITION_OPTIONS.find((option) => option.value === "in-flight")
    expect(inFlight?.bucket).toBe("null")
  })
})

describe("describeOutcome", () => {
  it("calls a run with no disposition in flight, never running", () => {
    // "Running" is an inference the graph cannot support: nothing here distinguishes a run parked
    // on the customer's CI from one whose process died.
    expect(describeOutcome(null)).toBe("in flight")
  })

  it("says a rehearsal that reported halted before the remote", () => {
    expect(describeOutcome("reported", true)).toBe("halted before the remote")
    expect(describeOutcome("reported", false)).toBe("reported")
  })
})

describe("isRehearsal", () => {
  it("reads the prefix off the run id", () => {
    expect(isRehearsal(run({ run_id: "rehearsal-2026-08-05" }))).toBe(true)
    expect(isRehearsal(run({ run_id: "prod-run-1" }))).toBe(false)
  })

  it("falls back to the thread id's second segment when there is no run id", () => {
    // `thread_id` is `{finding_id}:{run_id or head_sha}:{generation}`, so the rehearsal marker is
    // still there for a row the payload sent without a `run_id`.
    expect(
      isRehearsal(run({ run_id: null, thread_id: "finding-1:rehearsal-2026-08-05:0" })),
    ).toBe(true)
    expect(isRehearsal(run({ run_id: null, thread_id: "finding-1:abc123:0" }))).toBe(false)
  })
})

describe("recordLine", () => {
  it("gives an abandoned run the first line of its reason", () => {
    const line = recordLine(
      run({
        outcome: "abandoned",
        abandon_reason: "RuntimeError: no typecheck baseline\n  at tsc --help\n  more output",
      }),
    )
    expect(line.text).toBe("RuntimeError: no typecheck baseline")
  })

  it("names the absence when an abandoned run recorded no reason", () => {
    expect(recordLine(run({ outcome: "abandoned", abandon_reason: null })).absent).toBe(
      "no reason was recorded",
    )
    expect(recordLine(run({ outcome: "abandoned", abandon_reason: "  " })).absent).toBe(
      "no reason was recorded",
    )
  })

  it("gives an in-flight run the node the graph owes", () => {
    expect(recordLine(run({ outcome: null, current_node: "await_ci" })).text).toBe(
      "owed at await_ci",
    )
    expect(recordLine(run({ outcome: null, current_node: null })).absent).toBe("no node recorded")
  })

  it("never leaves a finished run's record empty", () => {
    // The column this feeds is full on every row of the reference and our runs carry no message
    // field. An empty cell here would render "we recorded nothing" as "nothing happened", which
    // are the two readings this console exists to keep apart.
    for (const outcome of ["opened", "reported", "parked"] as const) {
      const line = recordLine(run({ outcome, abandon_reason: null, current_node: null }))
      expect(line.absent).toBe("nothing recorded beyond the outcome")
      expect(line.text).toBeUndefined()
    }
  })
})
