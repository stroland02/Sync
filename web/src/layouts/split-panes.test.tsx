/**
 * Structure only, per `web/CLAUDE.md`: what is a sibling of what, and in what reading order.
 *
 * Never class names and never a snapshot — jsdom loads no stylesheet, so nothing here is evidence
 * that anything scrolls or that a track is 5fr wide. That evidence is measured in Chrome and
 * written into `DESIGN.md`. What this file can hold is the contract a caller depends on: the header
 * renders once and outside both panes, and each pane's children survive the layout.
 */

import { cleanup, render, screen, within } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { SplitPanes } from "@/layouts/split-panes"

afterEach(cleanup)

function renderSplit() {
  return render(
    <SplitPanes
      header={<h1>run identity</h1>}
      left={<section aria-label="Evidence">what it read</section>}
      right={<section aria-label="Remediation">what it wrote</section>}
    />,
  )
}

describe("SplitPanes", () => {
  it("renders the header once, outside both panes", () => {
    renderSplit()

    const header = screen.getByRole("heading", { name: "run identity" })
    expect(header).not.toBeNull()
    // Proved RED by returning only `left`: the header vanished with the panes it heads.
    expect(within(screen.getByRole("region", { name: "Evidence" })).queryByRole("heading")).toBeNull()
    expect(
      within(screen.getByRole("region", { name: "Remediation" })).queryByRole("heading"),
    ).toBeNull()
  })

  it("renders both panes at once, addressable by name", () => {
    renderSplit()

    expect(screen.getByRole("region", { name: "Evidence" }).textContent).toBe("what it read")
    expect(screen.getByRole("region", { name: "Remediation" }).textContent).toBe("what it wrote")
  })

  it("reads header, then evidence, then remediation", () => {
    const { container } = renderSplit()

    const text = container.textContent ?? ""
    expect(text.indexOf("run identity")).toBeLessThan(text.indexOf("what it read"))
    expect(text.indexOf("what it read")).toBeLessThan(text.indexOf("what it wrote"))
  })
})
