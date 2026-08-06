/**
 * A facet option counted at zero is a fact, and the fact is "nothing here carries this value" —
 * not "this value does not exist". Suppressing the chip turns a narrowing control into an
 * incomplete map of the column it narrows, and the reader has no way to tell which one they got.
 *
 * This is the invariant the console architecture plan filed under the disclosure header it never
 * built ("a section labelled (0) is a fact and must render rather than be suppressed"). The
 * facet chip is where that rule actually lives in this tree, so it is where the guard goes.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { FacetChips } from "@/components/filters"

afterEach(cleanup)

function renderChips(options: { value: string; count: number }[]) {
  render(
    <FacetChips
      legend="Severity"
      options={options}
      selected={null}
      onSelect={() => {}}
      allLabel="Every severity"
      countScope="Counted over this vendor, before any filter."
    />
  )
}

describe("FacetChips", () => {
  it("renders an option counted at zero rather than dropping it", () => {
    renderChips([
      { value: "breaking", count: 12 },
      { value: "deprecation", count: 0 },
    ])

    const chip = screen.getByRole("button", { name: /deprecation/ })
    expect(chip).toBeTruthy()
    expect(chip.textContent).toContain("0")
  })

  it("offers every option it is given, so the chips are a complete map of the column", () => {
    renderChips([
      { value: "breaking", count: 3 },
      { value: "deprecation", count: 0 },
      { value: "warning", count: 0 },
    ])

    // Three options plus the unfiltered chip. A count of zero must not cost a row here, or the
    // reader cannot tell an empty severity from one this control has never heard of.
    expect(screen.getAllByRole("button")).toHaveLength(4)
  })

  it("carries selection in aria-pressed, not only in a surface step", () => {
    render(
      <FacetChips
        legend="Severity"
        options={[{ value: "breaking", count: 3 }]}
        selected="breaking"
        onSelect={() => {}}
        allLabel="Every severity"
        countScope="Counted over this vendor, before any filter."
      />
    )

    expect(screen.getByRole("button", { name: /breaking/ }).getAttribute("aria-pressed")).toBe(
      "true"
    )
    expect(screen.getByRole("button", { name: "Every severity" }).getAttribute("aria-pressed")).toBe(
      "false"
    )
  })

  it("renders nothing when the column offers no options at all", () => {
    // Distinct from an option at zero: there is no facet here, so there is no control to draw
    // and no claim to make. The two cases must not collapse onto each other.
    const { container } = render(
      <FacetChips
        legend="Severity"
        options={[]}
        selected={null}
        onSelect={() => {}}
        allLabel="Every severity"
        countScope="Counted over this vendor, before any filter."
      />
    )

    expect(container.innerHTML).toBe("")
  })

  it("states what the counts are counted over", () => {
    // The chip counts and the table's own total answer different questions on purpose. The
    // sentence saying so is what stops a reader reading a disagreement as a bug.
    renderChips([{ value: "breaking", count: 3 }])

    expect(screen.getByText(/Counted over this vendor/)).toBeTruthy()
  })
})
