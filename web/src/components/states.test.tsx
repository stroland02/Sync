/**
 * A failed panel has to offer a way back.
 *
 * The empty-state walk (`reports/2026-08-17-gate-3-empty-state.md`) established that the console
 * already says *which* state it is in — a failed fetch renders "the API did not answer" rather
 * than a zero — so this is an affordance gap rather than an honesty one. Without it the only
 * recourse is a full page reload, which re-fetches every other panel, loses the reader's scroll
 * position and discards any filter they set.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: what kind of thing is on screen and what it does
 * when used, never a class name and never a snapshot.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ErrorState } from "@/components/states"

afterEach(cleanup)

describe("ErrorState's retry", () => {
  it("offers no control when the caller cannot retry, rather than a dead button", () => {
    render(<ErrorState error={new Error("nope")} what="the runs" />)

    expect(screen.queryByRole("button", { name: /try again/i })).toBeNull()
  })

  it("calls the caller's retry when one is given", () => {
    const onRetry = vi.fn()
    render(<ErrorState error={new Error("nope")} what="the runs" onRetry={onRetry} />)

    fireEvent.click(screen.getByRole("button", { name: /try again/i }))

    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it("still says what failed, because a retry control must not replace the explanation", () => {
    render(<ErrorState error={new Error("nope")} what="the runs" onRetry={() => {}} />)

    // The headline names the failure; the button is an addition to it, not a substitute.
    expect(screen.getByRole("button", { name: /try again/i })).not.toBeNull()
    expect(document.body.textContent).toContain("nope")
  })
})
