/**
 * The Overview's totals line, and the three claims it is not allowed to make.
 *
 * Scope is `.claude/rules/console-dev-loop.md`'s: classification and derivation, never class
 * names and never snapshots. Adopted from Lane F; what is tested here is mostly what was taken
 * back out, because each removal was a claim the payload cannot support.
 */

import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { TotalsBar } from "@/features/fleet/totals-bar"

afterEach(cleanup)

describe("TotalsBar", () => {
  it("states a count it was given", () => {
    render(<TotalsBar totalCallSites={1234} totalFindings={7} findingsAreFloor={false} />)

    expect(screen.getByText("1,234")).not.toBeNull()
    expect(screen.getByText("7")).not.toBeNull()
  })

  it("renders an unanswered total as absence rather than as nought", () => {
    render(<TotalsBar totalCallSites={null} totalFindings={null} findingsAreFloor={false} />)

    // The file this replaces defaulted both to `0`, so a total nobody had answered yet read as a
    // confident zero. Absence and zero are the distinction the console exists to keep.
    expect(screen.getAllByText("—")).toHaveLength(2)
    expect(screen.queryByText("0")).toBeNull()
  })

  it("says a bounded total is a floor rather than printing it as the population", () => {
    render(<TotalsBar totalCallSites={10} totalFindings={1000} findingsAreFloor />)

    // `OverviewResponse.total_findings_bound_reached`: past the bound the count is a floor, not
    // the population. Printing it plain would overstate what was counted.
    expect(screen.getByText(/at least/i)).not.toBeNull()
  })

  it("offers no time range, because nothing here is windowed", () => {
    render(<TotalsBar totalCallSites={10} totalFindings={2} findingsAreFloor={false} />)

    // The adopted file carried a selector with four ranges and no query behind any of them. It
    // filtered nothing while implying every figure beside it was scoped to a window -- and call
    // sites are the current state of the index, which no window applies to.
    expect(screen.queryByRole("combobox")).toBeNull()
    expect(screen.queryByText(/last 60 minutes|last 24 hours|last 7 days/i)).toBeNull()
  })

  it("claims no run is active, because nothing here can tell that from one that died", () => {
    const { container } = render(
      <TotalsBar totalCallSites={10} totalFindings={2} findingsAreFloor={false} />
    )

    // `CLAUDE.md`: nothing in this data separates a run parked on the customer's CI from one that
    // has died. "Active" is a liveness claim and there is no liveness fact behind it.
    expect(container.textContent).not.toMatch(/active/i)
  })
})
