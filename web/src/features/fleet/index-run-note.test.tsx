/**
 * Decision 61's "what was checked", now that a pass is a recorded fact.
 *
 * The empty table was ruled to state what was checked and name one next action. I left that
 * unbuilt because nothing recorded an index pass -- writing "4 detectors ran 14 minutes ago"
 * would have been inventing the fact it reports. `index_run` records it now, so the sentence can
 * be true.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import type { IndexRunSummary } from "@/api/types"
import { IndexRunNote } from "@/features/fleet/index-run-note"

afterEach(cleanup)

const completed: IndexRunSummary = {
  started_at: "2026-08-18T12:00:00Z",
  finished_at: "2026-08-18T12:00:30Z",
  outcome: "completed",
  call_sites: 1204,
}

describe("IndexRunNote", () => {
  it("says the index has never run, rather than implying it ran and found nothing", () => {
    render(<IndexRunNote run={null} />)

    expect(screen.getByText(/never been indexed/i)).not.toBeNull()
  })

  it("states what a completed pass checked and when", () => {
    render(<IndexRunNote run={completed} />)

    const text = screen.getByRole("note").textContent ?? ""
    expect(text).toMatch(/1,204 call sites/)
    expect(text).toMatch(/ago/)
  })

  it("says a pass is still running rather than reporting it as a result", () => {
    render(
      <IndexRunNote run={{ ...completed, finished_at: null, outcome: null, call_sites: null }} />
    )

    const text = screen.getByRole("note").textContent ?? ""
    expect(text).toMatch(/still running|has not finished/i)
    // No count while in flight: a partial one would read as the size of the codebase.
    expect(text).not.toMatch(/1,204/)
  })

  it("says the rows a failed pass left are partial, rather than letting them read as complete", () => {
    render(
      <IndexRunNote run={{ ...completed, outcome: "failed", call_sites: null }} />
    )

    expect(screen.getByRole("note").textContent).toMatch(/did not finish|partial/i)
  })
})
