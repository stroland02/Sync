/**
 * Conservation, which is the only thing a Sankey actually promises.
 *
 * A band that narrows means attrition; a band that widens means the units changed and the diagram
 * is lying. `assertConserves` is what stops the second from being drawn, so it is tested against
 * the exact shape that provoked it: Sync's own graph carries 8,723 vendor changes, 13 change units
 * and 24 findings, and putting all three on one set of bands would have made a widening look like
 * growth.
 */

import { describe, expect, it } from "vitest"

import { assertConserves } from "@/components/charts/sankey-flow"

describe("flow conservation", () => {
  it("accepts a flow that splits without losing anything", () => {
    expect(
      assertConserves([
        { source: "found", target: "attempted", value: 7 },
        { source: "found", target: "untouched", value: 17 },
        { source: "attempted", target: "opened", value: 3 },
        { source: "attempted", target: "abandoned", value: 4 },
      ]),
    ).toEqual([])
  });

  it("names a stage that forwards less than it received", () => {
    // The quiet defect: a stage silently dropping rows draws a narrowing that reads as measured
    // attrition when it is really a missing branch.
    expect(
      assertConserves([
        { source: "found", target: "attempted", value: 10 },
        { source: "attempted", target: "opened", value: 4 },
      ]),
    ).toEqual(["attempted"])
  })

  it("names a stage that forwards more than it received, which is a unit change", () => {
    // 13 change units carrying 24 findings. Drawn as one flow this widens, and a widening Sankey
    // is not attrition -- it is two different units on one diagram.
    expect(
      assertConserves([
        { source: "changes", target: "units", value: 13 },
        { source: "units", target: "findings", value: 24 },
      ]),
    ).toEqual(["units"])
  })

  it("treats a terminal node as conserving, because a sink has nowhere to forward to", () => {
    expect(
      assertConserves([{ source: "found", target: "not yet attempted", value: 24 }]),
    ).toEqual([])
  })
})
