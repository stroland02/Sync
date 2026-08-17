/**
 * The console's one two-column detail shape.
 *
 * Five screens spelled this grid by hand and two of them mirrored it; a sixth spelling
 * would eventually disagree with the other five. The two literals here are the two that
 * shipped — a rail width is a decision, and a third width is argued in DESIGN.md first.
 *
 * **This component owns the two-column shape and nothing inside either column.** `rail` and
 * `children` render directly as the grid's own children; how each column stacks internally —
 * its gap, its `min-w-0`, whether it wraps in a `div` at all — stays the caller's, because that
 * was already a real per-page decision (a bare `FactList` needs no wrapper; a column mixing
 * prose and links does) and a shared wrapper here would silently overwrite it.
 */

import type { ReactNode } from "react"

const SHAPE = {
  start: "lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]",
  end: "lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]",
} as const

export function DetailGrid({
  rail,
  railSide = "start",
  header,
  children,
}: {
  rail: ReactNode
  railSide?: keyof typeof SHAPE
  /** Spans both columns — a `PageHeader`, usually. */
  header?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={`grid items-start gap-8 ${SHAPE[railSide]}`}>
      {header !== undefined && <div className="lg:col-span-2">{header}</div>}
      {railSide === "start" ? (
        <>
          {rail}
          {children}
        </>
      ) : (
        <>
          {children}
          {rail}
        </>
      )}
    </section>
  )
}
