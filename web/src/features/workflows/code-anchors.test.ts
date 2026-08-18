/**
 * `file:line` anchors pulled out of the two block channels this run actually produces.
 *
 * `diagnostics` is `tsc` output and `replay_evidence` is the replay's own text; both are line-per-
 * record and both name a path and a line when they name anything. Nothing here invents an anchor:
 * a line the compiler did not anchor comes back with `anchor: null` and its text untouched.
 */

import { describe, expect, it } from "vitest"

import {
  VISIBLE_LINE_BUDGET,
  anchorLabel,
  codeLines,
  needsDisclosure,
  visibleLines,
} from "@/features/workflows/code-anchors"

describe("reading an anchor off a compiler line", () => {
  it("parses tsc's parenthesised form and keeps what follows it", () => {
    const lines = codeLines("src/billing/client.ts(12,3): error TS2551: Property 'amount' missing.")

    expect(lines).toHaveLength(1)
    expect(lines[0].anchor).toEqual({
      path: "src/billing/client.ts",
      line: 12,
      column: 3,
    })
    expect(lines[0].text).toBe("error TS2551: Property 'amount' missing.")
  })

  it("parses the colon-separated pretty form as the same anchor", () => {
    const lines = codeLines("src/billing/client.ts:12:3 - error TS2551: bad")

    expect(lines).toHaveLength(1)
    expect(lines[0].anchor).toEqual({ path: "src/billing/client.ts", line: 12, column: 3 })
    expect(lines[0].text).toBe("error TS2551: bad")
  })

  it("leaves an unanchored line alone rather than inventing a path for it", () => {
    const lines = codeLines("Found 2 errors in 1 file.")

    expect(lines).toHaveLength(1)
    expect(lines[0].anchor).toBeNull()
    expect(lines[0].text).toBe("Found 2 errors in 1 file.")
  })

  it("splits a multi-line block into one entry per line and anchors only the ones that carry one", () => {
    const lines = codeLines(
      ["src/a.ts(1,1): error TS1: one", "  continuation of the message", "src/b.ts(9,4): error TS2: two"].join(
        "\n",
      ),
    )

    expect(lines).toHaveLength(3)
    expect(lines.filter((line) => line.anchor !== null)).toHaveLength(2)
    expect(lines[1].anchor).toBeNull()
  })

  it("renders an anchor as file:line, which is what a reviewer pastes", () => {
    expect(anchorLabel({ path: "src/a.ts", line: 12, column: 3 })).toBe("src/a.ts:12")
  })
})

describe("the show-more budget over a long span", () => {
  function block(count: number): string {
    return Array.from({ length: count }, (_, index) => `src/a.ts(${index + 1},1): error TS1: e`).join(
      "\n",
    )
  }

  it("needs no disclosure at exactly the budget", () => {
    const lines = codeLines(block(VISIBLE_LINE_BUDGET))

    expect(lines).toHaveLength(VISIBLE_LINE_BUDGET)
    expect(needsDisclosure(lines)).toBe(false)
    expect(visibleLines(lines, false)).toHaveLength(VISIBLE_LINE_BUDGET)
  })

  it("truncates to the budget while collapsed, and shows every line once expanded", () => {
    const lines = codeLines(block(VISIBLE_LINE_BUDGET + 7))

    expect(lines.length).toBeGreaterThan(VISIBLE_LINE_BUDGET)
    expect(needsDisclosure(lines)).toBe(true)
    expect(visibleLines(lines, false)).toHaveLength(VISIBLE_LINE_BUDGET)
    expect(visibleLines(lines, true)).toHaveLength(VISIBLE_LINE_BUDGET + 7)
  })
})
