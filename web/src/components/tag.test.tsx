/**
 * The tone axis holds two rules the re-ruling of 2026-08-19 was granted on: a tone mapping
 * ranks exactly the way its vocabulary ranks, and a member the console has not caught up with
 * renders neutral rather than wearing a confident wrong colour.
 */

import { cleanup, render } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { OUTCOME_TONE, SEVERITY_TONE, SeverityTag, Tag } from "@/components/tag"

afterEach(cleanup)

describe("the severity ramp ranks as SEVERITY_ORDER does", () => {
  it("maps each severity one rung hotter than the one below it", () => {
    // The vocabulary's own descending order. A mapping that crossed it would colour a milder
    // value hotter than a graver one — a wrong claim no tooltip repairs.
    const rank: Record<string, number> = { critical: 4, serious: 3, warning: 2, good: 1, neutral: 0 }
    const severities = ["breaking", "warning", "deprecation", "addition", "info"]
    const tones = severities.map((severity) => rank[SEVERITY_TONE[severity]])
    expect(tones).toEqual([...tones].sort((a, b) => b - a))
    expect(new Set(tones).size).toBeGreaterThan(1)
  })

  it("renders an unknown severity neutral, never a guessed colour", () => {
    render(<SeverityTag severity="catastrophic" />)
    const tag = document.querySelector("[data-tone]")
    expect(tag?.getAttribute("data-tone")).toBe("neutral")
  })
})

describe("a toned tag never carries colour alone", () => {
  it("ships a glyph beside the word on every non-neutral tone", () => {
    render(<Tag tone="critical">breaking</Tag>)
    const tag = document.querySelector('[data-tone="critical"]')
    expect(tag?.querySelector("svg")).not.toBeNull()
    expect(tag?.textContent).toContain("breaking")
  })

  it("keeps the neutral tag exactly as it was — no glyph, hairline only", () => {
    render(<Tag>info</Tag>)
    const tag = document.querySelector('[data-tone="neutral"]')
    expect(tag?.querySelector("svg")).toBeNull()
  })
})

describe("outcome tones", () => {
  it("ranks abandoned graver than reported, and leaves the unknown neutral", () => {
    expect(OUTCOME_TONE["opened"]).toBe("good")
    expect(OUTCOME_TONE["abandoned"]).toBe("serious")
    expect(OUTCOME_TONE["reported"]).toBe("warning")
    expect(OUTCOME_TONE["running"]).toBeUndefined()
  })
})
