import { describe, expect, it } from "vitest"

import type { WorkflowNode } from "@/api/types"
import { checkTone, verificationChain } from "@/features/pullrequests/verification-chain"

function node(name: string, evidence: Record<string, unknown>, standing = "ran"): WorkflowNode {
  return {
    name,
    evidence,
    standing,
    last_seen_at: null,
  } as unknown as WorkflowNode
}

describe("verificationChain", () => {
  it("reports two checks even when neither happened, so a short chain cannot look complete", () => {
    // Omitting a check that did not run leaves a chain that reads as finished. That is how
    // "we could not check" disappears from a screen built to show it.
    const chain = verificationChain([])

    expect(chain).toHaveLength(2)
    expect(chain.map((c) => c.state)).toEqual(["unknown", "unknown"])
  })

  it("does not read a run parked on the customer's CI as one that passed", () => {
    // The defect this module is written around. `attempt_ci_result` is null while waiting, and
    // treating null as "nothing to report" renders waiting and passed identically.
    const chain = verificationChain([
      node("static_verify", { verify_ok: true }),
      node("await_ci", { ci_url: "https://ci.example/run/1", attempt_ci_result: null }),
    ])

    expect(chain[1].state).toBe("waiting")
    expect(chain[1].state).not.toBe("passed")
  })

  it("keeps a timed-out wait apart from a failure and from a pass", () => {
    // Sync giving up on the wait is not the customer's suite rejecting the patch, and it is
    // certainly not the suite accepting it.
    const chain = verificationChain([node("await_ci", { attempt_ci_result: "timed_out" })])

    expect(chain[1].state).toBe("timed_out")
  })

  it("separates a compile step that ran without a verdict from one never reached", () => {
    const ran = verificationChain([node("static_verify", {})])
    const never = verificationChain([node("static_verify", {}, "never_reached")])

    expect(ran[0].state).toBe("unknown")
    expect(never[0].state).toBe("not_reached")
    expect(ran[0].detail).not.toEqual(never[0].detail)
  })

  it("reports a rejected patch as failed rather than as an absence", () => {
    const chain = verificationChain([
      node("static_verify", { verify_ok: false }),
      node("await_ci", { attempt_ci_result: "failed" }),
    ])

    expect(chain.map((c) => c.state)).toEqual(["failed", "failed"])
  })

  it("gives every state a detail sentence that is not a restatement of the label", () => {
    // The state is legible without its colour only if the words carry it. A detail that repeats
    // the label leaves colour doing the work, which is the refusal in CLAUDE.md.
    const chain = verificationChain([
      node("static_verify", { verify_ok: true }),
      node("await_ci", { attempt_ci_result: "passed" }),
    ])

    for (const check of chain) {
      expect(check.detail.length).toBeGreaterThan(check.label.length)
      expect(check.detail.toLowerCase()).not.toEqual(check.label.toLowerCase())
    }
  })
})

/**
 * The tone a check wears where it is rendered as a tag rather than as a chain row.
 *
 * The three neutrals are the whole assertion. A run parked on the customer's CI wearing a pass is
 * the same defect `verificationChain` itself is written around, arriving one layer up as a colour.
 */
describe("checkTone", () => {
  it("tones only the three states that are a verdict", () => {
    expect(checkTone("passed")).toBe("good")
    expect(checkTone("failed")).toBe("critical")
    expect(checkTone("timed_out")).toBe("serious")
  })

  it("leaves waiting, not-reached and unknown neutral, because none of them is a verdict", () => {
    for (const state of ["waiting", "not_reached", "unknown"] as const) {
      expect(checkTone(state), `${state} wore a verdict's tone`).toBe("neutral")
    }
  })
})
