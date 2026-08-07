/**
 * A footer bar over a set with no second page carries the count and no pager.
 *
 * This is a structural invariant rather than a rendering one, which is why it sits here and not in
 * `DESIGN.md`: the question is whether a control exists, not what it looks like.
 * `runs-table.tsx` had already written the rule down — page controls over a set that fits on one
 * page are "a choice nobody has" — and enforced it by rendering no footer at all on that branch,
 * which is how the two longest screens in the console ended up with no record count anywhere under
 * their rows. Making the pager optional is what lets a complete listing have a footer, and this is
 * the guard that keeps a caller from getting two dead buttons instead.
 *
 * Shown red before the optional pager existed: the unpaged case rendered Previous and Next with
 * `undefined` in every paging prop, and the range read "Showing NaN–NaN of undefined".
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { FooterBar } from "@/layouts/footer-bar"

afterEach(cleanup)

describe("FooterBar", () => {
  it("renders no page controls for a complete listing", () => {
    render(<FooterBar left={<p>This is all 3 repositories.</p>} />)

    expect(screen.getByText("This is all 3 repositories.")).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Previous" })).toBeNull()
  })

  it("renders the pager when the caller has a page position to move", () => {
    render(
      <FooterBar
        offset={0}
        limit={50}
        shown={50}
        total={120}
        nextOffset={50}
        busy={false}
        onOffsetChange={() => {}}
      />
    )

    expect(screen.getByRole("button", { name: "Next" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Previous" })).toBeTruthy()
  })
})
