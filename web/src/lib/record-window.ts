/**
 * What a status band says about the page it is describing, and the set that page came from.
 *
 * Moved out of `components/table-toolbar.tsx` when the skeleton landed: the three helpers below
 * are formatters every screen's status band needs, and that file was dead product code with no
 * importer outside its own test.
 */

import { describeBoundedTotal } from "@/features/fleet/cardinality"

/**
 * How many records a query found.
 *
 * `boundReached` is required rather than optional on purpose: a caller that renders `count`
 * without deciding whether the count finished is claiming an exactness it has not checked, which
 * is the defect `total_findings_bound_reached` was added to the payload to catch. A `count` of
 * `null` is the count nothing answered — distinct from a counted zero, and never coerced to one.
 */
export interface RecordTotal {
  count: number | null
  boundReached: boolean
}

/**
 * The window sentence, or `null` when nothing counted.
 *
 * Returning `null` rather than a glyph keeps this a formatter: `<Absent>` in `components/status`
 * is the one place absence becomes ink, exactly as `lib/format`'s helpers are arranged.
 */
export function describeRecordWindow(
  offset: number,
  shown: number,
  total: RecordTotal,
  singular: string,
  plural: string
): string | null {
  if (total.count === null) return null

  const figure = describeBoundedTotal(total.count, total.boundReached)

  if (total.count === 0 && !total.boundReached) return `No ${plural}.`

  // A page that came back empty over a non-empty set: the set moved between the count and the
  // fetch. Rendering the arithmetic range here would print "201-200", which reads as a bug in the
  // table rather than as a set that changed.
  if (shown === 0) return `No ${plural} on this page, of ${figure} in the set.`

  // "The whole set" is only ever claimed against a count that finished. A bounded total has no
  // last page to be on.
  if (!total.boundReached && offset === 0 && shown === total.count) {
    return `This is all ${figure} ${total.count === 1 ? singular : plural}.`
  }

  return `Showing ${offset + 1}–${offset + shown} of ${figure} ${plural}.`
}

/**
 * What the `+` means, in words. The glyph is never the only channel, the same way a status colour
 * never ships without an icon and a word.
 */
export function boundedRecordCaveat(bound: number, plural: string): string {
  return (
    `This total stopped counting at ${bound.toLocaleString()}: there are at least that many ` +
    `${plural}, and this figure does not say how many more.`
  )
}
