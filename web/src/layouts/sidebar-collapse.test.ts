/**
 * What the sidebar reveals, what the frame reserves, and what it remembers.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation, never class names.
 * The widths are asserted as values because `DESIGN.md` argues them and a silent drift from the
 * argued number is the defect — not because a pixel is being tested.
 *
 * **Two derivations, not one, and keeping them apart is the whole point.** `sidebarState` answers
 * what the panel draws; `railState` answers what the content column has taken from it. A hover
 * moves the first and must never move the second, or every pointer that crosses the rail reflows
 * the page beside it.
 */

import { afterEach, describe, expect, it } from "vitest"

import {
  SIDEBAR_STORAGE_KEY,
  SIDEBAR_WIDTH,
  SIDEBAR_WIDTH_EXPANDED,
  SIDEBAR_WIDTH_MINIMISED,
  parsePinned,
  railState,
  readPinned,
  sidebarState,
  writePinned,
} from "@/layouts/sidebar-collapse"

afterEach(() => {
  window.localStorage.clear()
})

describe("the remembered pin", () => {
  it("reads an absent choice as unpinned, so hover-expand is what a reader who never chose gets", () => {
    // This reverses the pre-hover default deliberately. The old module defaulted to expanded and
    // argued it: "defaulting the other way would hide every destination's name from someone who
    // never asked". Hover-expand retires that argument rather than overruling it — the names are
    // one pointer-move away and arrive without a decision — and the owner asked for the rail to be
    // the default behaviour, with the pin kept for anyone who wants it held open.
    expect(parsePinned(null)).toBe(false)
    expect(readPinned()).toBe(false)
  })

  it("pins only on the exact stored string, not on anything truthy", () => {
    expect(parsePinned("true")).toBe(true)
    expect(parsePinned("false")).toBe(false)
    // A value this module did not write is not a choice. "1", "yes" and a stale JSON blob all read
    // as unpinned rather than being coerced into holding the panel open.
    expect(parsePinned("1")).toBe(false)
    expect(parsePinned("yes")).toBe(false)
    expect(parsePinned('{"pinned":true}')).toBe(false)
    expect(parsePinned("")).toBe(false)
  })

  it("round-trips a choice through the store", () => {
    writePinned(true)
    expect(window.localStorage.getItem(SIDEBAR_STORAGE_KEY)).toBe("true")
    expect(readPinned()).toBe(true)

    writePinned(false)
    expect(readPinned()).toBe(false)
  })

  it("keeps the two widths at the values DESIGN.md argues", () => {
    // 240px expanded, within 6px of mock v1's 246 and 6x the 40px frame. 48px minimised, which
    // settles the contradiction between the colour ramp's "48px column" and the shipped rail's 40px.
    expect(SIDEBAR_WIDTH_EXPANDED).toBe("15rem")
    expect(SIDEBAR_WIDTH_MINIMISED).toBe("3rem")
    expect(SIDEBAR_WIDTH.expanded).toBe(SIDEBAR_WIDTH_EXPANDED)
    expect(SIDEBAR_WIDTH.minimised).toBe(SIDEBAR_WIDTH_MINIMISED)
  })
})

describe("what the panel draws", () => {
  it("stays a rail when nothing points at it and nothing inside it holds focus", () => {
    expect(sidebarState({ pinned: false, pointerInside: false, focusInside: false })).toBe(
      "minimised"
    )
  })

  it("expands while the pointer is inside it", () => {
    expect(sidebarState({ pinned: false, pointerInside: true, focusInside: false })).toBe("expanded")
  })

  it("expands while focus is inside it, so a keyboard reader is never left in a rail", () => {
    // Hover alone would make the labels unreachable without a pointer. Focus is the second channel
    // and it is not optional: tabbing into the sidebar has to show what is being tabbed through.
    expect(sidebarState({ pinned: false, pointerInside: false, focusInside: true })).toBe("expanded")
  })

  it("holds open while focus stays inside after the pointer has left", () => {
    expect(sidebarState({ pinned: false, pointerInside: false, focusInside: true })).toBe("expanded")
  })

  it("stays expanded when pinned, whatever the pointer is doing", () => {
    for (const pointerInside of [true, false]) {
      for (const focusInside of [true, false]) {
        expect(sidebarState({ pinned: true, pointerInside, focusInside })).toBe("expanded")
      }
    }
  })
})

describe("what the frame reserves", () => {
  it("reserves the rail width until the reader pins it, so a hover never reflows the content", () => {
    // The reveal is an overlay. If the reserved width tracked the revealed one, the whole content
    // column would jump 192px sideways every time a pointer crossed the rail on its way somewhere
    // else — which is a worse fault than the width the rail was saving.
    expect(railState(false)).toBe("minimised")
    expect(railState(true)).toBe("expanded")
  })
})
