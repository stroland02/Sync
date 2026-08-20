/**
 * Findings grouped by the change that caused them.
 *
 * M15 Task 7. The claim is arithmetic: **twenty-four findings are thirteen change units**, and a
 * console listing them flat shows a reader twenty-four problems where there are thirteen. What is
 * under test is the pair of figures a reader compares â€” the unit count and the finding count â€”
 * because a grouped view whose parts do not add to the whole is a worse answer than no grouping,
 * and it is the kind of wrong that reads as a rounding artefact.
 *
 * Scope is `console-dev-loop.md`'s: derivation and structure. Never class names.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router"
import { afterEach, describe, expect, it } from "vitest"

import type { ChangeUnitRow, RiskRow } from "@/api/types"
import { ChangeUnitGroups, findingsHeld } from "@/features/findings/change-unit-groups"

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

function renderGroups(units: ChangeUnitRow[], total = units.length) {
  return render(
    <MemoryRouter>
      <ChangeUnitGroups repoId="demo" units={units} unitTotal={total} />
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
})

describe("the grouped view", () => {
  it("leads with the change rather than with the finding", () => {
    renderGroups([unit()])

    // The unit is the row; the findings are underneath it. A reader scanning this is deciding
    // which vendor change to deal with, not which of its call sites to open first.
    expect(screen.getByText(/PostCharges/)).toBeTruthy()
    expect(screen.getByText(/request-parameter-removed/)).toBeTruthy()
  })

  it("says how many findings sit under a unit before it is opened", () => {
    renderGroups([unit({ finding_count: 3, findings: [finding(), finding({ finding_id: "f-2" }), finding({ finding_id: "f-3" })] })])

    expect(screen.getByRole("button", { name: /3 findings/ })).toBeTruthy()
  })

  it("keeps a unit's findings closed until they are asked for", () => {
    // Twenty-four rows expanded by default is the flat table with extra steps.
    renderGroups([unit()])

    expect(screen.queryByText("src/billing/charge.ts:42")).toBeNull()
  })

  it("opens one unit's findings without opening the others", () => {
    renderGroups([
      unit({ findings: [finding({ file: "src/a.ts" })] }),
      unit({
        change_unit_id: "b",
        operation_id: "GetBalance",
        findings: [finding({ file: "src/b.ts", finding_id: "f-2" })],
      }),
    ])

    fireEvent.click(screen.getAllByRole("button", { name: /finding/ })[0])

    expect(screen.getByText(/src\/a\.ts/)).toBeTruthy()
    expect(screen.queryByText(/src\/b\.ts/)).toBeNull()
  })

  it("reconciles on screen: the units and the findings they hold", () => {
    renderGroups([unit({ finding_count: 9 }), unit({ change_unit_id: "b", finding_count: 4 })], 2)

    const summary = screen.getByTestId("grouping-summary").textContent
    expect(summary).toContain("2")
    expect(summary).toContain("13")
  })

  it("says which nothing an empty grouping is", () => {
    // Not a bare dash and not a zero with no scope: nothing open is a measured answer, and it
    // is a different fact from a workspace that was never indexed.
    renderGroups([], 0)

    expect(screen.getByText(/No open finding/)).toBeTruthy()
  })

  it("renders a unit whose versions the graph does not hold without inventing them", () => {
    renderGroups([unit({ from_version: null, to_version: null })])

    expect(screen.getByText(/not recorded/)).toBeTruthy()
  })

  it("says the nested rows are a sample when the unit holds more than travelled", () => {
    // The payload caps the array and states the count independently. Silence here would render
    // a truncated list as the whole unit -- the count above disagreeing with the rows beneath
    // it, which is the shape this console refuses.
    renderGroups([unit({ finding_count: 137, findings: [finding(), finding({ finding_id: "f-2" })] })])
    fireEvent.click(screen.getByRole("button", { name: /137 findings/ }))

    expect(screen.getByText(/Showing 2 of 137 findings/)).toBeTruthy()
  })

  it("says nothing about a sample when every finding travelled", () => {
    renderGroups([unit({ finding_count: 2, findings: [finding(), finding({ finding_id: "f-2" })] })])
    fireEvent.click(screen.getByRole("button", { name: /2 findings/ }))

    // Non-vacuous: the disclosure opened and the rows are there.
    expect(screen.getAllByRole("row").length).toBeGreaterThan(1)
    expect(screen.queryByText(/Showing/)).toBeNull()
  })
})
