/**
 * One fact: the label register above the value register.
 *
 * **This is what `.furniture` was defined for.** `index.css` has carried it since the design-system
 * slice — uppercase, `0.025em`, applied to `--text-meta` — and `DESIGN.md` records which of that
 * step's two jobs it covers: a *scanned* label takes it, a *read* value does not. It was used in one
 * place, hand-spelled in `site-nav.tsx`. The report on why the console came out flat names the
 * consequence: the console had `text-meta` but never used it as a distinct register, so a label and
 * the thing it labelled arrived at the same weight and the eye had nothing to sort by.
 *
 * The two registers are the whole component. A label is small, uppercase, letterspaced and muted; a
 * value is large, primary ink, and — when it is a number — on the `--text-figure` step with tabular
 * figures, which is what that step was added for and where it has been rendering on three of nine
 * routes. Nothing here is a chart, a delta, a sparkline or a colour: `DESIGN.md`'s first rule is
 * that nothing on screen may assert what the data does not hold, and a tile that showed a figure
 * going *up* would be claiming a comparison the payload does not carry.
 *
 * **A tile never renders an empty value.** `value` is `ReactNode` and a caller with nothing passes
 * `<Absent>…</Absent>` from `components/status.tsx`, which is the console's one absence marker and
 * says which kind of nothing this is. A dash would collapse "zero", "not measured" and "this view
 * cannot see it" onto one glyph, and distinguishing those is the product's argument.
 */

import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export function FactTile({
  label,
  value,
  note,
  figure = false,
  className,
}: {
  /** Scanned, not read. Rendered through `.furniture`. */
  label: string
  value: ReactNode
  /** One line qualifying the value — what it is counted over, or when it was measured. */
  note?: ReactNode
  /**
   * `true` puts the value on `--text-figure` with tabular figures, which is for a number an
   * operator compares down a column or across a poll. A string — an id, a path, a timestamp — takes
   * the body step instead: 32px of a repository name is not a figure, it is a headline.
   */
  figure?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-field rounded-surface border border-line bg-surface p-section",
        className
      )}
    >
      <span className="furniture text-meta text-ink-muted">{label}</span>
      <span className={cn("min-w-0 break-words", figure ? "text-figure" : "text-body")}>
        {value}
      </span>
      {note !== undefined && <span className="text-meta text-ink-muted">{note}</span>}
    </div>
  )
}
