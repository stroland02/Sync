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
  scale = "linear",
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
  /**
   * `"log"` where the set spans orders of magnitude, on the owner's ruling of 2026-08-19.
   *
   * Measured against this deployment: 8,576 warnings, 108 breaking, 39 deprecation. Linear, the
   * two that matter are one pixel each and read as a rendering fault -- the same illegibility
   * that made the provenance ring look unbuilt. Log makes them comparable.
   *
   * **It is opt-in and it is announced.** A log axis a reader takes for linear is worse than no
   * chart, because every comparison they make is wrong by a factor they cannot see. The caption
   * gains a sentence naming the scale, and the counts are printed beside every bar under either
   * scale, so the exact values never depend on reading a length.
   */
  scale?: "linear" | "log"
  className?: string
}) {
  const ink = seriesScale(rows.map((row) => row.key))
  const shown = rows.slice(0, cap)
  const rest = rows.slice(cap)
  const largest = Math.max(...rows.map((row) => row.value), 1)
  // log1p rather than log: a member at zero is a legitimate measurement in several of these
  // sets, and log(0) is negative infinity. `log1p` maps 0 to 0 and keeps the ordering.
  const project = (value: number) =>
    scale === "log" ? Math.log1p(value) / Math.log1p(largest) : value / largest
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
        <p className="max-w-prose text-meta text-ink-muted">
          {caption}
          {scale === "log" && (
            <>
              {" "}
              <span className="text-ink">
                Bar lengths are on a logarithmic scale
              </span>{" "}
              — this set spans orders of magnitude, and on a linear scale the smaller members
              would be a single pixel. Compare the printed counts, not the lengths.
            </>
          )}
        </p>
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
                  width: `${Math.max(project(row.value) * 100, 1.5)}%`,
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
