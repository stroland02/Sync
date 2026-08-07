/**
 * Several facts about one thing: label left, value right, one line each.
 *
 * The other half of `fact-tile.tsx`, and the difference is not styling. A tile is a fact that stands
 * alone and gets a grid cell; a list is a set of facts *about one subject* that a reader scans down
 * without reading — nine of them beside a title is the shape the owner's first direction example is
 * built around, and `references/direction/NOTES.md` records why it reads the way it does: "Facts are
 * a list, not a paragraph. Nine of them, label left, value right, one line each, scannable without
 * reading. We render most of these as prose or as table columns."
 *
 * A `<dl>` because that is what this is, and the semantics are load-bearing rather than tidy: a
 * screen reader announces a term and its description as a pair, which is the whole claim the visual
 * arrangement is making. `Formatted`, `Absent` and the rung components all render inside a `<dd>`
 * unchanged.
 *
 * **The label column is fixed and the value column takes the slack.** A label column that sized to
 * its content would step left and right down the list as the words changed length, and the reason to
 * put labels in a column is that the eye can drop down one edge. `--spacing-frame` is not involved;
 * this is a component, and the width is the widest label the console has ("Response fields read")
 * with room, expressed as a fraction so it holds at any body size.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export interface Fact {
  label: string
  /** Never bare `null`. A caller with nothing renders `<Absent>` and says which nothing it is. */
  value: ReactNode
}

export function FactList({ facts, className }: { facts: Fact[]; className?: string }) {
  return (
    <dl className={cn("flex flex-col", className)}>
      {facts.map((fact) => (
        <div
          key={fact.label}
          // A rule between rows rather than a gap: a list of nine reads as one object when the rows
          // are ruled and as nine objects when they are spaced. `border-b` on every row and none on
          // the last, which is the shape `table.tsx` already uses for the same reason.
          className="flex items-baseline gap-section border-b border-line py-row last:border-b-0"
        >
          <dt className="furniture w-2/5 shrink-0 text-meta text-ink-muted">{fact.label}</dt>
          <dd className="min-w-0 flex-1 text-body break-words">{fact.value}</dd>
        </div>
      ))}
    </dl>
  )
}
