/**
 * The binding status tag: what a call's status says, and what it refuses to say with colour.
 *
 * **Owner question, 2026-08-19: "why do we not show safe APIs?"** This is the answer's render
 * side. The claim under test is the one with a wrong answer — that `unchecked` reads as its own
 * fact rather than as a mild version of `clean`, because a reader skimming past it is exactly the
 * failure the third member exists to prevent.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { BINDING_STATUSES } from "@/api/types"
import { BINDING_STATUS_TONE, BindingStatusTag, SEVERITY_TONE } from "@/components/tag"

afterEach(cleanup)

describe("what a binding status says", () => {
  it("renders every member of the closed vocabulary as a word", () => {
    // No member falls through to its raw payload key: `at_risk` on screen is the console showing
    // a reader a column name.
    for (const status of BINDING_STATUSES) {
      cleanup()
      render(<BindingStatusTag status={status} />)
      expect(screen.getByText(/at risk|clean|not checked/)).toBeTruthy()
    }
  })

  it("says 'not checked' rather than anything that reads as clean", () => {
    render(<BindingStatusTag status="unchecked" />)

    const text = screen.getByText(/not checked/).textContent ?? ""
    expect(text).not.toMatch(/\bsafe\b|\bok\b|\bfine\b/i)
  })

  it("carries what each member means, so the vocabulary is not learned elsewhere", () => {
    const { container } = render(<BindingStatusTag status="unchecked" />)

    // The distinction has to travel with the value: `unchecked` is not a weaker `clean`, and the
    // reason is that nothing was examined.
    expect(container.firstElementChild?.getAttribute("title")).toMatch(/never been read/i)
  })

  it("states that a decline or a failed fetch is not evidence", () => {
    // The trap this closes: counting any intake attempt rather than a successful one would turn
    // a week of 403s into an all-clear.
    const { container } = render(<BindingStatusTag status="unchecked" />)

    expect(container.firstElementChild?.getAttribute("title")).toMatch(/decline|failed fetch/i)
  })

  it("says clean is a measured answer rather than an absent one", () => {
    const { container } = render(<BindingStatusTag status="clean" />)

    expect(container.firstElementChild?.getAttribute("title")).toMatch(/measured answer/i)
  })

  it("renders a status outside the vocabulary as itself rather than as nothing", () => {
    // A payload this console has not caught up with is rendered honestly — the same rule
    // `lib/format.ts` applies to an unrecognised rung.
    render(<BindingStatusTag status="quarantined" />)

    expect(screen.getByText("quarantined")).toBeTruthy()
  })
})

describe("what the tone claims, and what it must not", () => {
  it("never tones at_risk as gravely as a breaking change", () => {
    // `at_risk` means an open finding names this operation, of any severity. Wearing the same
    // tone as `breaking` would claim a grade the status does not carry; the severity tag beside
    // it is what ranks the finding.
    expect(BINDING_STATUS_TONE.at_risk).not.toBe(SEVERITY_TONE.breaking)
  })

  it("tones unchecked rather than leaving it neutral", () => {
    // The one way this feature fails its reader is by being skimmed past as a milder clean.
    expect(BINDING_STATUS_TONE.unchecked).toBe("warning")
    expect(BINDING_STATUS_TONE.unchecked).not.toBe(BINDING_STATUS_TONE.clean)
  })

  it("gives an unrecognised status no tone at all", () => {
    // Colouring a value the console has not caught up with is a confident wrong verdict.
    render(<BindingStatusTag status="quarantined" />)

    expect(screen.getByText("quarantined").getAttribute("data-tone")).toBe("neutral")
  })

  it("never lets a tone travel without its word", () => {
    // The owner's re-ruling kept this discipline from the monochrome one it replaced.
    for (const status of BINDING_STATUSES) {
      cleanup()
      render(<BindingStatusTag status={status} />)
      const text = screen.getByText(/at risk|clean|not checked/).textContent ?? ""
      expect(text.trim().length).toBeGreaterThan(0)
    }
  })
})
