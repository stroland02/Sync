/**
 * Findings grouped by the change that caused them.
 *
 * M15 Task 7. The claim is arithmetic: **twenty-four findings are thirteen change units**, and a
 * console listing them flat shows a reader twenty-four problems where there are thirteen. What is
 * under test is the pair of figures a reader compares — the unit count and the finding count —
 * because a grouped view whose parts do not add to the whole is a worse answer than no grouping,
 * and it is the kind of wrong that reads as a rounding artefact.
 *
 * **Rewritten 2026-08-26 with the expander.** *keeps a unit's findings closed until they are asked
 * for* and *opens one unit's findings without opening the others* both described a disclosure this
 * table no longer has: a unit opens in the drawer, so the table publishes an id and renders no
 * nested rows at all. Those two are replaced by the pair that holds the new contract, and the two
 * sample-caveat tests moved with the nested table into `findings-inspector.test.tsx` rather than
 * being deleted. *renders a unit whose versions the graph does not hold without inventing them* is
 * rewritten against the folded Change-kind cell, and it is the one that proves the fold did not
 * silently drop the absence marker.
 *
 * Scope is `console-dev-loop.md`'s: derivation and structure. Never class names.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { ChangeUnitRow, RiskRow } from "@/api/types"
import {
  ChangeUnitGroups,
  findingsHeld,
  groupingSummary,
} from "@/features/findings/change-unit-groups"

afterEach(cleanup)

function finding(overrides: Partial<RiskRow> = {}): RiskRow {
  return {
    name: "stripe-postcharges-4b1c9e",
    file: "src/billing/charge.ts",
    line: 42,
    symbol: "createCharge",
    operation: "PostCharges",
    vendor: "stripe",
    change_kind: "request-parameter-removed",
    severity: "breaking",
    finding_id: "f-1",
    binding_source: "static",
    ...overrides,
  }
}

function unit(overrides: Partial<ChangeUnitRow> = {}): ChangeUnitRow {
  const findings = overrides.findings ?? [finding()]
  return {
    change_unit_id: "stripe:PostCharges:request-parameter-removed",
    vendor_id: "stripe",
    operation_id: "PostCharges",
    change_kind: "request-parameter-removed",
    from_version: "v2320",
    to_version: "v2330",
    severity: "breaking",
    repository_count: 1,
    call_site_count: 1,
    binding_rung: "static",
    finding_count: findings.length,
    findings,
    finding_ids: findings.map((row) => row.finding_id),
    repo_ids: ["demo"],
    standing: null,
    last_checkpoint_at: null,
    ...overrides,
  }
}

function renderGroups(
  units: ChangeUnitRow[],
  props: { selectedId?: string | null; onSelect?: (id: string) => void } = {},
) {
  return render(
    <MemoryRouter>
      <ChangeUnitGroups
        units={units}
        selectedId={props.selectedId ?? null}
        onSelect={props.onSelect ?? (() => {})}
      />
    </MemoryRouter>,
  )
}

describe("counting what the grouping holds", () => {
  it("sums the payload's own counts rather than the rows it was sent", () => {
    // The counts are what the payload states. Counting `findings.length` would report the rows
    // this page happens to hold, and a unit's findings are not paginated by anything that would
    // make those two agree in every case.
    const units = [
      unit({ finding_count: 9, findings: [finding()] }),
      unit({ change_unit_id: "b", finding_count: 4, findings: [] }),
    ]

    expect(findingsHeld(units)).toBe(13)
  })

  it("is zero for no units, which is a count and not an absence", () => {
    expect(findingsHeld([])).toBe(0)
  })

  it("reconciles the two figures in one sentence: the units and the findings they hold", () => {
    // Moved off the DOM and onto the derivation when the sentence moved into the pane footer the
    // page pins. The claim is unchanged and it is still the one that matters here.
    const summary = groupingSummary(
      [unit({ finding_count: 9 }), unit({ change_unit_id: "b", finding_count: 4 })],
      2,
    )

    expect(summary).toContain("2 changes")
    expect(summary).toContain("13 open findings")
  })
})

describe("the grouped view", () => {
  it("leads with the change rather than with the finding", () => {
    renderGroups([unit()])

    // The unit is the row; its findings are in the inspector. A reader scanning this is deciding
    // which vendor change to deal with, not which of its call sites to open first.
    expect(screen.getByText(/PostCharges/)).toBeTruthy()
    expect(screen.getByText(/request-parameter-removed/)).toBeTruthy()
  })

  it("says how many findings sit under a unit without opening it", () => {
    renderGroups([
      unit({
        finding_count: 3,
        findings: [finding(), finding({ finding_id: "f-2" }), finding({ finding_id: "f-3" })],
      }),
    ])

    expect(screen.getByText(/3 findings/)).toBeTruthy()
  })

  it("renders no constituent finding inside the row", () => {
    // Replaces "keeps a unit's findings closed until they are asked for". There is no disclosure
    // any more: the nested table lives in the drawer, so the row must hold no call site at all --
    // a row whose height jumps under a reader's pointer is the control this replaced.
    renderGroups([unit()])

    expect(screen.queryByText("src/billing/charge.ts:42")).toBeNull()
    expect(screen.queryByRole("button", { name: /3 findings/ })).toBeNull()
  })

  it("publishes the pressed unit's id to the caller rather than selecting it itself", () => {
    // Replaces "opens one unit's findings without opening the others". Selection lives in the URL
    // now, so a table that selected itself would disagree with the address the moment Back was
    // pressed.
    const onSelect = vi.fn()
    renderGroups(
      [
        unit(),
        unit({ change_unit_id: "b", operation_id: "GetBalance" }),
      ],
      { onSelect },
    )

    fireEvent.click(screen.getAllByRole("button", { name: "Inspect" })[1])

    expect(onSelect).toHaveBeenCalledWith("b")
  })

  it("marks the selected unit and only that one", () => {
    renderGroups([unit(), unit({ change_unit_id: "b", operation_id: "GetBalance" })], {
      selectedId: "b",
    })

    const pressed = screen
      .getAllByRole("button", { name: "Inspect" })
      .filter((control) => control.getAttribute("aria-pressed") === "true")
    expect(pressed).toHaveLength(1)
  })

  it("draws no empty row, because the panel above owns the empty state", () => {
    // Two empty states would render one nothing twice, and only one of them can say which nothing
    // it is -- `TriageEmpty` knows what was checked and this table does not.
    renderGroups([])

    expect(screen.queryByText(/No open finding/)).toBeNull()
    expect(screen.getAllByRole("columnheader").length).toBeGreaterThan(0)
  })

  it("renders a unit whose versions the graph does not hold without inventing them", () => {
    // The Versions column folded under Change kind. This is the test that proves the fold did not
    // quietly drop the absence marker with the column.
    renderGroups([unit({ from_version: null, to_version: null })])

    expect(screen.getByText(/not recorded/)).toBeTruthy()
  })

  it("keeps a recorded version span visible after the fold", () => {
    // Non-vacuous partner to the one above: the pair still renders, so the previous test is about
    // the absence rather than about the cell having disappeared.
    renderGroups([unit()])

    expect(screen.getByText(/v2320/)).toBeTruthy()
  })
})

describe("the Standing column", () => {
  it("tells three answers apart: a disposition, a run in flight, and no run at all", () => {
    // The reference's Agent Status, landed on data we hold. This is the column a fabrication would
    // enter through, so the three have to render as three distinguishable things.
    const { container: recorded } = renderGroups([unit({ standing: "opened" })])
    expect(recorded.textContent).toMatch(/opened/)

    cleanup()
    const { container: flight } = renderGroups([unit({ standing: "in_progress" })])
    expect(flight.textContent).toMatch(/in flight/)
    expect(flight.textContent).not.toMatch(/opened/)

    cleanup()
    const { container: none } = renderGroups([unit({ standing: null })])
    expect(none.textContent).toMatch(/no run recorded/)
    expect(none.textContent).not.toMatch(/in flight/)
  })

  it("renders a missing checkpoint time as its own absence rather than omitting the row", () => {
    renderGroups([unit({ standing: "opened", last_checkpoint_at: null })])

    expect(screen.getByText(/no checkpoint time/)).toBeTruthy()
  })
})
