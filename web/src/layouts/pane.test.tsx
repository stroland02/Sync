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

  it("stamps `locked` only when a screen asks to own its scrollbars", () => {
    // The stamp is what `main`'s `:has([data-screen=locked])` reads. A screen that does not ask
    // must not carry it, or every screen loses the page scroll at once.
    expect(bandOf("locked").getAttribute("data-screen")).toBe("locked")
    expect(bandOf("flow").getAttribute("data-screen")).toBeNull()
    expect(bandOf("fill").getAttribute("data-screen")).toBeNull()
  })

  it("leaves the flow layout growing, and bounds the other two", () => {
    expect(bandOf("flow").className).not.toContain("min-h-0")
    expect(bandOf("fill").className).toContain("min-h-0")
    expect(bandOf("locked").className).toContain("min-h-0")
  })
})
