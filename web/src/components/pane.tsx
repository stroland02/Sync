/**
 * A pane as a panel: hairline border, a banded header strip, one scrolling body.
 *
 * The banded header is the reference's own treatment and four rebuild specs each described it
 * separately — a raised strip at row height carrying an uppercase furniture label, an optional
 * leading icon, optional trailing controls, closed by a hairline. The disagreements between those
 * four descriptions are settled here rather than four times: the strip is `row-lg` (40px), it
 * sits on `secondary` over the pane's `card`, and the label is furniture register, never body.
 *
 * `footer` exists because two specs wanted a pinned count or a pagination row under the body, and
 * a footer inside `PaneScroll` would scroll away from the rows it counts.
 *
 * The mechanic is `layouts/pane.tsx`; this adds only chrome. A pane that needs no border — a
 * bare region of a bento grid, a split half — composes `Pane`/`PaneScroll` directly.
 */

import type { ComponentType, ReactNode, SVGProps } from "react"

import { Pane, PaneScroll } from "@/layouts/pane"
import { cn } from "@/lib/utils"

export function PanelPane({
  label,
  icon: Icon,
  actions,
  footer,
  className,
  bodyClassName,
  children,
}: {
  /** Furniture register, uppercase. What this pane holds, not a sentence about it. */
  label: ReactNode
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  /** Controls belonging to this pane, right-aligned in its header strip. */
  actions?: ReactNode
  /** Pinned under the body: a count, a pagination row. Never inside the scroll. */
  footer?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
}) {
  return (
    <Pane className={cn("rounded-surface border border-line bg-card", className)}>
      <header className="flex h-row-lg shrink-0 items-center gap-row border-b border-line bg-secondary px-row">
        {Icon !== undefined && (
          <Icon aria-hidden="true" className="size-4 shrink-0 text-graphics" />
        )}
        {/* `text-section`, not the reference's 12px uppercase furniture. The mock is the lowest
            authority where it disagrees with DESIGN.md, and
            `reports/2026-08-06-why-the-console-came-out-flat.md` measured exactly one 18px heading
            in the whole application with every other h2 at furniture size -- a screen whose only
            headings are one h1 and three column-header-sized strips is that failure repeated. */}
        <h2 className="min-w-0 truncate text-section">{label}</h2>
        {actions !== undefined && <span className="ml-auto flex shrink-0 items-center gap-field">{actions}</span>}
      </header>

      <PaneScroll className={bodyClassName}>{children}</PaneScroll>

      {footer !== undefined && (
        <footer className="flex h-row-lg shrink-0 items-center gap-row border-t border-line px-row text-meta text-ink-muted">
          {footer}
        </footer>
      )}
    </Pane>
  )
}
