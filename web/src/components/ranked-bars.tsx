/**
 * A ranked horizontal bar chart over a closed set — the shape six of the catalogue's dashboards
 * need, written once.
 *
 * Call sites per integration, findings per detector, changes per vendor: all the same question —
 * *which members of this set carry the most, and by how much* — and all pure counts. That is
 * exactly what a chart is permitted to render (`2026-08-18-dashboards.md`), and a ranked bar is
 * the form that answers it without a second axis to misread.
 *
 * **SVG rather than the chart library, and the reason is narrow.** ECharts owns every dashboard
 * with an axis, a legend, a tooltip or a time dimension, and this component does not compete
 * with it — a bar row here is a labelled rectangle whose width is a ratio, and pulling a chart
 * engine in to draw one would cost a canvas, a resize observer and a theme bridge for geometry
 * that is three numbers. Anything that grows an axis belongs in ECharts.
 *
 * **The scale is the maximum, and it is stated.** A bar's width is its share of the largest
 * member, not of the total — those are different claims, and a reader who assumes the wrong one
 * misreads every row. The caption says which.
 *
 * **Colour carries identity where the set is integrations, and nothing otherwise.** The scale is
 * `lib/palette.ts`'s, so a vendor is the same colour here as on the map and in every chart. A
 * set that is not integrations takes ink: a bar's length is the measurement, and a hue over it
 * would be a second encoding of the same number.
 */

import { seriesScale } from "@/lib/palette"
import { cn } from "@/lib/utils"

export interface RankedRow {
  readonly key: string
  readonly value: number
}

export function RankedBars({
  label,
  caption,
  rows,
  unit,
  colourByKey = true,
  max: cap = 10,
  className,
}: {
  label: string
  /** What the bars are counted over, and what their width is a share of. */
  caption: string
  /** Already sorted by the caller — the caller knows whether ties break by name or by id. */
  rows: readonly RankedRow[]
  unit: string
  /** `false` for a set that is not integrations: length is the measurement, hue would repeat it. */
  colourByKey?: boolean
  /** How many rows are drawn before the rest are summarised rather than silently dropped. */
  max?: number
  className?: string
}) {
  const ink = seriesScale(rows.map((row) => row.key))
  const shown = rows.slice(0, cap)
  const rest = rows.slice(cap)
  const largest = Math.max(...rows.map((row) => row.value), 1)
  const restTotal = rest.reduce((sum, row) => sum + row.value, 0)

  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-section rounded-surface border border-line bg-surface p-section",
        className
      )}
    >
      <div className="flex flex-col gap-field">
        <h3 className="text-section">{label}</h3>
        <p className="max-w-prose text-meta text-ink-muted">{caption}</p>
      </div>

      <div className="flex min-w-0 flex-col gap-row">
        {shown.map((row) => (
          <div key={row.key} className="flex min-w-0 flex-col gap-field">
            <div className="flex min-w-0 items-baseline justify-between gap-row">
              <span className="min-w-0 truncate font-mono text-meta text-ink">{row.key}</span>
              <span className="shrink-0 font-mono text-meta tabular-nums text-ink-muted">
                {row.value.toLocaleString()}
              </span>
            </div>
            {/* `role="img"` with a name, because a bar whose only channel is width is
                unreadable to a screen reader without one. */}
            <div
              className="h-2 w-full overflow-hidden rounded-control bg-surface-muted"
              role="img"
              aria-label={`${row.key}: ${row.value} ${unit}`}
            >
              <div
                className={cn("h-full rounded-control", !colourByKey && "bg-line-strong")}
                style={{
                  width: `${Math.max((row.value / largest) * 100, 1.5)}%`,
                  backgroundColor: colourByKey ? ink(row.key) : undefined,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {rest.length > 0 && (
        <p className="text-meta text-ink-muted">
          {rest.length} further {rest.length === 1 ? "row" : "rows"} not drawn, holding{" "}
          {restTotal.toLocaleString()} {unit} between them — summarised rather than dropped.
        </p>
      )}
    </div>
  )
}
