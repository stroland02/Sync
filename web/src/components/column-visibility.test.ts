/**
 * Column visibility: the four rules that stop a preference becoming a broken screen.
 *
 * Scope is `console-dev-loop.md`'s — derivation and structural invariants, never class names.
 * `readStored` is the derivation with a wrong answer, so it is what these drive.
 */

import { beforeEach, describe, expect, it } from "vitest"

import { readStoredForTest, type ColumnSpec } from "@/components/column-visibility"

const COLUMNS: readonly ColumnSpec[] = [
  { id: "path", label: "File" },
  { id: "rung", label: "Rung", hideable: false },
  { id: "symbol", label: "Symbol" },
  { id: "sdk", label: "SDK version", defaultVisible: false },
]

beforeEach(() => window.localStorage.clear())

describe("stored column choices", () => {
  it("starts from the defaults, with an opt-in column hidden", () => {
    const visible = readStoredForTest("call-sites", COLUMNS)

    expect(visible.has("path")).toBe(true)
    expect(visible.has("sdk")).toBe(false)
  })

  it("keeps a column that may not be hidden, whatever the store says", () => {
    // The rung is not a hideable column anywhere in this console (`console-surface.md`). A stored
    // set written before that rule existed must not defeat it.
    window.localStorage.setItem("sync.columns.call-sites", JSON.stringify(["path"]))

    expect(readStoredForTest("call-sites", COLUMNS).has("rung")).toBe(true)
  })

  it("drops a stored id for a column that no longer exists", () => {
    // A column removed in a later release leaves its id in somebody's storage forever. Reading
    // that back as authoritative resurrects a column that is gone.
    window.localStorage.setItem(
      "sync.columns.call-sites",
      JSON.stringify(["path", "a-column-we-deleted"]),
    )

    const visible = readStoredForTest("call-sites", COLUMNS)

    expect(visible.has("a-column-we-deleted")).toBe(false)
    expect(visible.has("path")).toBe(true)
  })

  it("falls back to the defaults on a corrupt value rather than rendering nothing", () => {
    window.localStorage.setItem("sync.columns.call-sites", "{not json")

    expect(readStoredForTest("call-sites", COLUMNS).has("path")).toBe(true)
  })

  it("remembers per table, so hiding one screen's column does not hide another's", () => {
    window.localStorage.setItem("sync.columns.call-sites", JSON.stringify(["path", "rung"]))

    expect(readStoredForTest("call-sites", COLUMNS).has("symbol")).toBe(false)
    expect(readStoredForTest("findings", COLUMNS).has("symbol")).toBe(true)
  })
})
