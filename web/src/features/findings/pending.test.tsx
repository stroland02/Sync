import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { Absent } from "@/components/status"
import { Pending } from "@/features/findings/pending"

/**
 * Owner decision 36: four states, and none may collapse into another.
 *
 * These assert on what a reader sees, not on class names -- the console's vitest scope is
 * classification and structural invariants, and a snapshot here would fail on every restyle.
 */
describe("a value that has not arrived yet", () => {
  it("renders the word rather than a shape", () => {
    render(<Pending />)

    expect(screen.getByText("loading")).toBeTruthy()
  })

  it("reads differently from a value that is absent", () => {
    const { container: pending } = render(<Pending />)
    const { container: absent } = render(<Absent>no feed recorded</Absent>)

    expect(pending.textContent).not.toBe(absent.textContent)
  })

  it("reads differently from a measured zero", () => {
    // The case this exists for. A skeleton and a `0` occupy the same space and a reader completes
    // the shape; the word cannot be mistaken for a figure.
    const { container: pending } = render(<Pending />)
    const { container: zero } = render(<span>0</span>)

    expect(pending.textContent).not.toBe(zero.textContent)
    expect(pending.textContent).not.toMatch(/^\d+$/)
  })

  it("reads differently from a source that could not answer", () => {
    const { container: pending } = render(<Pending />)
    const { container: cannotTell } = render(<Absent>the API did not answer</Absent>)

    expect(pending.textContent).not.toBe(cannotTell.textContent)
  })

  it("lets a caller say what is loading without becoming a shape", () => {
    render(<Pending>loading the run</Pending>)

    expect(screen.getByText("loading the run")).toBeTruthy()
  })
})
