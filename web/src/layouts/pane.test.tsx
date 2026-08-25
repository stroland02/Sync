/**
 * The locked-layout primitives keep the chain that makes a pane scroll.
 *
 * Four classes, each load-bearing, and the failure is silent when one goes: without `min-h-0` a
 * flex child refuses to shrink below its content, so the column grows and the page finds a second
 * scrollbar nobody meant. That is why the chain is a component rather than a paragraph, and why
 * this asserts the classes rather than a rendered height — jsdom resolves no stylesheet, so a
 * computed-style assertion here would pass whatever the class said.
 */

import { cleanup, render } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { PanelPane } from "@/components/pane"
import { Pane, PaneScroll } from "@/layouts/pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"

afterEach(cleanup)

const RECORDS: StatusSegment[] = [{ kind: "records", label: "Rows", text: "1 row" }]

describe("the pane mechanic", () => {
  it("keeps every link of the shrink chain", () => {
    const { container } = render(
      <Pane>
        <PaneScroll>rows</PaneScroll>
      </Pane>
    )

    const pane = container.firstElementChild as HTMLElement
    for (const link of ["min-h-0", "min-w-0", "flex-1", "overflow-hidden"]) {
      expect(pane.className, `pane lost ${link}`).toContain(link)
    }

    const scroll = pane.firstElementChild as HTMLElement
    expect(scroll.className).toContain("min-h-0")
    expect(scroll.className).toContain("overflow-auto")
  })

  it("gives a pane exactly one scroll region, because two scrollbars over one body is unreadable", () => {
    const { container } = render(
      <PanelPane label="Call sites" footer="40 rows">
        rows
      </PanelPane>
    )

    expect(container.querySelectorAll(".overflow-auto")).toHaveLength(1)
  })

  it("pins the panel's footer outside the scroll, so a count cannot scroll away from its rows", () => {
    const { container } = render(
      <PanelPane label="Call sites" footer="40 rows">
        rows
      </PanelPane>
    )

    const footer = container.querySelector("footer")!
    expect(footer.className).toContain("shrink-0")
    expect(footer.closest(".overflow-auto")).toBeNull()
  })
})

describe("the screen layout union", () => {
  function bandOf(layout: "flow" | "fill" | "locked") {
    cleanup()
    const { container } = render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScreenFrame status={RECORDS} layout={layout}>
          <table />
        </ScreenFrame>
      </MemoryRouter>
    )
    return container.querySelector("[data-band='content']") as HTMLElement
  }

  it("stamps every bounded layout, and never a flowing one", () => {
    // The stamp does two jobs, and both read it through `:has()`: `locked` flips `main` to
    // `overflow-hidden`, and either stamp clamps the content box with `min-h-0`. A flowing
    // screen must carry neither -- that clamp is what held 986px of content at 869px and
    // clipped the rest, which is the regression this pair exists to stop.
    expect(bandOf("locked").getAttribute("data-screen")).toBe("locked")
    expect(bandOf("fill").getAttribute("data-screen")).toBe("fill")
    expect(bandOf("flow").getAttribute("data-screen")).toBeNull()
  })

  it("leaves the flow layout growing, and bounds the other two", () => {
    expect(bandOf("flow").className).not.toContain("min-h-0")
    expect(bandOf("fill").className).toContain("min-h-0")
    expect(bandOf("locked").className).toContain("min-h-0")
  })
})

/**
 * Nothing is clipped, on either kind of screen.
 *
 * Both halves of this shipped broken and the owner found them by scrolling, not a test. A flowing
 * screen carried `min-h-0` on its content box, which clamped it to the viewport so everything past
 * the fold was clipped rather than scrolled -- 986px of content held at 869px. A locked screen had
 * the inverse: its table was not bounded by any pane, grew to 1601px inside a 925px region, and
 * inflated the screen it was supposed to be bounded by.
 *
 * The two are one rule with two directions, which is why they are asserted together: a flowing
 * box must be free to grow, a bounded box must actually bound, and neither may clip.
 */
describe("neither layout clips its content", () => {
  it("leaves a flowing screen's box free to grow past the viewport", () => {
    cleanup()
    const { container } = render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScreenFrame status={RECORDS} layout="flow">
          <table />
        </ScreenFrame>
      </MemoryRouter>
    )

    const band = container.querySelector("[data-band='content']") as HTMLElement
    // `min-h-0` here is what clamped a flowing screen to the viewport. The frame applies it
    // through `:has([data-screen])`, so the absence of the stamp is what keeps this box free.
    expect(band.getAttribute("data-screen")).toBeNull()
    expect(band.className).not.toContain("min-h-0")
  })

  it("stamps a bounded screen so the frame clamps its box", () => {
    cleanup()
    for (const layout of ["fill", "locked"] as const) {
      cleanup()
      const { container } = render(
        <MemoryRouter initialEntries={["/settings"]}>
          <ScreenFrame status={RECORDS} layout={layout}>
            <table />
          </ScreenFrame>
        </MemoryRouter>
      )
      const band = container.querySelector("[data-band='content']") as HTMLElement
      expect(band.getAttribute("data-screen"), `${layout} lost its stamp`).toBe(layout)
    }
  })
})
