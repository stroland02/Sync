import { describe, expect, it } from "vitest"

import {
  CALL_SITE_COLUMNS,
  nextSortDirection,
  sortCallSites,
  type SortState,
} from "./call-site-columns"

/**
 * A call site reduced to the fields these tests order by. The real payload is wider; ordering
 * reads a handful of fields and nothing here should depend on the rest.
 */
function site(overrides: Record<string, unknown> = {}) {
  return {
    repo_id: "acme/web",
    path: "src/a.ts",
    line: 1,
    symbol: "stripe.charges.create",
    sdk_version: "12.0.0",
    binding_rung: "static",
    loop_depth: 0,
    indexed_at: "2026-08-01T00:00:00Z",
    ...overrides,
  }
}

describe("the columns declare their own type", () => {
  it("gives every column a type label, because a header that only names a field says less", () => {
    for (const column of CALL_SITE_COLUMNS) {
      expect(column.label.length, `${column.key} has no label`).toBeGreaterThan(0)
      expect(column.type.length, `${column.key} has no type label`).toBeGreaterThan(0)
    }
  })

  it("keeps the rung first, which is a decision this console already made", () => {
    expect(CALL_SITE_COLUMNS[0].key).toBe("binding_rung")
  })

  it("names its types from Sync's own vocabulary rather than a database's", () => {
    const types = new Set(CALL_SITE_COLUMNS.map((column) => column.type))
    expect(types.has("provenance")).toBe(true)
    // `uuid`, `jsonb` and `timestamptz` describe somebody else's storage. What a reader of this
    // table needs is what the value *is* here.
    expect(types.has("uuid")).toBe(false)
    expect(types.has("jsonb")).toBe(false)
  })
})

describe("sorting", () => {
  it("orders a numeric column numerically rather than as text", () => {
    const items = [site({ loop_depth: 10 }), site({ loop_depth: 2 }), site({ loop_depth: 1 })]

    const sorted = sortCallSites(items, { key: "loop_depth", direction: "asc" })

    expect(sorted.map((s) => s.loop_depth)).toEqual([1, 2, 10])
  })

  it("orders text case-insensitively, so casing does not split one group in two", () => {
    const items = [site({ symbol: "beta" }), site({ symbol: "Alpha" }), site({ symbol: "gamma" })]

    const sorted = sortCallSites(items, { key: "symbol", direction: "asc" })

    expect(sorted.map((s) => s.symbol)).toEqual(["Alpha", "beta", "gamma"])
  })

  it("reverses on descending", () => {
    const items = [site({ loop_depth: 1 }), site({ loop_depth: 3 }), site({ loop_depth: 2 })]

    const sorted = sortCallSites(items, { key: "loop_depth", direction: "desc" })

    expect(sorted.map((s) => s.loop_depth)).toEqual([3, 2, 1])
  })

  it("sinks absent values to the bottom in BOTH directions", () => {
    // Absence is not a value, so it must not sort as one. Ascending by a column with nulls would
    // otherwise open with a screen of blanks, and descending would close with them -- the reader
    // learns the ordering of the rows that have no data instead of the rows that do. This is the
    // same distinction the console draws everywhere else between absence and zero.
    const items = [site({ sdk_version: "2.0.0" }), site({ sdk_version: null }), site({ sdk_version: "1.0.0" })]

    const ascending = sortCallSites(items, { key: "sdk_version", direction: "asc" })
    const descending = sortCallSites(items, { key: "sdk_version", direction: "desc" })

    expect(ascending.map((s) => s.sdk_version)).toEqual(["1.0.0", "2.0.0", null])
    expect(descending.map((s) => s.sdk_version)).toEqual(["2.0.0", "1.0.0", null])
  })

  it("returns the rows untouched when nothing is sorted", () => {
    // "No sort" is a real state and not a synonym for "sorted by the first column". The order the
    // server sent is itself a decision, and clearing a sort has to give it back.
    const items = [site({ loop_depth: 3 }), site({ loop_depth: 1 })]

    const sorted = sortCallSites(items, null)

    expect(sorted.map((s) => s.loop_depth)).toEqual([3, 1])
  })

  it("does not mutate the array it was handed", () => {
    const items = [site({ loop_depth: 2 }), site({ loop_depth: 1 })]

    sortCallSites(items, { key: "loop_depth", direction: "asc" })

    expect(items.map((s) => s.loop_depth)).toEqual([2, 1])
  })

  it("is stable, so rows equal on the sort key keep the order they arrived in", () => {
    const items = [
      site({ loop_depth: 1, path: "src/first.ts" }),
      site({ loop_depth: 1, path: "src/second.ts" }),
      site({ loop_depth: 0, path: "src/third.ts" }),
    ]

    const sorted = sortCallSites(items, { key: "loop_depth", direction: "asc" })

    expect(sorted.map((s) => s.path)).toEqual(["src/third.ts", "src/first.ts", "src/second.ts"])
  })
})

describe("the sort control cycles through three states", () => {
  it("starts a fresh column ascending", () => {
    expect(nextSortDirection(null, "symbol")).toEqual({ key: "symbol", direction: "asc" })
  })

  it("turns ascending into descending on the same column", () => {
    const current: SortState = { key: "symbol", direction: "asc" }

    expect(nextSortDirection(current, "symbol")).toEqual({ key: "symbol", direction: "desc" })
  })

  it("clears back to no sort on the third press, rather than cycling forever", () => {
    const current: SortState = { key: "symbol", direction: "desc" }

    expect(nextSortDirection(current, "symbol")).toBeNull()
  })

  it("switching column starts that column ascending rather than inheriting a direction", () => {
    const current: SortState = { key: "symbol", direction: "desc" }

    expect(nextSortDirection(current, "loop_depth")).toEqual({ key: "loop_depth", direction: "asc" })
  })
})
