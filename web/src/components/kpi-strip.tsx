/**
 * The row of facts a page opens with — owner ruling, 2026-08-19: every page begins the same way.
 *
 * The convention is a control plane's, learnable like a table
 * (`.claude/rules/interface-originality.md`), and it is the one thing a reader gets from every
 * screen without reading: what this page is counting, and how much of it there is. What is ours
 * is what may go in a tile, and the rule is narrower than it looks.
 *
 * **A tile carries one measured number and what it was counted over.** Never a composite, never
 * a delta the payload does not carry, never a rate without its denominator — `FactTile`'s own
 * docstring holds that line and this component inherits it rather than restating it.
 *
 * **A tile may not restate its own table's footer at the same weight.** `precedent-chart.tsx`
 * records two KPI figures being deleted for exactly that. A tile earns its slot by answering
 * something the rows beneath do not: a scope the page is filtered away from, a distribution the
 * rows do not sum, a date the rows do not carry.
 *
 * **Three or four, and the grid is why.** Four tiles divide a page evenly at every breakpoint
 * this console supports; five leaves a widow on the second row, which is the asymmetry the
 * owner's layout ruling exists to prevent. A page with a fifth fact has a card, not a tile.
 */

import type { ReactNode } from "react"
import { createPortal } from "react-dom"

import { FactTile } from "@/components/fact-tile"
import { TopbarStat, useTopbarStatsTarget } from "@/layouts/topbar-stats"
import { cn } from "@/lib/utils"

export interface Kpi {
  readonly label: string
  readonly value: ReactNode
  /** What the figure was counted over, or when it was measured. */
  readonly note?: ReactNode
  /** `false` for a string — an id, a path, a date. `FactTile` carries why. */
  readonly figure?: boolean
}

export function KpiStrip({
  items,
  className,
}: {
  /** Three or four. More than four breaks the grid the layout ruling depends on. */
  items: readonly [Kpi, Kpi, Kpi] | readonly [Kpi, Kpi, Kpi, Kpi]
  className?: string
}) {
  // Inside the chassis the strip lives in the top bar -- owner ruling 2026-08-25, every page.
  // The portal keeps the page's own code unchanged: it passes the same items, and the chrome is
  // where they land. Outside the chassis (a bare test, a screen on its own) the in-page grid
  // below is the fallback, so the facts are never lost to a missing slot. Notes travel as the
  // segment's tooltip; the tile carried them in full, and the bar has one line.
  const target = useTopbarStatsTarget()
  if (target !== null) {
    return createPortal(
      <>
        {items.map((item) => (
          <TopbarStat
            key={item.label}
            label={item.label}
            value={item.value}
            note={typeof item.note === "string" ? item.note : undefined}
          />
        ))}
      </>,
      target,
    )
  }

  return (
    // One surface, hairline-divided, rather than four cards with four borders and four gaps.
    // The owner's direction of 2026-08-19: the strip is the page's instrument panel and should
    // read as one instrument. `divide-x` supplies the separation the gaps used to, at a fraction
    // of the height, and `auto-rows-fr` still holds every cell to one height so a note that wraps
    // cannot make its neighbour shorter.
    <div
      className={cn(
        "grid auto-rows-fr overflow-hidden rounded-surface border border-line bg-surface",
        "divide-y divide-line sm:grid-cols-2 sm:divide-y-0 sm:[&>*:nth-child(n+3)]:border-t",
        "sm:[&>*]:border-line",
        items.length === 4 ? "xl:grid-cols-4" : "xl:grid-cols-3",
        "xl:[&>*:nth-child(n+3)]:border-t-0 xl:divide-x",
        className
      )}
    >
      {items.map((item) => (
        <FactTile
          key={item.label}
          className="px-section py-row"
          label={item.label}
          value={item.value}
          note={item.note}
          figure={item.figure ?? true}
        />
      ))}
    </div>
  )
}
