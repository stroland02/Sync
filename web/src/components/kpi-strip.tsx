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
 * **A tile may not restate its own table's footer at the same weight.** `corpus-chart.tsx`
 * records two KPI figures being deleted for exactly that. A tile earns its slot by answering
 * something the rows beneath do not: a scope the page is filtered away from, a distribution the
 * rows do not sum, a date the rows do not carry.
 *
 * **Three or four, and the grid is why.** Four tiles divide a page evenly at every breakpoint
 * this console supports; five leaves a widow on the second row, which is the asymmetry the
 * owner's layout ruling exists to prevent. A page with a fifth fact has a card, not a tile.
 */

import type { ReactNode } from "react"

import { FactTile } from "@/components/fact-tile"
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
  return (
    <div
      className={cn(
        // `auto-rows-fr` is the symmetry: a tile whose note wraps to two lines would otherwise
        // be taller than its neighbours, and a row of tiles at four heights is the defect the
        // owner named across the whole console.
        "grid auto-rows-fr gap-section sm:grid-cols-2",
        items.length === 4 ? "xl:grid-cols-4" : "xl:grid-cols-3",
        className
      )}
    >
      {items.map((item) => (
        <div
          key={item.label}
          className="flex flex-col rounded-surface border border-line bg-surface p-section"
        >
          <FactTile
            label={item.label}
            value={item.value}
            note={item.note}
            figure={item.figure ?? true}
          />
        </div>
      ))}
    </div>
  )
}
