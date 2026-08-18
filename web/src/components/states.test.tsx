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

import { NotFoundError } from "@/api/errors"
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

/**
 * A 404 says a URL did not resolve. It does not say what the API holds.
 *
 * B147 is the case that proves the difference: `/api/repositories/{repo_id}/coverage` uses
 * Starlette's default path converter, which cannot match a repo_id containing slashes, so a
 * repository `/api/repositories` demonstrably lists answers 404 anyway. The old copy read "The
 * API does not hold that identifier" and that sentence was false on screen — the API holds the
 * repository, the route never resolved. Two 404s reach this panel and the response cannot tell
 * them apart, so the copy must not choose between them.
 */
describe("ErrorState on a 404", () => {
  /** The B147 shape: no route matched, so the body is not the API's JSON and the id is the path. */
  const routeMissed = new NotFoundError(
    "not found",
    "/api/repositories/github.com%2Fstripe%2Fdemo/coverage",
    "/api/repositories/github.com%2Fstripe%2Fdemo/coverage",
  )

  /** The API's own 404: a route resolved, and it named the record it does not hold. */
  const recordAbsent = new NotFoundError("finding not found", "f-123", "/api/findings/f-123")

  it("never claims the API lacks the identifier, because a 404 is not evidence of that", () => {
    for (const error of [routeMissed, recordAbsent]) {
      cleanup()
      render(<ErrorState error={error} what="index coverage" />)

      // Positive first, so the negative below cannot pass against an empty render.
      expect(document.body.textContent).toContain("404")
      expect(document.body.textContent).not.toContain("does not hold that identifier")
    }
  })

  it("states the status the API actually answered rather than a conclusion drawn from it", () => {
    render(<ErrorState error={routeMissed} what="index coverage" />)

    expect(document.body.textContent).toContain("404")
  })

  it("shows the failing URL, which the identifier alone does not give", () => {
    render(<ErrorState error={recordAbsent} what="the finding" />)

    expect(document.body.textContent).toContain("/api/findings/f-123")
  })

  it("keeps the message that came back with the 404 rather than paraphrasing it", () => {
    render(<ErrorState error={recordAbsent} what="the finding" />)

    expect(document.body.textContent).toContain("finding not found")
  })
})
