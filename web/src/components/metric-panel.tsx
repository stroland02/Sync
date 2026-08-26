/**
 * A panel whose value sits above its own evidence.
 *
 * The third member of the family `fact-tile.tsx` and `fact-list.tsx` already hold. A tile is one
 * fact standing alone; a list is several facts about one subject; a panel is **one figure and the
 * rows, chart or tallies that justify it**, which is the arrangement
 * `.claude/rules/interface-originality.md` names as a convention of the form rather than an
 * invention. Built on the vendored `Card`, so the plane, the radius, the hairline and the rule
 * under the header are Supabase's and not a second set of values.
 *
 * **`value` is optional, and the reason is a rule rather than a convenience.** M7-W163 removed the
 * open-findings total from the vendor panel because the fact rail at the top of the same screen
 * already carried it: two renderings of one count is a fact written twice, and the one that stays
 * is the one an operator reaches first. A panel whose headline count is already a tile therefore
 * passes no `value` and keeps the count in its title sentence. Making the prop optional is what
 * stops that rule from being something each level has to remember.
 *
 * The figure takes `--text-figure`, not `--text-display`. The display step has exactly one
 * consumer — `layouts/page-header.tsx` — and `test_exactly_one_component_spends_the_display_step`
 * holds it there, because a second focal point on one screen is none.
 *
 * **`unit` is required alongside `value` by the type, and that is the point.** A panel named
 * "Repair record" with a bare `3` under it is a number claiming to be whatever the reader guesses;
 * the same panel reading `3 findings with a repair attempt` cannot be misread. This is the same
 * rule the absence vocabulary follows — a glyph is never the only channel — applied to a figure.
 *
 * **The title is an `h2`, written here rather than taken from the vendored `CardTitle`.** That
 * component renders an `h3` and accepts no `asChild`, and a panel is the level directly under the
 * page: the screen's own `h1`, then a panel, then whatever a panel's own body headings are —
 * `precedent-summary.tsx`'s three tally headings are `h3` and are contained by their panel, so a
 * panel at `h3` would put a container and its contents on one outline level and leave the document
 * with no `h2` at all. Screen-reader outline and visual weight are two different decisions and this
 * is the file where they stop being confused.
 *
 * **The title takes `--text-section`, and until M7-W188 it took the furniture register.** The
 * argument for furniture was that a panel name is scanned rather than read. It is — but so is a
 * table column header, and the two rendered at the same 12px uppercase step, inside the panel and
 * on its header, with nothing between them saying which contained which. A panel heads a region a
 * reader enters; a column header names the values under it. `DESIGN.md`'s *Type* section carries
 * that boundary and `tests/test_console_design_tokens.py` holds this heading to the section side
 * of it. The display step stays the screen's own: this is the step between the two, not a
 * second focal point.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

type Metric =
  | { value: ReactNode; unit: string }
  | undefined

export function MetricPanel({
  label,
  hint,
  metric,
  caption,
  children,
  className,
  frame = "plain",
}: {
  /** The section's name, at `--text-section`. It heads everything below it in this panel. */
  label: ReactNode
  /**
   * Explanation on demand, rendered as an ⓘ beside the label. For prose about how the panel
   * works — never for a protected honesty sentence, a count's scope, or an absence-versus-zero
   * distinction, which stay in `caption` or in the panel body where they cannot be missed.
   */
  hint?: ReactNode
  /**
   * The panel's own figure and what it counts. Omitted when the fact rail already carries this
   * count — see above. `value` is never bare `null`: a panel with nothing to show renders
   * `<Absent>` and says which nothing it is.
   */
  metric?: Metric
  /** What the figure means, what it is counted over, and what it cannot tell you. */
  caption?: ReactNode
  /** The evidence: a table, a chart, a set of tallies. */
  children: ReactNode
  className?: string
  /**
   * `"board"` for a panel sitting beside another panel at the same depth — the hairline ring plus
   * a tinted header strip over a bottom rule, which is what tells two adjacent cards apart when
   * the surface step alone cannot. `"plain"` is every panel that owns its own row.
   */
  frame?: "plain" | "board"
}) {
  const board = frame === "board"
  return (
    <Card
      variant={board ? "grouping" : "plain"}
      className={cn("flex h-full min-w-0 flex-col", board && "pt-0", className)}
    >
      <CardHeader
        className={cn(
          board && "rounded-t-surface border-b bg-surface-subtle pt-(--card-spacing)"
        )}
      >
        <div className="flex items-center gap-row">
          <h2 className="text-section">{label}</h2>
          {hint}
        </div>
        {metric !== undefined && (
          <p className="flex flex-wrap items-baseline gap-row">
            <span className="text-figure text-foreground">{metric.value}</span>
            <span className="text-body text-muted-foreground">{metric.unit}</span>
          </p>
        )}
        {caption !== undefined && (
          <div className="flex flex-col gap-field text-body text-muted-foreground">{caption}</div>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-section">{children}</CardContent>
    </Card>
  )
}
