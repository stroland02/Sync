/**
 * The sidebar is one component at two widths, and this is the test that decides it.
 *
 * `references/direction/NOTES.md` entry 6 states the discriminator: **an icon must not move
 * vertically when the sidebar collapses.** If it moves, expanding added a column of chrome rather
 * than widening one list, and the thing built is an icon rail plus a contextual panel — which the
 * owner ruled against on 2026-08-06 and which this item's first dispatch built.
 *
 * **jsdom has no layout, so vertical position cannot be read directly** — `getBoundingClientRect`
 * returns zeroes here. Saying so matters, because a test that asserted on those numbers would pass
 * against any tree at all. What is asserted instead is the structural cause: the ordered sequence of
 * rows in the list is identical in both states, and the group headings still occupy their rows when
 * collapsed. An icon can only move if a row above it appears or disappears, so a list whose row
 * sequence is invariant is a list whose icons hold their positions. The pixels are measured in Chrome
 * and recorded in `docs/superpowers/BACKLOG.md`; this holds the property that makes that measurement
 * come out right.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { AppFrame } from "@/layouts/app-frame"
import { AREAS, ROUTES } from "@/lib/routes"

afterEach(cleanup)

// jsdom reports a 1024px window, which is below the width at which the frame opens the sidebar, so
// without this every test here would start collapsed by accident rather than by choice. Setting it
// makes the starting state deliberate and lets the toggle assertions below name a direction.
beforeEach(() => {
  window.innerWidth = 1600
})

function renderFrame() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <AppFrame />
    </MemoryRouter>
  )
}

/** Every row of the one list, in document order: a heading reserves a row, a destination is a row. */
function rowShape(container: HTMLElement): string[] {
  return [...container.querySelectorAll("nav ul > li")].map((li) => {
    const destination = li.querySelector("[data-destination]")
    return destination === null
      ? `heading:${li.textContent?.trim()}`
      : `destination:${destination.getAttribute("data-destination")}`
  })
}

function toggle(container: HTMLElement): HTMLElement {
  const button = container.querySelector("nav button")
  if (button === null) throw new Error("the sidebar has no collapse toggle")
  return button as HTMLElement
}

/**
 * Click the toggle and assert the state actually changed.
 *
 * The assertion is here rather than in one test because of what happened without it: the first draft
 * called `element.click()` directly, React never flushed the update outside `act`, and every
 * assertion below compared the expanded tree against itself. All of them passed. A test that cannot
 * fail is worse than no test, and the whole file was one — `fireEvent` wraps in `act`, and reading
 * `aria-expanded` back proves the collapse happened before anything is compared.
 */
function collapse(container: HTMLElement): void {
  const before = toggle(container).getAttribute("aria-expanded")
  fireEvent.click(toggle(container))
  expect(toggle(container).getAttribute("aria-expanded")).not.toBe(before)
}

describe("the sidebar is one list at two widths", () => {
  it("keeps every row in the same order when it collapses, so no icon can move", () => {
    const { container } = renderFrame()
    const expanded = rowShape(container)

    collapse(container)
    const collapsed = rowShape(container)

    expect(collapsed).toEqual(expanded)
  })

  it("adds no row and drops none, which is the other half of not moving", () => {
    const { container } = renderFrame()
    const expanded = rowShape(container)

    collapse(container)

    // A count assertion on its own would pass if one row were swapped for another, and the order
    // assertion above would pass on an empty list. Both, plus this, is what closes it.
    expect(rowShape(container)).toHaveLength(expanded.length)
    expect(expanded.length).toBe(ROUTES.length + AREAS.length)
  })

  it("still occupies the group headings' rows when collapsed", () => {
    // The structural cause of the property above. A heading that rendered nothing when collapsed
    // would take its row out of the flow and every icon below it would rise — which is what "two
    // layouts rather than one at two widths" looks like in a DOM.
    const { container } = renderFrame()

    collapse(container)

    const headings = rowShape(container).filter((row) => row.startsWith("heading:"))
    expect(headings).toHaveLength(AREAS.length)
  })

  it("renders every declared destination at both widths", () => {
    // The collapse must change density, never reachability. The first version of this chassis left
    // four area icons behind when collapsed and the nine levels were unreachable without expanding.
    const { container } = renderFrame()
    const paths = () =>
      [...container.querySelectorAll("[data-destination]")].map((el) =>
        el.getAttribute("data-destination")
      )

    expect(paths()).toEqual(ROUTES.map((route) => route.path))

    collapse(container)

    expect(paths()).toEqual(ROUTES.map((route) => route.path))
  })
})

describe("a collapsed row keeps its label semantically", () => {
  it("names every destination for a screen reader at both widths", () => {
    const { container } = renderFrame()

    collapse(container)

    for (const route of ROUTES) {
      const row = container.querySelector(`[data-destination="${route.path}"]`)
      expect(row?.getAttribute("aria-label")).toContain(route.label)
      // The tooltip is the sighted reader's equivalent of the accessible name, so it carries the
      // same string rather than a shortened one.
      expect(row?.getAttribute("title")).toBe(row?.getAttribute("aria-label"))
    }
  })

  it("carries where a subject comes from on the routes that need one", () => {
    // `reachedFrom` was a line of prose in the panel this replaced. Prose cannot be a row here — a
    // sentence rendering expanded and not collapsed changes the height above every icon beneath it —
    // so it rides the accessible name at both widths instead of appearing at one.
    const { container } = renderFrame()

    for (const route of ROUTES.filter((r) => r.params.length > 0)) {
      const row = container.querySelector(`[data-destination="${route.path}"]`)
      expect(row?.getAttribute("aria-label")).toContain(route.reachedFrom ?? "")
    }
  })

  it("keeps the toggle reachable and labelled in both states", () => {
    const { container } = renderFrame()

    expect(toggle(container).getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByTitle("Collapse the sidebar")).toBeTruthy()

    fireEvent.click(toggle(container))

    expect(toggle(container).getAttribute("aria-expanded")).toBe("false")
    expect(screen.getByTitle("Expand the sidebar")).toBeTruthy()

    fireEvent.click(toggle(container))

    // Back again, because a toggle that only works once is a toggle that has state and no inverse.
    expect(toggle(container).getAttribute("aria-expanded")).toBe("true")
  })

  it("starts collapsed on a window too narrow to spend the width on labels", () => {
    // The other side of the `beforeEach` above, asserted rather than left implicit: the default is a
    // measurement about content width, not a preference, and B115 carries the numbers.
    window.innerWidth = 1280
    const { container } = renderFrame()

    expect(toggle(container).getAttribute("aria-expanded")).toBe("false")
  })
})
