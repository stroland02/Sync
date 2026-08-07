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
 * page: `PageHeader`'s `h1`, then a panel, then whatever a panel's own body headings are —
 * `corpus-summary.tsx`'s three tally headings are `h3` and are contained by their panel, so a
 * panel at `h3` would put a container and its contents on one outline level and leave the document
 * with no `h2` at all. The register is unaffected: a panel name is scanned rather than read, so it
 * takes the furniture treatment whatever element carries it. Screen-reader outline and visual
 * weight are two different decisions and this is the file where they stop being confused.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader } from "@/vendor/supabase/ui/card"

type Metric =
  | { value: ReactNode; unit: string }
  | undefined

export function MetricPanel({
  label,
  metric,
  caption,
  children,
  className,
}: {
  /** Scanned, not read. The panel's name in the furniture register. */
  label: ReactNode
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
}) {
  return (
    <Card className={cn("flex min-w-0 flex-col", className)}>
      <CardHeader>
        <h2 className="furniture text-meta text-ink-muted">{label}</h2>
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
