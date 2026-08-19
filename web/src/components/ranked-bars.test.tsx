/**
 * The ranked bars' projection and its announcement.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: derivation and structural invariants, never
 * class names and never a snapshot. What is asserted here is that a log scale is *visible* to a
 * reader and that it does not swallow a zero — the two ways a log axis lies.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { RankedBars } from "@/components/ranked-bars"

afterEach(cleanup)

const SKEWED = [
  { key: "warning", value: 8576 },
  { key: "breaking", value: 108 },
  { key: "deprecation", value: 39 },
]

describe("ranked bars", () => {
  it("says on screen when the scale is logarithmic", () => {
    render(<RankedBars label="Severity" caption="Counted over every change." rows={SKEWED} unit="changes" scale="log" />)

    // A log axis a reader takes for linear is worse than no chart: every comparison they make is
    // wrong by a factor they cannot see. The announcement is the thing that makes it permissible.
    expect(document.body.textContent).toMatch(/logarithmic/i)
  })

  it("says nothing about a scale when the scale is linear", () => {
    render(<RankedBars label="Severity" caption="Counted over every change." rows={SKEWED} unit="changes" />)

    expect(document.body.textContent).not.toMatch(/logarithmic/i)
  })

  it("prints every count, so exact values never depend on reading a length", () => {
    render(<RankedBars label="Severity" caption="Counted over every change." rows={SKEWED} unit="changes" scale="log" />)

    // The whole defence of a log scale is that the numbers are still there to be read.
    for (const row of SKEWED) {
      expect(screen.getByText(row.value.toLocaleString())).toBeTruthy()
    }
  })

  it("draws a member measured at nought without collapsing the scale", () => {
    // log(0) is negative infinity, and a zero is a legitimate measurement in several of the sets
    // this component draws -- the provenance rungs among them. `log1p` maps 0 to 0.
    const withZero = [
      { key: "present", value: 100 },
      { key: "measured-at-none", value: 0 },
    ]

    render(<RankedBars label="Rungs" caption="Counted over every finding." rows={withZero} unit="findings" scale="log" />)

    expect(screen.getByText("0")).toBeTruthy()
    expect(screen.getByText("100")).toBeTruthy()
  })
})
