/**
 * Scope and search on the left, at most one primary action on the right.
 *
 * This is `components/filters.tsx`'s `ControlBar` promoted out of the filter module and given the
 * right-hand slot it never had. That component's own docstring already carried the reason its name
 * is not `FilterBar`: an ordering narrows nothing and a filter does, so the bar is a layout and must
 * not imply that everything inside it does the same job. The same argument extends one step — an
 * action does not narrow anything either.
 *
 * **`action` is one slot, not a list, and the type enforces it.** A control plane with two primary
 * actions has none: the operator reads both, weighs them, and the point of a primary action is that
 * there is nothing to weigh. A second thing to do belongs in the row it acts on or behind a
 * disclosure that names it.
 *
 * No `justify-between` on a single child. A bar holding only scope selectors should leave its right
 * side empty rather than stretch the scope across the full width, which is what a
 * `justify-between` with one child does and what reads as a layout accident.
 */

import type { ReactNode } from "react"

export function ControlBar({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start gap-section">
      {/* `flex-1 min-w-0` so the scope controls take the slack and wrap internally; the action keeps
          its intrinsic width and stays on the right until the whole bar wraps. */}
      <div className="flex min-w-0 flex-1 flex-wrap items-start gap-section">{children}</div>
      {action !== undefined && <div className="shrink-0">{action}</div>}
    </div>
  )
}
