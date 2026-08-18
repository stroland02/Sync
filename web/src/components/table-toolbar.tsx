/**
 * The chrome around a table that is hundreds of rows long: a filter above it, and a footer that
 * says how many records there are.
 *
 * **The footer is the honest part, and it is the reason this file exists.** A table showing
 * fifty rows says nothing about whether that is the whole set, the first page of four thousand,
 * or everything a count that gave up early managed to see. Three answers have to stay apart and
 * every one of them has been collapsed onto another in this console before:
 *
 * - a **confirmed zero** — the query ran and counted nothing. A number, or words.
 * - a **bounded total** — the count stopped at a ceiling, so the figure is a floor. The `+`
 *   convention, never a bare number.
 * - an **unanswered count** — nothing computed a total. The absence marker, never `0`.
 *
 * The `+` convention and its vocabulary come from `features/fleet/cardinality.tsx`, which is
 * imported rather than restated. `components/provenance.tsx` mirrored the two-token ternary
 * instead, on the grounds that a shared component should not depend on a feature; that reading
 * was right about the dependency and wrong about the cost, and this would have been the third
 * copy of one sentence's worth of vocabulary. `CLAUDE.md`'s *a fact written twice will disagree
 * with itself* and *factor at the second use* both bite here, and the module being imported has
 * no dependencies of its own. **The right long-term home is `lib/format.ts`** — that file is not
 * this lane's to edit, and the move is reported as a blocker rather than done quietly.
 *
 * No motion anywhere here, for the reason `page-controls.tsx` measured: a page change unmounts
 * the subtree, so there is nothing to animate, and paging is frequent enough that a transition
 * would be a delay paid on every click with no information behind it.
 */

import type { ReactNode } from "react"

import { PrefixFilter } from "@/components/filters"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import { describeBoundedTotal } from "@/features/fleet/cardinality"

/**
 * How many records a table's query found.
 *
 * `boundReached` is required rather than optional on purpose: a caller that renders `count`
 * without deciding whether the count finished is claiming an exactness it has not checked,
 * which is the defect `total_findings_bound_reached` was added to the payload to catch. A
 * `count` of `null` is the count nothing answered — distinct from a counted zero, and it must
 * never be coerced to one.
 */
export interface RecordTotal {
  count: number | null
  boundReached: boolean
}

/**
 * What the footer says about the page and the set it came from, or `null` when nothing counted.
 *
 * Returning `null` rather than a glyph keeps this a formatter: `<Absent>` in
 * `components/status` is the one place absence becomes ink, exactly as `lib/format`'s helpers
 * are arranged.
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
  // fetch. Rendering the arithmetic range here would print "201-200", which reads as a bug in
  // the table rather than as a set that changed.
  if (shown === 0) return `No ${plural} on this page, of ${figure} in the set.`

  // "The whole set" is only ever claimed against a count that finished. A bounded total has no
  // last page to be on.
  if (!total.boundReached && offset === 0 && shown === total.count) {
    return `This is all ${figure} ${total.count === 1 ? singular : plural}.`
  }

  return `Showing ${offset + 1}–${offset + shown} of ${figure} ${plural}.`
}

/**
 * What the `+` means, in words. The glyph is never the only channel, the same way a status
 * colour never ships without an icon and a word.
 */
export function boundedRecordCaveat(bound: number, plural: string): string {
  return (
    `This total stopped counting at ${bound.toLocaleString()}: there are at least that many ` +
    `${plural}, and this figure does not say how many more.`
  )
}

/**
 * The bar above a table: the filter that narrows it, and whatever actions the screen owns.
 *
 * The filter is `PrefixFilter` rather than a second input, so there is one answer in this
 * console to "when does a filter apply" — on submit, never on a keystroke, for the reasons
 * `filters.tsx` argues. Narrowing goes to the query; a filter applied to the rows already
 * fetched would report a total drawn from a set it never filtered.
 */
export function TableToolbar({
  filter,
  children,
}: {
  filter?: {
    legend: string
    value: string | null
    onSubmit: (next: string | null) => void
    placeholder: string
    note: string
  }
  children?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-section">
      {filter ? <PrefixFilter {...filter} /> : null}
      {children ? <div className="flex flex-wrap items-center gap-row">{children}</div> : null}
    </div>
  )
}

/**
 * The bar below a table: the record count, and the two controls that move between pages.
 *
 * `Next` is driven by the `nextOffset` the transport returned rather than by arithmetic over
 * the total — the transport returns `null` on the last page precisely so a client cannot walk
 * past the end, and over a bounded or unanswered total there is no arithmetic to do.
 */
export function TableFooterBar({
  offset,
  limit,
  shown,
  total,
  bound,
  singular,
  plural,
  nextOffset,
  busy,
  onOffsetChange,
}: {
  offset: number
  limit: number
  shown: number
  total: RecordTotal
  /** The ceiling the count stopped at, when it stopped. Required for the caveat to be sayable. */
  bound?: number
  singular: string
  plural: string
  nextOffset: number | null
  busy: boolean
  onOffsetChange: (offset: number) => void
}) {
  const statement = describeRecordWindow(offset, shown, total, singular, plural)

  return (
    <div className="flex flex-col gap-row">
      <div className="flex flex-wrap items-center justify-between gap-row text-body">
        <span className="text-ink-muted">
          {statement === null ? (
            <Absent>nothing answered the record count for this table</Absent>
          ) : (
            statement
          )}
        </span>
        <span className="flex items-center gap-row">
          <Button
            variant="outline"
            size="sm"
            disabled={busy || offset === 0}
            onClick={() => onOffsetChange(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || nextOffset === null}
            onClick={() => nextOffset !== null && onOffsetChange(nextOffset)}
          >
            Next
          </Button>
        </span>
      </div>
      {total.boundReached && bound !== undefined ? (
        <p className="max-w-prose text-meta text-muted-foreground">
          {boundedRecordCaveat(bound, plural)}
        </p>
      ) : null}
    </div>
  )
}
