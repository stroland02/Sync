/**
 * The call-site table's columns, their types, and how a reader reorders them.
 *
 * The owner's direction for record-heavy screens is a spreadsheet-shaped table — *"our calls and
 * endpoints that have hundreds of different records and IDs and information"*. Two conventions
 * come with that form and neither is anybody's invention: a header states the **type** of what is
 * under it, and a header is the control that **sorts** it.
 *
 * **The type vocabulary is ours.** The reference states storage types — `uuid`, `jsonb`,
 * `timestamptz` — because a table editor's reader is editing a database and that is the fact they
 * need. Nobody reading this screen is. What they need is what the value *is* to Sync, so a rung is
 * `provenance` and a call site's position is a `path`. Taking `uuid` because the reference has one
 * would describe somebody else's product, which `.claude/rules/interface-originality.md` is
 * explicit about.
 *
 * Sorting lives here rather than in the page for the reason `call-site-fields.ts` exists: the
 * comparison is a derivation with real edge cases -- numeric columns that must not order as text,
 * and absence that must not order as a value -- and a derivation with edge cases belongs where a
 * test can reach it without rendering anything.
 */

/** A column of the call-site table, and how to read a value out of a row for ordering. */
export interface CallSiteColumn {
  key: string
  label: string
  /** What the value is, in Sync's vocabulary. Rendered beside the label in a muted register. */
  type: string
  /** Absent when ordering the column would not mean anything to a reader. */
  sortBy?: (row: Record<string, unknown>) => string | number | null | undefined
}

export type SortDirection = "asc" | "desc"

export interface SortState {
  key: string
  direction: SortDirection
}

/**
 * **The rung is first, and that is a decision this console already made** rather than one taken
 * again here: it was eighth of nine and the widest column, and no other table in the console
 * ordered it that way. Everything after it is the order a reader scans -- where the call is, what
 * it calls, then what the index learned about it.
 */
export const CALL_SITE_COLUMNS: readonly CallSiteColumn[] = [
  {
    key: "binding_rung",
    label: "Rung",
    type: "provenance",
    sortBy: (row) => row.binding_rung as string | null,
  },
  {
    key: "repo_id",
    label: "Repository",
    type: "identifier",
    sortBy: (row) => row.repo_id as string | null,
  },
  {
    key: "path",
    label: "Call site",
    type: "path",
    sortBy: (row) => `${row.path as string}:${String(row.line as number).padStart(9, "0")}`,
  },
  { key: "symbol", label: "Symbol", type: "text", sortBy: (row) => row.symbol as string | null },
  {
    key: "sdk_version",
    label: "SDK version",
    type: "version",
    sortBy: (row) => row.sdk_version as string | null,
  },
  // Both list columns are joined into one cell by `joinOrAbsent`. Ordering by the text of a joined
  // list would order by whichever element happens to sort first, which is not a fact about the
  // call site, so neither offers a sort rather than offering a misleading one.
  { key: "argument_keys", label: "Argument keys", type: "list" },
  { key: "response_fields_read", label: "Response fields read", type: "list" },
  {
    key: "loop_depth",
    label: "Loop depth",
    type: "integer",
    sortBy: (row) => row.loop_depth as number | null,
  },
  {
    key: "indexed_at",
    label: "Indexed at",
    type: "timestamp",
    sortBy: (row) => row.indexed_at as string | null,
  },
]

const BY_KEY = new Map(CALL_SITE_COLUMNS.map((column) => [column.key, column]))

/**
 * The next sort state when a reader presses `key`, cycling ascending, descending, none.
 *
 * **Three states rather than two, because "unsorted" is a real one.** The order the server sent is
 * itself a decision, and a two-state toggle takes it away permanently after the first press with
 * no way back short of reloading the screen.
 */
export function nextSortDirection(current: SortState | null, key: string): SortState | null {
  if (!current || current.key !== key) return { key, direction: "asc" }
  if (current.direction === "asc") return { key, direction: "desc" }
  return null
}

function compare(left: string | number | null | undefined, right: string | number | null | undefined): number {
  // Absence sinks in both directions, so it is never reversed into the top of the screen. It is
  // not a value and must not be ordered as one -- the same distinction this console draws between
  // absence and zero everywhere else.
  const leftAbsent = left === null || left === undefined || left === ""
  const rightAbsent = right === null || right === undefined || right === ""
  if (leftAbsent || rightAbsent) return leftAbsent && rightAbsent ? 0 : leftAbsent ? 1 : -1

  if (typeof left === "number" && typeof right === "number") return left - right
  return String(left).localeCompare(String(right), undefined, { sensitivity: "base" })
}

/**
 * `items` reordered by `sort`, or handed back untouched when nothing is sorted.
 *
 * Absence is handled before direction is applied, which is why sinking it works in both
 * directions: reversing the comparison would otherwise lift every blank row to the top.
 */
export function sortCallSites<T extends object>(items: readonly T[], sort: SortState | null): T[] {
  // One cast, here, rather than an index signature on the payload type. `BindingCallSite` is a
  // declared interface and adding `[key: string]: unknown` to it to satisfy this function would
  // switch off every typo check the rest of the console gets from it -- a wide loss to buy a
  // narrow convenience. The accessors above read named fields and are covered by their tests.
  const read = (row: T) => row as unknown as Record<string, unknown>
  if (!sort) return [...items]
  const column = BY_KEY.get(sort.key)
  if (!column?.sortBy) return [...items]

  const decorated = items.map((row, index) => ({ row, index }))
  decorated.sort((a, b) => {
    const ordered = compare(column.sortBy!(read(a.row)), column.sortBy!(read(b.row)))
    if (ordered !== 0) {
      const absent = ordered === 1 || ordered === -1
      const bothPresent = column.sortBy!(read(a.row)) != null && column.sortBy!(read(b.row)) != null
      if (!bothPresent && absent) return ordered
      return sort.direction === "asc" ? ordered : -ordered
    }
    // Stable: rows equal on the key keep the order they arrived in, so a second sort does not
    // silently reshuffle rows the reader was already looking at.
    return a.index - b.index
  })
  return decorated.map((entry) => entry.row)
}
