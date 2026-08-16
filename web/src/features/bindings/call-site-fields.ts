/**
 * How a call site's list-valued fields become one cell of text.
 *
 * Its own module because both renderings of a call site need it — the table's cell and the
 * drawer's card — and `CLAUDE.md`'s rule is to factor at the second use rather than the third,
 * where the two copies have already drifted. `lib/format.ts` would be the obvious home and is the
 * data seam this port does not open.
 *
 * `null` rather than `""` for an empty list, so `<Formatted>` draws the absence marker. An empty
 * cell says nothing and a column that failed to render also says nothing; the marker is what tells
 * a reader the index looked and found none.
 */

/** A string list joined for one cell, or null when the site recorded none. */
export function joinOrAbsent(values: readonly string[]): string | null {
  return values.length === 0 ? null : values.join(", ")
}
