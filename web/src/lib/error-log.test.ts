/**
 * Ninety-two cards saying the same thing is one fact, and this is where that gets counted.
 *
 * The owner's own capture of a console with no API behind it showed 92 stacked
 * *"The API is unreachable"* cards covering the page. Every one of them was a genuine failure and
 * none of them was a second piece of information: one poll failing ninety-two times is one kind of
 * failure with a count. **The cap is presentation and nothing else** — every entry stays in the
 * log, which is what `groupErrorsByKind` reading the whole array rather than a window of it holds.
 *
 * Newest first, because the log is newest first and a reader looking at an error surface is looking
 * for what just broke.
 */

import { describe, expect, it } from "vitest"

import { KINDS_SHOWN, groupErrorsByKind, type ErrorEntry } from "@/lib/error-log"

/** Newest first, the order `reportError` maintains by prepending. */
function log(...summaries: string[]): ErrorEntry[] {
  return summaries.map((summary, index) => ({
    id: String(summaries.length - index),
    summary,
    detail: `detail ${summaries.length - index}`,
    timestamp: "2026-08-07T00:00:00Z",
  }))
}

describe("the error surface groups by kind before it counts", () => {
  it("collapses one kind repeated into one row carrying its count", () => {
    const kinds = groupErrorsByKind(log("unreachable", "unreachable", "unreachable"))

    expect(kinds).toHaveLength(1)
    expect(kinds[0].count).toBe(3)
  })

  it("keeps the newest entry of a kind as the one it shows", () => {
    const kinds = groupErrorsByKind(log("unreachable", "unreachable"))

    expect(kinds[0].newest.detail).toBe("detail 2")
  })

  it("orders kinds by the newest entry each one holds", () => {
    const kinds = groupErrorsByKind(log("later", "earlier", "earlier"))

    expect(kinds.map((kind) => kind.summary)).toEqual(["later", "earlier"])
  })

  it("counts every entry, including the ones beyond the cap", () => {
    // The claim the cap rests on: nothing is dropped, only the drawing is bounded. A grouping that
    // read a window of the log would report a smaller total and the count on screen would be wrong.
    const kinds = groupErrorsByKind(log("a", "b", "c", "d", "e"))

    expect(kinds).toHaveLength(5)
    expect(kinds.length).toBeGreaterThan(KINDS_SHOWN)
  })

  it("says nothing about an empty log", () => {
    expect(groupErrorsByKind([])).toEqual([])
  })
})
