/**
 * Whether a published change lands on an operation this codebase calls — the one derivation the
 * Integration changes screen exists to draw, and the one that is easiest to get quietly wrong.
 *
 * Three of these guards are about *which nothing*: a census that answered and found no call site
 * is a measured zero, a census that could not be taken is not, and a repository that was never
 * indexed is a third thing again. Collapsing any pair renders one nothing as another, which is the
 * refusal `web/CLAUDE.md` names first.
 */

import { describe, expect, it } from "vitest"

import {
  bindingOf,
  bindingSplit,
  censusFromCallSites,
  censusNeverIndexed,
  censusUnanswered,
  operationsNamed,
} from "@/features/vendors/change-binding"

const SITES = [
  { vendor_id: "stripe", operation_id: "PostCharges" },
  { vendor_id: "stripe", operation_id: "PostCharges" },
  { vendor_id: "openai", operation_id: "createChatCompletion" },
]

describe("bindingOf", () => {
  it("counts the call sites that name the operation the change names", () => {
    const census = censusFromCallSites(SITES, 3)
    expect(bindingOf(census, "stripe", "PostCharges")).toEqual({ kind: "bound", callSites: 2 })
  })

  it("keys on the integration as well as the operation, so two vendors cannot share a count", () => {
    // `by_operation` from the call-sites payload is keyed by operation id alone, and two vendors
    // publishing the same operation name would lend each other call sites through it. The count
    // here has to be the pair or the screen reports exposure the graph does not hold.
    const census = censusFromCallSites(SITES, 3)
    expect(bindingOf(census, "twilio", "PostCharges").kind).toBe("not-bound")
  })

  it("answers a complete census with no matching site as a measured zero", () => {
    const census = censusFromCallSites(SITES, 3)
    expect(bindingOf(census, "datadog", "POST /api/v2/logs")).toEqual({ kind: "not-bound" })
  })

  it("refuses to call an absence a zero when the census is bounded short of the total", () => {
    // The call-site read is capped, so a repository with more sites than the cap has a census that
    // cannot prove an absence. Saying "nothing here binds it" from a partial read is exactly the
    // one-nothing-for-another defect.
    const census = censusFromCallSites(SITES, 900)
    const answer = bindingOf(census, "datadog", "POST /api/v2/logs")
    expect(answer.kind).toBe("not-counted")
    if (answer.kind === "not-counted") expect(answer.why).toMatch(/900/)
  })

  it("still reports a hit from a bounded census, because a positive needs no completeness", () => {
    const census = censusFromCallSites(SITES, 900)
    expect(bindingOf(census, "openai", "createChatCompletion")).toEqual({
      kind: "bound",
      callSites: 1,
    })
  })

  it("reports never-indexed as itself, never as nothing-here", () => {
    expect(bindingOf(censusNeverIndexed(), "stripe", "PostCharges")).toEqual({
      kind: "never-indexed",
    })
  })

  it("reports a census that did not answer as uncounted, carrying its reason", () => {
    const answer = bindingOf(censusUnanswered("the call sites did not answer"), "stripe", "X")
    expect(answer.kind).toBe("not-counted")
    if (answer.kind === "not-counted") expect(answer.why).toBe("the call sites did not answer")
  })

  it("treats an indexed repository holding no call site at all as a measured zero", () => {
    // A pass that ran and found nothing is a zero; that is the arm `censusNeverIndexed` is not.
    expect(bindingOf(censusFromCallSites([], 0), "stripe", "PostCharges")).toEqual({
      kind: "not-bound",
    })
  })
})

describe("bindingSplit", () => {
  const changes = [
    { vendor_id: "stripe", operation_id: "PostCharges" },
    { vendor_id: "openai", operation_id: "createChatCompletion" },
    { vendor_id: "datadog", operation_id: "POST /api/v2/logs" },
  ]

  it("partitions the rows it was given, so the parts carry their own denominator", () => {
    const split = bindingSplit(changes, censusFromCallSites(SITES, 3))
    expect(split).toEqual({ bound: 2, notBound: 1, notCounted: 0, total: 3 })
  })

  it("puts every row in the uncounted arm when the census could not be taken", () => {
    const split = bindingSplit(changes, censusUnanswered("no answer"))
    expect(split).toEqual({ bound: 0, notBound: 0, notCounted: 3, total: 3 })
  })

  it("never claims a zero for a repository that was never indexed", () => {
    const split = bindingSplit(changes, censusNeverIndexed())
    expect(split.notBound).toBe(0)
    expect(split.notCounted).toBe(3)
  })

  it("sums to the rows it was handed under every census", () => {
    for (const census of [
      censusFromCallSites(SITES, 3),
      censusFromCallSites(SITES, 900),
      censusNeverIndexed(),
      censusUnanswered("no answer"),
    ]) {
      const split = bindingSplit(changes, census)
      expect(split.bound + split.notBound + split.notCounted).toBe(split.total)
    }
  })
})

describe("operationsNamed", () => {
  const page = [
    { vendor_id: "stripe", operation_id: "PostCharges" },
    { vendor_id: "stripe", operation_id: "PostCharges" },
    { vendor_id: "openai", operation_id: "createChatCompletion" },
    { vendor_id: "datadog", operation_id: "POST /api/v2/logs" },
  ]

  it("collapses the page to one entry per integration and operation, counting the changes", () => {
    const named = operationsNamed(page, censusFromCallSites(SITES, 3))
    expect(named).toHaveLength(3)
    expect(named.find((row) => row.operationId === "PostCharges")?.changes).toBe(2)
  })

  it("ranks the operations this codebase calls most heavily first", () => {
    const named = operationsNamed(page, censusFromCallSites(SITES, 3))
    expect(named.map((row) => row.operationId)).toEqual([
      "PostCharges",
      "createChatCompletion",
      "POST /api/v2/logs",
    ])
  })

  it("orders totally, so two entries the census cannot separate never reshuffle", () => {
    // A ranking whose ties are left to the sort's stability reshuffles between reads for no reason
    // a reader can see, which reads as a fault in the data rather than in the ordering.
    const forward = operationsNamed(page, censusNeverIndexed()).map((row) => row.operationId)
    const reversed = operationsNamed([...page].reverse(), censusNeverIndexed()).map(
      (row) => row.operationId,
    )
    expect(forward).toEqual(reversed)
  })

  it("carries each entry's own binding answer rather than a shared one", () => {
    const named = operationsNamed(page, censusFromCallSites(SITES, 3))
    expect(named.find((row) => row.operationId === "PostCharges")?.binding).toEqual({
      kind: "bound",
      callSites: 2,
    })
    expect(named.find((row) => row.operationId === "POST /api/v2/logs")?.binding).toEqual({
      kind: "not-bound",
    })
  })
})
