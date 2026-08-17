/**
 * The sidebar's remembered state, and what it does with a value it did not write.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation, never class names.
 * The widths are asserted as values because `DESIGN.md` argues them and a silent drift from the
 * argued number is the defect — not because a pixel is being tested.
 */

import { afterEach, describe, expect, it } from "vitest"

import {
  SIDEBAR_STORAGE_KEY,
  SIDEBAR_WIDTH_EXPANDED,
  SIDEBAR_WIDTH_MINIMISED,
  parseMinimised,
  readMinimised,
  writeMinimised,
} from "@/layouts/sidebar-collapse"

afterEach(() => {
  window.localStorage.clear()
})

describe("the remembered state", () => {
  it("reads an absent choice as expanded, so labels show for someone who never chose", () => {
    // Defaulting the other way would hide every destination's name from a first-time reader.
    expect(parseMinimised(null)).toBe(false)
    expect(readMinimised()).toBe(false)
  })

  it("minimises only on the exact stored string, not on anything truthy", () => {
    expect(parseMinimised("true")).toBe(true)
    expect(parseMinimised("false")).toBe(false)
    // A value this module did not write is not a choice. "1", "yes" and a stale JSON blob all read
    // as expanded rather than being coerced into hiding the labels.
    expect(parseMinimised("1")).toBe(false)
    expect(parseMinimised("yes")).toBe(false)
    expect(parseMinimised('{"minimised":true}')).toBe(false)
    expect(parseMinimised("")).toBe(false)
  })

  it("round-trips a choice through the store", () => {
    writeMinimised(true)
    expect(window.localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("true")
    expect(readMinimised()).toBe(true)

    writeMinimised(false)
    expect(readMinimised()).toBe(false)
  })

  it("keeps the two widths at the values DESIGN.md argues", () => {
    // 240px expanded, within 6px of mock v1's 246 and 6x the 40px frame. 48px minimised, which
    // settles the contradiction between the colour ramp's "48px column" and the shipped rail's 40px.
    expect(SIDEBAR_WIDTH_EXPANDED).toBe("15rem")
    expect(SIDEBAR_WIDTH_MINIMISED).toBe("3rem")
  })
})
