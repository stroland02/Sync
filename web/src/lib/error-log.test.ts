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

import { afterEach, describe, expect, it } from "vitest"

import {
  KINDS_SHOWN,
  clearErrors,
  dismissKind,
  getErrorEntries,
  groupErrorsByKind,
  reportError,
  type ErrorEntry,
} from "@/lib/error-log"

afterEach(clearErrors)

/** Newest first, the order `reportError` maintains by prepending. */
function log(...summaries: string[]): ErrorEntry[] {
  return summaries.map((summary, index) => ({
    id: String(summaries.length - index),
    summary,
    detail: `detail ${summaries.length - index}`,
    timestamp: "2026-08-07T00:00:00Z",
  }))
}

/** The same, where the endpoint each failure came from is the thing under test. */
function logOf(...pairs: [summary: string, path: string][]): ErrorEntry[] {
  return pairs.map(([summary, path], index) => ({
    id: String(pairs.length - index),
    summary,
    path,
    detail: `${summary} at ${path}`,
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

describe("a row counts only the path it names", () => {
  // `describe-failure.ts` puts the endpoint in its own field, so one summary — "The API answered
  // with HTTP 502." — is what *every* failing endpoint says during an outage. Keyed on the summary
  // alone, five failures across three endpoints drew one row printing one path beside "5 times",
  // which attributes four failures to a route that produced one of them.
  it("separates one summary arriving from two endpoints", () => {
    const kinds = groupErrorsByKind(
      logOf(
        ["The API answered with HTTP 502.", "/api/overview"],
        ["The API answered with HTTP 502.", "/api/repositories"],
        ["The API answered with HTTP 502.", "/api/repositories"]
      )
    )

    expect(kinds).toHaveLength(2)
    expect(kinds.map((kind) => kind.newest.path)).toEqual(["/api/overview", "/api/repositories"])
    expect(kinds.map((kind) => kind.count)).toEqual([1, 2])
  })

  it("still collapses one summary from one endpoint", () => {
    const kinds = groupErrorsByKind(
      logOf(
        ["The API is unreachable.", "/api/corpus"],
        ["The API is unreachable.", "/api/corpus"]
      )
    )

    expect(kinds).toHaveLength(1)
    expect(kinds[0].count).toBe(2)
  })

  it("keeps a failure carrying no path as its own row", () => {
    // A render crash has a summary and no endpoint. It must not be folded into whichever API
    // failure happens to share its wording.
    const kinds = groupErrorsByKind([
      ...logOf(["An unexpected error occurred.", "/api/runs"]),
      ...log("An unexpected error occurred."),
    ])

    expect(kinds).toHaveLength(2)
  })

  it("dismisses the row a reader was looking at, and only that row", () => {
    // The other half of the same defect: dismissing by summary cleared entries whose paths had
    // never been on screen, so a reader lost failures they had not read.
    reportError({ summary: "The API answered with HTTP 502.", path: "/api/overview", detail: "a" })
    reportError({ summary: "The API answered with HTTP 502.", path: "/api/runs", detail: "b" })

    const [newest] = groupErrorsByKind(getErrorEntries())
    dismissKind(newest.key)

    const left = groupErrorsByKind(getErrorEntries())
    expect(left).toHaveLength(1)
    expect(left[0].newest.path).toBe("/api/overview")
  })
})
