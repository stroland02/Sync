/**
 * A pane as a panel: hairline border, a banded header strip, one scrolling body.
 *
 * The banded header is the reference's own treatment and four rebuild specs each described it
 * separately — a raised strip at row height carrying an uppercase furniture label, an optional
 * leading icon, optional trailing controls, closed by a hairline. The disagreements between those
 * four descriptions are settled here rather than four times: the strip is `row-lg` (40px), it
 * sits on `secondary` over the pane's `card`, and the label is furniture register, never body.
 *
 * `h-[var(--row-lg)]` rather than `h-row-lg`, and the difference is not style: `--row-lg` is a bare
 * custom property, not a `--spacing-*` one, so Tailwind generates no `h-row-lg` utility and the
 * class was inert. Measured 2026-08-26 in Chrome at 1920×1080: the header rendered at 29px and the
 * footer at 17px, both content height. `data-table.tsx` already spells the token this way.
 *
 * `footer` exists because two specs wanted a pinned count or a pagination row under the body, and
 * a footer inside `PaneScroll` would scroll away from the rows it counts.
 *
 * `scroll={false}` exists for one case and it is a correctness fix rather than a preference: a
 * table's scroll has to belong to the vendored `data-slot=table-container`, because that element is
 * `overflow-auto` and therefore *is* the containing block for a `position: sticky` header inside
 * it. Wrapping it in a second scroller leaves the head sticking to a box that never scrolls, so the
 * header simply rides away with the rows. `TableFrame fill` moves that scroll onto the container,
 * and this prop lets a pane hand it over — still exactly one scrolling region in the pane.
 *
 * The mechanic is `layouts/pane.tsx`; this adds only chrome. A pane that needs no border — a
 * bare region of a bento grid, a split half — composes `Pane`/`PaneScroll` directly.
 */

import type { ComponentType, ReactNode, SVGProps } from "react"

import { Pane, PaneScroll } from "@/layouts/pane"
import { cn } from "@/lib/utils"

export function PanelPane({
  label,
  hint,
  icon: Icon,
  actions,
  footer,
  className,
  bodyClassName,
  footerClassName,
  scroll = true,
  children,
}: {
  /** Furniture register, uppercase. What this pane holds, not a sentence about it. */
  label: ReactNode
  /** A disclosure explaining the pane's own claim, beside its name. */
  hint?: ReactNode
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  /** Controls belonging to this pane, right-aligned in its header strip. */
  actions?: ReactNode
  /** Pinned under the body: a count, a pagination row. Never inside the scroll. */
  footer?: ReactNode
  className?: string
  bodyClassName?: string
  /**
   * For a foot that holds a control rather than a count. The default row is one `row-lg` line;
   * the finding detail pins an action there, which is two lines and would overflow it.
   */
  footerClassName?: string
  /**
   * Whether the pane owns its body's scroll. `false` hands it to the child — the one caller is a
   * table, whose sticky head needs the scroll on the table container itself.
   */
  scroll?: boolean
  children: ReactNode
}) {
  return (
    <Pane className={cn("rounded-surface border border-line bg-card", className)}>
      <header className="flex h-[var(--row-lg)] shrink-0 items-center gap-row border-b border-line bg-secondary px-row">
        {Icon !== undefined && (
          <Icon aria-hidden="true" className="size-4 shrink-0 text-graphics" />
        )}
        {/* `text-section`, not the reference's 12px uppercase furniture. The mock is the lowest
            authority where it disagrees with DESIGN.md, and
            `reports/2026-08-06-why-the-console-came-out-flat.md` measured exactly one 18px heading
            in the whole application with every other h2 at furniture size -- a screen whose only
            headings are one h1 and three column-header-sized strips is that failure repeated. */}
        <h2 className="min-w-0 truncate text-section">{label}</h2>
        {/* The ⓘ sits with the label rather than in `actions`: it explains the pane's own claim,
            and a disclosure pushed to the right edge reads as a control over the pane's contents
            instead. `actions` keeps the right edge for things that act. */}
        {hint}
        {actions !== undefined && <span className="ml-auto flex shrink-0 items-center gap-field">{actions}</span>}
      </header>

      {scroll ? (
        <PaneScroll className={bodyClassName}>{children}</PaneScroll>
      ) : (
        <div className={cn("flex min-h-0 min-w-0 flex-1 flex-col", bodyClassName)}>{children}</div>
      )}

      {footer !== undefined && (
        <footer
          className={cn(
            "flex h-[var(--row-lg)] shrink-0 items-center gap-row border-t border-line px-row text-meta text-ink-muted",
            footerClassName,
          )}
        >
          {footer}
        </footer>
      )}
    </Pane>
  )
}
