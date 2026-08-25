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
  it("reads an absent choice as pinned, so a reader who never chose gets the full sidebar", () => {
    // Flipped back on 2026-08-24 by the owner's Stitch specification: "a persistent 240px sidebar
    // with a collapsed 48px icon-only state". Persistent is the word that decides it. The rail
    // default and the argument that held it -- that a reveal answers the naming problem, so the
    // names are one pointer-move away -- are superseded rather than wrong. Hover-expand and the
    // pin both stay; what changed is which state an unchosen reader lands in.
    expect(parsePinned(null)).toBe(true)
    expect(readPinned()).toBe(true)
  })

  it("collapses only on the exact stored string, never on an unrecognised value", () => {
    expect(parsePinned("true")).toBe(true)
    expect(parsePinned("false")).toBe(false)
    // A value this module did not write is not a choice, and an unrecognised one must not collapse
    // the panel: "1", "yes" and a stale JSON blob all fall to the persistent default. Only the
    // exact string this module writes for "collapsed" collapses it.
    expect(parsePinned("1")).toBe(true)
    expect(parsePinned("yes")).toBe(true)
    expect(parsePinned('{"pinned":true}')).toBe(true)
    expect(parsePinned("")).toBe(true)
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
  it("reserves the full width while focus is inside, so a clicked row does not sit on top of the page", () => {
    // The defect this closes, seen in a screenshot of the running console: clicking a destination
    // leaves focus inside the sidebar, `sidebarState` keeps the panel expanded because focus holds
    // it open, and the frame had reserved only the rail — so a 240px panel sat on top of a page
    // laid out from x=48. The heading rendered as "W".
    //
    // The distinction that fixes it is transient versus persistent, not hover versus pin. A POINTER
    // is transient: the reader is looking at the sidebar, the overlay is what they are reading, and
    // reflowing the page under them would be worse. FOCUS is persistent: it survives the pointer
    // leaving, it survives a click, and while it is inside the sidebar the reader may be reading the
    // page. Persistent reveals reserve their width; only the pointer overlays.
    expect(railState({ pinned: false, pointerInside: false, focusInside: true })).toBe("expanded")
    expect(railState({ pinned: true, pointerInside: false, focusInside: false })).toBe("expanded")
    expect(railState({ pinned: false, pointerInside: false, focusInside: false })).toBe("minimised")
  })

  it("reserves exactly what the panel draws, on every input, so nothing is ever covered", () => {
    // The owner ruled against the overlay after seeing it: the sidebar pushes the page. So the
    // reserved box and the drawn panel must agree on every combination of inputs, not merely on the
    // ones a test happened to pick — a single disagreeing case is a state where the panel covers
    // content, which is the defect.
    for (const pinned of [true, false]) {
      for (const pointerInside of [true, false]) {
        for (const focusInside of [true, false]) {
          const reveal = { pinned, pointerInside, focusInside }
          expect(railState(reveal)).toBe(sidebarState(reveal))
        }
      }
    }
    expect(railState({ pinned: false, pointerInside: false, focusInside: false })).toBe("minimised")
    expect(railState({ pinned: true, pointerInside: false, focusInside: false })).toBe("expanded")
  })
})
