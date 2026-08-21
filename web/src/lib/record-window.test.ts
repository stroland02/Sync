/**
 * What a status band is allowed to claim about how many records there are.
 *
 * Three answers have to stay apart, and every one has been collapsed onto another somewhere in
 * this console before: a confirmed zero, a total that stopped counting at a ceiling, and a count
 * nothing answered. The first is a measurement, the second is a floor, the third is absence. A
 * band that renders `0` for all three is the defect this file exists to catch.
 *
 * Moved here with the formatters when `components/table-toolbar.tsx` retired. That file had no
 * importer outside its own test, but these assertions are the only coverage the branching in
 * `describeRecordWindow` has.
 */

import { describe, expect, it } from "vitest"

import {
  boundedRecordCaveat,
  describeRecordWindow,
  type RecordTotal,
} from "@/lib/record-window"

const CONFIRMED = (count: number): RecordTotal => ({ count, boundReached: false })
const BOUNDED = (count: number): RecordTotal => ({ count, boundReached: true })
const UNANSWERED: RecordTotal = { count: null, boundReached: false }

describe("describeRecordWindow", () => {
  it("states a confirmed zero in words rather than as absence", () => {
    expect(describeRecordWindow(0, 0, CONFIRMED(0), "call site", "call sites")).toBe(
      "No call sites."
    )
  })

  it("returns null for a count nothing answered, so the caller renders the absence marker", () => {
    expect(describeRecordWindow(0, 0, UNANSWERED, "call site", "call sites")).toBeNull()
  })

  it("says the page is the whole set when one page holds every record", () => {
    const sentence = describeRecordWindow(0, 7, CONFIRMED(7), "call site", "call sites")

    expect(sentence).toContain("7")
    expect(sentence).toContain("call sites")
    expect(sentence).not.toContain("Showing")
  })

  it("uses the singular noun for exactly one record", () => {
    expect(describeRecordWindow(0, 1, CONFIRMED(1), "call site", "call sites")).toContain(
      "1 call site."
    )
  })

  it("places the page inside the total when the set is longer than a page", () => {
    const sentence = describeRecordWindow(50, 50, CONFIRMED(4213), "call site", "call sites")

    expect(sentence).toContain("51")
    expect(sentence).toContain("100")
    expect(sentence).toContain("4,213")
  })

  it("marks a total that stopped counting with the + convention and never as an exact figure", () => {
    const bounded = describeRecordWindow(0, 50, BOUNDED(1000), "call site", "call sites")
    const confirmed = describeRecordWindow(0, 50, CONFIRMED(1000), "call site", "call sites")

    expect(bounded).toContain("1,000+")
    expect(confirmed).toContain("1,000")
    expect(confirmed).not.toContain("1,000+")
    expect(bounded).not.toBe(confirmed)
  })

  it("never claims a bounded page is the whole set, even when the page holds the counted total", () => {
    const sentence = describeRecordWindow(0, 1000, BOUNDED(1000), "call site", "call sites")

    expect(sentence).toContain("1,000+")
    expect(sentence).toContain("Showing")
  })

  it("says a page is empty rather than rendering an impossible range when the set moved underneath it", () => {
    const sentence = describeRecordWindow(200, 0, CONFIRMED(120), "call site", "call sites")

    expect(sentence).not.toContain("201")
    expect(sentence).toContain("120")
  })
})

describe("boundedRecordCaveat", () => {
  it("says in words what the + glyph means, so the glyph is never the only channel", () => {
    const caveat = boundedRecordCaveat(1000, "call sites")

    expect(caveat).toContain("1,000")
    expect(caveat).toContain("at least")
    expect(caveat).toContain("call sites")
  })
})
