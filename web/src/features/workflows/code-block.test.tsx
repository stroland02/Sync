/**
 * The anchored code block: what a reviewer sees of `tsc`'s output and the replay's.
 *
 * `code-anchors.test.ts` holds the parsing. This holds that the component spends it — that an
 * anchored line renders its `file:line` address as its own element, and that a long span is
 * collapsed with a control that says how much is hidden rather than either truncated silently or
 * dumped whole. Structure only: no class names, no snapshots.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { VISIBLE_LINE_BUDGET } from "@/features/workflows/code-anchors"
import { CodeBlock } from "@/features/workflows/code-block"

afterEach(cleanup)

function block(count: number): string {
  return Array.from(
    { length: count },
    (_, index) => `src/billing/client.ts(${index + 1},3): error TS2551: no such property`,
  ).join("\n")
}

describe("the anchored code block", () => {
  it("renders one row per line, each anchored line carrying its file:line address", () => {
    const { container } = render(<CodeBlock text={block(3)} />)

    const rows = container.querySelectorAll("ol > li")
    expect(rows).toHaveLength(3)
    expect(screen.getByText("src/billing/client.ts:1")).not.toBeNull()
    expect(screen.getByText("src/billing/client.ts:3")).not.toBeNull()
  })

  it("carries an unanchored line through unchanged rather than dropping it", () => {
    const { container } = render(
      <CodeBlock text={"src/a.ts(1,1): error TS1: one\nFound 1 error in 1 file."} />,
    )

    expect(container.querySelectorAll("ol > li")).toHaveLength(2)
    expect(screen.getByText("Found 1 error in 1 file.")).not.toBeNull()
  })

  it("offers no disclosure when the whole block already fits", () => {
    render(<CodeBlock text={block(VISIBLE_LINE_BUDGET)} />)

    expect(screen.queryByRole("button", { name: /show/i })).toBeNull()
  })

  it("collapses a long span, names how many lines there are, and reveals them all on request", () => {
    const total = VISIBLE_LINE_BUDGET + 9
    const { container } = render(<CodeBlock text={block(total)} />)

    expect(container.querySelectorAll("ol > li")).toHaveLength(VISIBLE_LINE_BUDGET)

    const more = screen.getByRole("button", { name: new RegExp(`${total}`) })
    fireEvent.click(more)

    expect(container.querySelectorAll("ol > li")).toHaveLength(total)

    fireEvent.click(screen.getByRole("button", { name: /show fewer/i }))
    expect(container.querySelectorAll("ol > li")).toHaveLength(VISIBLE_LINE_BUDGET)
  })
})
