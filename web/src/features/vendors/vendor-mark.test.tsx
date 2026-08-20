/**
 * The vendor mark — test suite for fetch, degradation and identity.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification, derivation and structural
 * invariants. Never class names, never snapshots.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { VendorMark, monogramFor, vendorMarkUrl } from "@/features/vendors/vendor-mark"

afterEach(cleanup)

describe("vendorMarkUrl", () => {
  it("points at a well-known endpoint keyed on the vendor's domain", () => {
    expect(vendorMarkUrl("stripe")).toContain("stripe.com")
  })

  it("does not build a url from an id that cannot be a hostname", () => {
    expect(vendorMarkUrl("")).toBeNull()
    expect(vendorMarkUrl("../etc/passwd")).toBeNull()
    expect(vendorMarkUrl("a b")).toBeNull()
  })
})

describe("monogramFor", () => {
  it("takes the first character of the id, upper-cased", () => {
    expect(monogramFor("stripe")).toBe("S")
  })

  it("takes an initial from each part of a compound id", () => {
    expect(monogramFor("google-maps")).toBe("GM")
    expect(monogramFor("aws_s3")).toBe("AS")
  })

  it("never returns more than two characters", () => {
    expect(monogramFor("a-b-c-d-e")).toHaveLength(2)
  })

  it("falls back to a placeholder when the id yields no letters", () => {
    expect(monogramFor("")).toBe("?")
  })
})

describe("VendorMark", () => {
  it("fetches a mark rather than drawing one", () => {
    render(<VendorMark vendorId="stripe" />)

    const img = screen.getByTestId("vendor-mark-image")
    expect(img.getAttribute("src")).toBe(vendorMarkUrl("stripe"))
  })

  /**
   * The id beside it is the identity. The mark is an aid to finding a row, so it carries no
   * alternative text — a screen reader announcing "stripe" twice is worse than announcing it once.
   */
  it("is decorative, because the vendor id is the identity", () => {
    render(<VendorMark vendorId="stripe" />)

    expect(screen.getByTestId("vendor-mark-image").getAttribute("alt")).toBe("")
  })

  it("degrades to a monogram when no mark is served", () => {
    render(<VendorMark vendorId="stripe" />)

    fireEvent.error(screen.getByTestId("vendor-mark-image"))

    expect(screen.queryByTestId("vendor-mark-image")).toBeNull()
    expect(screen.getByTestId("vendor-mark-monogram").textContent).toBe("S")
  })

  it("degrades to a monogram without attempting a fetch when the id cannot be a hostname", () => {
    render(<VendorMark vendorId="a b" />)

    expect(screen.queryByTestId("vendor-mark-image")).toBeNull()
    expect(screen.getByTestId("vendor-mark-monogram").textContent).toBe("AB")
  })
})
