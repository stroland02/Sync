/**
 * The API surface panel: the one place on this console where good news is a number.
 *
 * The derivations with wrong answers are both about zero. A missing member must draw a bar at
 * nought **once a surface exists**, because a healthy codebase's `at_risk: 0` is exactly the
 * figure a reader came for and a chart that omits it looks broken. And a codebase with no call
 * sites at all must draw no bars, because three noughts there would claim its operations had been
 * examined and found clean.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ApiSurfacePanel, surfaceBars } from "@/features/repositories/api-surface-panel"

afterEach(cleanup)

describe("the bars", () => {
  it("draws every member of the vocabulary, including the ones at nought", () => {
    // `web/CLAUDE.md`'s donut lesson, one panel over: a bar of length zero still has a row, a
    // label and a count, and `at_risk: 0` is the whole point of the panel.
    const bars = surfaceBars({ clean: 41 })

    expect(bars).toHaveLength(3)
    expect(bars.find((bar) => bar.key === "At risk")?.value).toBe(0)
    expect(bars.find((bar) => bar.key === "Clean")?.value).toBe(41)
  })

  it("keeps the vocabulary's own order rather than sorting by size", () => {
    // Most-wanting-attention first. Sorting by count would move the row a reader is looking for
    // every time the numbers changed.
    expect(surfaceBars({ clean: 90, at_risk: 1 }).map((bar) => bar.key)).toEqual([
      "At risk",
      "Not checked",
      "Clean",
    ])
  })
})

describe("what the panel says", () => {
  it("leads with how many operations the codebase calls", () => {
    render(<ApiSurfacePanel counts={{ at_risk: 3, clean: 41, unchecked: 9 }} />)

    // 3 + 41 + 9. The panel sums the payload rather than being handed a total, so the two cannot
    // disagree — a separate total is a second figure that drifts.
    expect(screen.getByText("53")).toBeTruthy()
    // Twice on purpose: the metric's unit and the chart's caption both name the grain, because
    // "operations, not call sites" is the claim a reader most easily assumes wrongly.
    expect(screen.getAllByText(/operations this codebase calls/).length).toBeGreaterThan(0)
  })

  it("says which nothing an unindexed codebase is, rather than drawing three zeroes", () => {
    // Three noughts would claim the operations had been examined and found clean. There are no
    // operations, which is a different fact and the one this states.
    render(<ApiSurfacePanel counts={{}} />)

    expect(screen.getByText(/no operation indexed/)).toBeTruthy()
    expect(screen.getByText(/nothing here has been examined/i)).toBeTruthy()
  })

  it("renders no percentage, ratio or health figure", () => {
    // Rejected three times on the record: a scalar averaging "we could not check" with "we
    // checked and it passed" collapses the distinction this panel exists to draw.
    const { container } = render(<ApiSurfacePanel counts={{ at_risk: 3, clean: 41, unchecked: 9 }} />)

    const text = container.textContent ?? ""
    expect(text).not.toMatch(/%|health|score|\bratio\b/i)
  })

  it("counts a single operation with singular words", () => {
    render(<ApiSurfacePanel counts={{ clean: 1 }} />)

    expect(screen.getByText(/1 operation this codebase calls|operation this codebase calls/)).toBeTruthy()
  })
})
