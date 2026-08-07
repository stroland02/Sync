/**
 * What the Pull Request level's rail may say, given evidence the transport does not type.
 *
 * `pr_number`, `pr_url` and `branch` are not fields on `WorkflowState`. They are keys inside
 * `nodes[].evidence`, which is `Record<string, unknown>` — so every one of them can be absent, can
 * be a node the payload does not carry at all, or can hold something that is not a scalar. Four
 * ways to get this wrong, and each is reachable against a real payload.
 *
 * **A URL that is not one.** The value originates in a customer's repository by way of a forge, so
 * it arrives at a boundary. Anything that is not `http:` or `https:` must render as text: a
 * `javascript:` href in an anchor is a script the console would run on somebody else's say-so.
 *
 * **A number rendered as `[object Object]`.** `String()` over an object produces something that
 * looks like a value in a rail row. A non-scalar is an absence, not a string.
 *
 * **A node the payload does not carry.** The bundle names five nodes; a graph that renamed one
 * sends four. That is an absence, not a crash.
 *
 * **One absence sentence for four different nothings.** A pull request missing because routing
 * decided against a patch, missing because the run was abandoned before it got there, and missing
 * because the run has not got there yet are three different facts. The rail says which, in the
 * short form, because the long form is already once on the same screen.
 */

import { describe, expect, it } from "vitest"

import type { WorkflowNode, WorkflowOutcome } from "@/api/types"
import { bundleFacts, noBranchPhrase, noPullRequestPhrase } from "@/features/pullrequests/bundle-facts"

function node(name: string, evidence: Record<string, unknown>): WorkflowNode {
  return { name, status: "done", standing: "ran", evidence }
}

/** The seeded run `9f176dea35907f95beb29553e574a037`, which opened a pull request. */
function openedRun(): WorkflowNode[] {
  return [
    node("push_branch", { branch: "sync/fix-post-charges-param" }),
    node("open_pr", { pr_url: "https://github.com/example/repo/pull/101", pr_number: 101 }),
  ]
}

describe("bundleFacts", () => {
  it("lifts the number, the address and the branch out of the two nodes that carry them", () => {
    expect(bundleFacts(openedRun())).toEqual({
      prNumber: "101",
      prUrl: "https://github.com/example/repo/pull/101",
      branch: "sync/fix-post-charges-param",
    })
  })

  it("reports absence rather than throwing when the payload carries neither node", () => {
    expect(bundleFacts([])).toEqual({ prNumber: null, prUrl: null, branch: null })
  })

  it("reports absence for a node that ran and produced none of these keys", () => {
    expect(bundleFacts([node("open_pr", {}), node("push_branch", {})])).toEqual({
      prNumber: null,
      prUrl: null,
      branch: null,
    })
  })

  it("treats a key present holding null as an absence, because a rail row cannot render null", () => {
    expect(bundleFacts([node("open_pr", { pr_url: null, pr_number: null })])).toMatchObject({
      prNumber: null,
      prUrl: null,
    })
  })

  it("refuses a href that is not http or https", () => {
    for (const hostile of [
      "javascript:alert(1)",
      "data:text/html,<script>alert(1)</script>",
      "file:///etc/passwd",
      "not a url at all",
      "",
    ]) {
      expect(bundleFacts([node("open_pr", { pr_url: hostile })]).prUrl).toBeNull()
    }
  })

  it("keeps a plain http address, because a self-hosted forge is not always TLS", () => {
    expect(bundleFacts([node("open_pr", { pr_url: "http://forge.internal/x/pull/3" })]).prUrl).toBe(
      "http://forge.internal/x/pull/3",
    )
  })

  it("refuses a non-scalar rather than stringifying it into something that reads as a value", () => {
    expect(
      bundleFacts([
        node("open_pr", { pr_number: { value: 101 } }),
        node("push_branch", { branch: ["a", "b"] }),
      ]),
    ).toMatchObject({ prNumber: null, branch: null })
  })

  it("reads the two nodes by name rather than by position", () => {
    const shuffled = [
      node("open_pr", { pr_number: 7 }),
      node("await_ci", { branch: "not-this-one" }),
      node("push_branch", { branch: "sync/real" }),
    ]
    expect(bundleFacts(shuffled)).toMatchObject({ prNumber: "7", branch: "sync/real" })
  })
})

describe("noPullRequestPhrase", () => {
  it("says which nothing it is, and never the same words twice", () => {
    const phrases = (["reported", "abandoned", "running", "opened"] as const).map((outcome) =>
      noPullRequestPhrase(outcome),
    )
    expect(new Set(phrases).size).toBe(phrases.length)
  })

  it("reads a null outcome and the value a checkpoint writes as one state", () => {
    expect(noPullRequestPhrase(null)).toBe(noPullRequestPhrase("running"))
  })

  it("does not claim finality on a run that is still in flight", () => {
    for (const outcome of [null, "running"] as const) {
      expect(noPullRequestPhrase(outcome)).toContain("yet")
    }
  })

  it("names an outcome the console has never heard of rather than borrowing another's sentence", () => {
    const grown = "escalated" as WorkflowOutcome
    expect(noPullRequestPhrase(grown)).not.toBe(noPullRequestPhrase("abandoned"))
    expect(noPullRequestPhrase(grown)).not.toBe(noPullRequestPhrase("reported"))
  })
})

describe("noBranchPhrase", () => {
  it("says which nothing it is, and never the same words twice", () => {
    const phrases = (["reported", "abandoned", "running", "opened"] as const).map((outcome) =>
      noBranchPhrase(outcome),
    )
    expect(new Set(phrases).size).toBe(phrases.length)
  })

  it("is never the pull request's sentence, because a missing branch is a different fact", () => {
    for (const outcome of ["reported", "abandoned", "running", "opened", null] as const) {
      expect(noBranchPhrase(outcome)).not.toBe(noPullRequestPhrase(outcome))
    }
  })

  it("does not claim finality on a run that is still in flight", () => {
    for (const outcome of [null, "running"] as const) {
      expect(noBranchPhrase(outcome)).toContain("yet")
    }
  })
})
