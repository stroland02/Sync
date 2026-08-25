import { cleanup, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"

// `globals` is unset in vitest.config.ts, so nothing cleans up between renders. Without this the
// band queries below read every prior test's DOM -- and the assertion that a band is ABSENT is
// exactly the one that fails spuriously when the previous test rendered one.
afterEach(cleanup)

const RECORDS: StatusSegment[] = [
  { kind: "records", label: "Changes", text: "Showing 1–25 of 61 changes." },
]

function band(name: string) {
  return document.querySelector(`[data-band="${name}"]`)
}

describe("ScreenFrame", () => {
  it("renders the controls band when a screen has controls", () => {
    render(
      <ScreenFrame controls={<button>Severity</button>} status={RECORDS}>
        <table />
      </ScreenFrame>
    )

    expect(document.querySelectorAll('[data-band="controls"]')).toHaveLength(1)
    expect(screen.getByRole("button", { name: "Severity" })).toBeTruthy()
  })

  it("renders NO controls band at all when a screen has none", () => {
    // Not an empty band, not a reserved height: no element. Four screens are genuinely
    // control-free, and a bar saying "nothing to narrow here" is chrome asserting an absence.
    render(
      <ScreenFrame status={RECORDS}>
        <table />
      </ScreenFrame>
    )

    expect(band("controls")).toBeNull()
  })

  it("always renders the content band", () => {
    render(
      <ScreenFrame status={RECORDS}>
        <p>rows</p>
      </ScreenFrame>
    )

    expect(band("content")).toBeTruthy()
    expect(screen.getByText("rows")).toBeTruthy()
  })

  it("always renders a status band holding at least one segment", () => {
    render(
      <ScreenFrame status={RECORDS}>
        <table />
      </ScreenFrame>
    )

    expect(band("status")).toBeTruthy()
    expect(document.querySelectorAll("[data-status-segment]").length).toBeGreaterThan(0)
    expect(screen.getByText("Showing 1–25 of 61 changes.")).toBeTruthy()
  })

  it("states why nothing counts rather than rendering a blank strip", () => {
    // `none` is a screen saying nothing here pages, with the reason. A blank band would draw
    // "no records" and "has not answered yet" as the same nothing.
    render(
      <ScreenFrame status={[{ kind: "none", why: "one subject — nothing here pages" }]}>
        <p>a finding</p>
      </ScreenFrame>
    )

    expect(band("status")).toBeTruthy()
    expect(screen.getByText("one subject — nothing here pages")).toBeTruthy()
  })

  it("renders the absence glyph for a figure nothing answered, never a zero", () => {
    render(
      <ScreenFrame status={[{ kind: "figure", label: "Call sites", value: null }]}>
        <table />
      </ScreenFrame>
    )

    const status = band("status")
    expect(status).toBeTruthy()
    expect(status?.textContent).not.toContain("0")
  })

  it("puts the bands in reading order: controls, then content", () => {
    render(
      <ScreenFrame controls={<button>Severity</button>} status={RECORDS}>
        <table />
      </ScreenFrame>
    )

    const controls = band("controls")!
    const content = band("content")!
    expect(controls.compareDocumentPosition(content) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})

/**
 * The page names itself once, in the content band, above everything it contains.
 *
 * Measured on the Findings screen before this moved: the `h1` rendered at **13px** while every
 * `h2` inside it rendered at 18px -- a page titled smaller than its own sections. The heading had
 * been living in the breadcrumb trail, where body size is correct for a trail segment and wrong
 * for a document's top-level heading.
 *
 * The size is asserted through the class rather than a computed style: jsdom resolves no
 * stylesheet, so `getComputedStyle` here would report the same thing whatever the class said,
 * and a test that cannot fail is worse than no test.
 */
describe("the page's heading", () => {
  it("renders once, in the content band, at the page step", () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScreenFrame status={RECORDS}>
          <table />
        </ScreenFrame>
      </MemoryRouter>
    )

    const headings = document.querySelectorAll("h1")
    expect(headings).toHaveLength(1)

    const heading = headings[0]
    expect(heading.className).toContain("text-page")
    // Not `text-body`, which is what it carried in the trail and what made it smaller than its
    // own sections.
    expect(heading.className).not.toContain("text-body")
  })

  it("comes before the controls, so a screen says what it is before how to narrow it", () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScreenFrame status={RECORDS} controls={<button>Severity</button>}>
          <table />
        </ScreenFrame>
      </MemoryRouter>
    )

    const heading = document.querySelector("h1")!
    const controls = band("controls")!
    expect(heading.compareDocumentPosition(controls) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("takes an explicit title over the registry's label", () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <ScreenFrame status={RECORDS} title="A better name" subtitle="What it answers.">
          <table />
        </ScreenFrame>
      </MemoryRouter>
    )

    expect(document.querySelector("h1")?.textContent).toBe("A better name")
    expect(document.body.textContent).toContain("What it answers.")
  })
})
