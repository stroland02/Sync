/**
 * The rule the lead screen turns on, and the one Decision 6 named as classification that cannot
 * move into Python: whether a set is small enough to list is a property of the viewport, and the
 * transport serves an agent that has none.
 *
 * The boundary is tested at, below and above deliberately. An off-by-one here is not a visible
 * bug — the screen still renders, still says a sentence, and the sentence is wrong about one row.
 */

import { describe, expect, it } from "vitest"

import {
  CARDINALITY_THRESHOLD,
  describeBoundedTotal,
  describeCardinality,
  isCompleteListing,
  sliceForDisplay,
} from "@/features/fleet/cardinality"

const AT = CARDINALITY_THRESHOLD
const BELOW = CARDINALITY_THRESHOLD - 1
const ABOVE = CARDINALITY_THRESHOLD + 1

describe("isCompleteListing", () => {
  it("lists a set below the threshold", () => {
    expect(isCompleteListing(BELOW)).toBe(true)
  })

  it("lists a set exactly at the threshold", () => {
    // At the boundary the panel still shows every row: the threshold is the largest set worth
    // listing, not the first set worth counting.
    expect(isCompleteListing(AT)).toBe(true)
  })

  it("counts a set above the threshold", () => {
    expect(isCompleteListing(ABOVE)).toBe(false)
  })

  it("lists an empty set", () => {
    expect(isCompleteListing(0)).toBe(true)
  })
})

describe("describeCardinality", () => {
  it("says a zero set is empty rather than claiming to show all of nothing", () => {
    expect(describeCardinality(0, "run", "runs", "severity then age")).toBe("No runs.")
  })

  it("agrees with its own noun on a set of one", () => {
    expect(describeCardinality(1, "run", "runs", "severity then age")).toBe("This is all 1 run.")
  })

  it("claims completeness at the threshold and never above it", () => {
    expect(describeCardinality(AT, "run", "runs", "severity then age")).toContain("This is all")
    expect(describeCardinality(ABOVE, "run", "runs", "severity then age")).not.toContain(
      "This is all"
    )
  })

  it("states the count, the slice and the ordering once the set is too large to list", () => {
    const said = describeCardinality(4213, "finding", "findings", "severity then age")
    expect(said).toContain("4,213")
    expect(said).toContain(String(CARDINALITY_THRESHOLD))
    expect(said).toContain("ordered by severity then age")
  })

  it("states the slice the table beneath it actually renders, not the threshold", () => {
    // A paginated panel's page is not this module's threshold, and a sentence claiming ten rows
    // above a table of fifty is the defect this whole module exists to prevent.
    expect(describeCardinality(4213, "finding", "findings", "age", 50)).toContain(
      "Showing 50 of 4,213"
    )
  })
})

describe("sliceForDisplay", () => {
  it("returns every row of a set at or below the threshold", () => {
    const rows = Array.from({ length: AT }, (_, i) => i)
    expect(sliceForDisplay(rows)).toHaveLength(AT)
  })

  it("returns the threshold's worth of a set above it", () => {
    const rows = Array.from({ length: ABOVE }, (_, i) => i)
    expect(sliceForDisplay(rows)).toHaveLength(CARDINALITY_THRESHOLD)
  })

  it("does not hand back the caller's own array to slice in place", () => {
    const rows = [1, 2, 3]
    expect(sliceForDisplay(rows)).not.toBe(rows)
  })
})

describe("describeBoundedTotal", () => {
  it("renders an exact count as itself", () => {
    expect(describeBoundedTotal(4213, false)).toBe("4,213")
  })

  it("marks a count the transport stopped early as a floor", () => {
    // "1,000" and "at least 1,000" are different claims, and the second is the true one once
    // the scan stopped. Rendering the bare total would imply a completeness it does not have.
    expect(describeBoundedTotal(1000, true)).toBe("1,000+")
  })
})
