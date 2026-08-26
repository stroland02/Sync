/**
 * An abandon reason is unbounded subprocess output, and nothing may size itself from it.
 *
 * A `tsc` run that fails its baseline check writes the compiler's whole `--help` text into
 * `abandon_reason`. Rendered straight, one run drew a row about a thousand pixels tall and pushed
 * every other run off the screen — so the guard here is that a long reason is clamped, and that
 * clamping it never becomes silent truncation: the count of what is behind the disclosure is on
 * screen, and the exact text is still in the DOM rather than cut away.
 *
 * **Moved from `features/fleet/abandon-reason.test.tsx` with its subject.** `runs-table.tsx` was
 * deleted in the Runs rebuild and `AbandonReason` moved to `features/runs/abandon-reason.tsx` — it
 * is the one export of that file with a life beyond the deleted card, and it now renders in the run
 * record drawer rather than inside a table cell. The component is unchanged and so are these
 * assertions; only the import moved.
 *
 * Every query is scoped to its own render's container. `document` accumulates the containers of
 * every earlier case in the file, so a document-wide `querySelector("details")` in the last test
 * finds the disclosure the second test rendered and reports a pass or a failure about the wrong
 * subject entirely.
 */

import { render, within } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { AbandonReason } from "@/features/runs/abandon-reason"

const LONG = `RuntimeError: could not establish a typecheck baseline for /tmp/repo: ${"tsc --help output ".repeat(200)}`
const SHORT = "the remediator produced no change"

describe("AbandonReason", () => {
  it("shows a short reason whole, with nothing to expand", () => {
    const { container } = render(<AbandonReason reason={SHORT} />)

    expect(within(container).getByText(SHORT)).toBeTruthy()
    // No disclosure: a reader pressing to reveal what is already fully on screen learns nothing.
    expect(container.querySelector("details")).toBeNull()
  })

  it("clamps a long reason behind a disclosure rather than rendering it whole", () => {
    const { container } = render(<AbandonReason reason={LONG} />)

    const summary = container.querySelector("summary")
    expect(summary).not.toBeNull()
    // The head of the string is what a reader needs — the error class and what failed.
    expect(summary!.textContent).toContain("RuntimeError: could not establish a typecheck baseline")
    // The clamp is real: the summary carries a small fraction of a reason this long.
    expect(summary!.textContent!.length).toBeLessThan(LONG.length / 2)
  })

  it("says how much is behind the disclosure, so the clamp is not a silent truncation", () => {
    const { container } = render(<AbandonReason reason={LONG} />)

    expect(
      within(container).getByText(`show all ${LONG.length.toLocaleString()} characters`),
    ).toBeTruthy()
  })

  it("keeps the exact text, so nothing is dropped by being clamped", () => {
    const { container } = render(<AbandonReason reason={LONG} />)

    expect(container.querySelector("pre")!.textContent).toBe(LONG)
  })

  it("says which nothing it is when no reason was recorded", () => {
    // An abandoned run with no reason is a dropped record, and the absence vocabulary is what
    // keeps it from reading as a run that gave up for no reason anybody can look up.
    const { container } = render(<AbandonReason reason={null} />)

    expect(container.querySelector("details")).toBeNull()
    expect(container.querySelector("pre")).toBeNull()
  })
})
