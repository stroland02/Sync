/**
 * The integration mark: drawn here, fetched from nowhere.
 *
 * The claim that matters most is a negative one — **no network request leaves the browser for a
 * vendor's logo**. That fetch used to exist, it was on by default, and it told a third party which
 * integrations a customer watches.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { SERIES_SLOTS } from "@/lib/palette"
import { VendorMark, monogramFor, slotFor } from "@/features/vendors/vendor-mark"

afterEach(cleanup)

describe("the monogram", () => {
  it("takes one letter per part of the id, at most two", () => {
    expect(monogramFor("stripe")).toBe("S")
    expect(monogramFor("google-maps")).toBe("GM")
    // A third letter stops being a monogram and starts being a truncated word.
    expect(monogramFor("a-b-c-d")).toBe("AB")
  })

  it("answers for an id with no letters in it at all", () => {
    expect(monogramFor("---")).toBe("?")
  })
})

describe("the palette slot", () => {
  it("is the same for one vendor however often it is asked", () => {
    // A mark that changed colour between two screens would read as two different integrations.
    expect(slotFor("stripe")).toBe(slotFor("stripe"))
  })

  it("does not depend on what else is on screen", () => {
    // Hashed from the id rather than assigned by position, which is the whole reason it is stable.
    expect(slotFor("twilio")).toBe(slotFor("twilio"))
    expect(slotFor("stripe")).not.toBe(undefined)
  })

  it("only ever returns a colour the design contract already argues", () => {
    // No generated hue: these slots have their contrast proven in DESIGN.md.
    for (const id of ["stripe", "openai", "twilio", "anthropic", "github", "zz-unknown-vendor"]) {
      expect(SERIES_SLOTS as readonly string[]).toContain(slotFor(id))
    }
  })
})

describe("what the mark renders", () => {
  it("reaches no third party, whichever mark it draws", () => {
    const { container } = render(<VendorMark vendorId="stripe" />)

    // The durable claim, and it is about the ORIGIN rather than the element. This asserted "no
    // `img` at all" while the monogram was the only mark; bundling logos (owner ruling
    // 2026-08-25) makes an `img` legitimate, so asserting its absence would now fail for a
    // reason that has nothing to do with what the rule protects. What must never come back is a
    // remote source: that endpoint learned which integrations a customer watches, and it made
    // the console's appearance depend on a network nobody here controls.
    for (const img of container.querySelectorAll("img")) {
      const src = img.getAttribute("src") ?? ""
      expect(src).not.toMatch(/^https?:|^\/\//)
    }
    expect(screen.getByTestId("vendor-mark-monogram").textContent).toBe("S")
  })

  it("names the vendor for a pointer without reading it twice to a screen reader", () => {
    render(<VendorMark vendorId="openai" />)

    const mark = screen.getByTestId("vendor-mark-monogram")
    expect(mark.getAttribute("title")).toBe("OpenAI")
    expect(mark.getAttribute("aria-hidden")).toBe("true")
  })
})
