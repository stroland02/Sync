/**
 * Which row the URL is asking for, against the rows a page holds.
 *
 * Three of the four answers are easy; the fourth is the one this module exists for and the one a
 * careless implementation collapses. A key the window does not hold is neither *nothing selected*
 * nor *the row is gone*, and folding it onto either tells a reader something the console cannot
 * know. Proven red by collapsing `unresolved` onto `none` and watching the "this window does not
 * hold it" case go silent.
 *
 * The per-view resolution is the second claim. The grouped rows are change units and the flat rows
 * are findings — two id spaces — so a key from one view must not resolve against the other's rows.
 */

import { describe, expect, it } from "vitest"

import type { ChangeUnitRow, RiskRow } from "@/api/types"
import { selectRow } from "@/features/findings/finding-selection"

function finding(id: string): RiskRow {
  return {
    name: "stripe-postcharges-4b1c9e",
    file: "src/billing/charge.ts",
    line: 42,
    symbol: "createCharge",
    operation: "PostCharges",
    vendor: "stripe",
    change_kind: "removed",
    severity: "breaking",
    finding_id: id,
    binding_source: "static",
  }
}

function unit(id: string): ChangeUnitRow {
  return {
    change_unit_id: id,
    vendor_id: "stripe",
    operation_id: "PostCharges",
    change_kind: "request-parameter-removed",
    from_version: "v2320",
    to_version: "v2330",
    severity: "breaking",
    repository_count: 1,
    call_site_count: 1,
    binding_rung: "static",
    finding_count: 1,
    findings: [finding("f-1")],
    finding_ids: ["f-1"],
    repo_ids: ["demo"],
    standing: null,
    last_checkpoint_at: null,
  }
}

const UNITS = [unit("stripe:PostCharges:request-parameter-removed")]
const ROWS = [finding("f-1")]

describe("selectRow", () => {
  it("reads an absent parameter and an empty one as the same closed state", () => {
    // The setter spells "nothing selected" as the parameter's absence, so a hand-edited `?inspect=`
    // is that intention badly spelled rather than a lookup that failed.
    expect(selectRow(null, true, UNITS, ROWS)).toEqual({ kind: "none" })
    expect(selectRow("", true, UNITS, ROWS)).toEqual({ kind: "none" })
    expect(selectRow("", false, UNITS, ROWS)).toEqual({ kind: "none" })
  })

  it("resolves a unit id in the grouped view and a finding id in the flat one", () => {
    expect(selectRow("stripe:PostCharges:request-parameter-removed", true, UNITS, ROWS)).toEqual({
      kind: "unit",
      unit: UNITS[0],
    })
    expect(selectRow("f-1", false, UNITS, ROWS)).toEqual({ kind: "finding", row: ROWS[0] })
  })

  it("refuses a key from the other view rather than landing it on a wrong row", () => {
    // Two id spaces with no rule keeping them apart. Matching a finding id against units would
    // open whichever unit happened to share the string, and nothing would report it.
    expect(selectRow("f-1", true, UNITS, ROWS)).toEqual({ kind: "unresolved", key: "f-1" })
    expect(
      selectRow("stripe:PostCharges:request-parameter-removed", false, UNITS, ROWS),
    ).toEqual({ kind: "unresolved", key: "stripe:PostCharges:request-parameter-removed" })
  })

  it("carries the unheld key back so the drawer can print it", () => {
    // The reader needs to see what was asked for: the row may sit behind a chip, on another page,
    // or nowhere in the graph, and only they can tell which.
    expect(selectRow("nothing-holds-this", true, UNITS, ROWS)).toEqual({
      kind: "unresolved",
      key: "nothing-holds-this",
    })
  })

  it("compares keys whole, so a colon inside an operation id cannot split one", () => {
    // `change_unit_id` is `vendor:operation:kind` joined and an operation identifier may hold a
    // colon. A parser reading the segments back apart resolves one unit's key onto another's on
    // somebody's repository, silently.
    const odd = unit("stripe:v1:charges:create:request-parameter-removed")
    expect(selectRow("stripe:v1:charges:create:request-parameter-removed", true, [odd], ROWS)).toEqual(
      { kind: "unit", unit: odd },
    )
    expect(selectRow("stripe:v1", true, [odd], ROWS)).toEqual({
      kind: "unresolved",
      key: "stripe:v1",
    })
  })

  it("is unresolved against an empty page rather than closed", () => {
    // An empty window has not answered the question the key asks; saying "nothing selected" here
    // would report the reader's own link as never having existed.
    expect(selectRow("f-1", false, [], [])).toEqual({ kind: "unresolved", key: "f-1" })
  })
})
