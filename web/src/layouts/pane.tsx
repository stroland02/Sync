/**
 * The two-element mechanic every locked screen composes from.
 *
 * A pane that fills its share of a locked viewport and scrolls its own body is four classes in a
 * chain, and every one of them is load-bearing: `min-h-0` on each flex ancestor (without it a
 * flex child refuses to shrink below its content and the whole column grows instead of
 * scrolling), `flex-1` to claim the share, `overflow-hidden` on the pane so nothing escapes it,
 * and exactly one `overflow-auto` inside. Four specs each wrote that chain out separately, which
 * is why it is a component rather than a paragraph: a paragraph is enforced by whoever remembers
 * it, and the failure mode is silent — the page simply grows a second scrollbar nobody meant.
 *
 * **Exactly one `PaneScroll` per `Pane`.** Two scroll regions in one pane is two scrollbars over
 * one body, and a reader cannot tell which one they are holding.
 *
 * This file is the mechanic with no chrome. `components/pane.tsx` is the banded surface built on
 * it — border, header strip, label — for the panes that need to look like panels rather than
 * regions.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** A region that takes its share of a locked column and refuses to grow past it. */
export function Pane({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cn("flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden", className)}>
      {children}
    </div>
  )
}

/** The one scrolling body inside a `Pane`. */
export function PaneScroll({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cn("min-h-0 flex-1 overflow-auto", className)}>{children}</div>
}
