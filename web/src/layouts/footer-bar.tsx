/**
 * The bar under a table: what you are looking at, and how to get to the rest of it.
 *
 * `components/page-controls.tsx` moves in here rather than being reimplemented, and the reason is
 * written in that file: "Next" is driven by `next_offset` rather than by arithmetic on `total`,
 * because the transport returns null on the last page precisely so a client cannot walk past the
 * end — and `/api/overview`'s total is *bounded* at 1,000, so arithmetic on it would invent a page
 * that does not exist. Anything here that recomputed paging would be a second answer to a question
 * the payload already answers.
 *
 * **The record count is the footer's own job and is deliberately not a "page size" control.** The
 * brief for this component named three things: pagination, page size, record count. Two of them
 * exist. A page-size selector needs `limit` to be a value an operator sets and it is
 * `DEFAULT_LIMIT` everywhere today, with `_MAX_LIMIT` enforced in the transport — so a control here
 * would be a select with one option, which is furniture claiming a choice nobody has. It arrives
 * with the first screen that has a reason to page at a different size, and the slot is `left`.
 *
 * `left` is where a caller puts what the count is counted over, and every long table in this console
 * has something to say there — the vendor findings table's filtered-total caveat, the binding
 * surface's shared-directory note. Those are the sentences `.claude/rules/console-surface.md`
 * protects, so this component gives them a place rather than leaving a caller to invent one.
 *
 * **The pager is optional, and that is what lets a complete listing have a footer at all.** Four of
 * the routes this console reads — `/api/repositories`, `/api/detectors`, `/api/overview`, and
 * `/api/runs` whenever the set is under the cardinality threshold — return their whole answer and
 * take no offset. `runs-table.tsx` had already reasoned that page controls over a set that fits on
 * one page are a choice nobody has, and paid for it by rendering no footer on that branch; the two
 * longest screens in the console then had their record counts in an `h2` and nothing under the rows
 * they counted. So a caller either supplies the whole paging group or none of it, held by the type
 * rather than by care: half a group is a pager that cannot say where it is.
 */

import type { ReactNode } from "react"

import { PageControls } from "@/components/page-controls"

interface Paging {
  offset: number
  limit: number
  shown: number
  total: number
  /** The scope's count with no filter applied. Decision 60: with a filter active the count says
      what it excluded, because a bare range under a narrowed table reads as the whole set. */
  unfilteredTotal?: number
  nextOffset: number | null
  busy: boolean
  onOffsetChange: (offset: number) => void
}

/** A complete listing: every row it holds is already on screen, so there is no page to move to. */
type Unpaged = { [K in keyof Paging]?: never }

type FooterBarProps = {
  /** What the count is counted over, when that is not simply "everything". */
  left?: ReactNode
} & (Paging | Unpaged)

function isPaged(props: FooterBarProps): props is { left?: ReactNode } & Paging {
  return props.onOffsetChange !== undefined
}

export function FooterBar(props: FooterBarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-section border-t border-line pt-section">
      <div className="flex min-w-0 flex-1 flex-col gap-field">{props.left}</div>
      {isPaged(props) && (
        <div className="shrink-0">
          <PageControls
            offset={props.offset}
            limit={props.limit}
            shown={props.shown}
            total={props.total}
            unfilteredTotal={props.unfilteredTotal}
            nextOffset={props.nextOffset}
            busy={props.busy}
            onOffsetChange={props.onOffsetChange}
          />
        </div>
      )}
    </div>
  )
}
