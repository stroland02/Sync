/**
 * The quality axes as a ledger: one row per axis, its value, its sample count, and the denominator
 * it would be computed over.
 *
 * **This is the product's argument in its most literal form, and the rebuild of 2026-08-26 made it
 * denser rather than louder.** It was a two-column grid of five sub-panels, each drawing a card to
 * say "not measured yet" — five borders and five headings for five words. A ledger says the same
 * five things in five rows and puts the denominator in a column beside them, which is what a reader
 * checking a ratio actually needs.
 *
 * **An unmeasured axis is not a failing axis and this never renders it as one** — no red, no
 * warning, no "incomplete" badge. It is a measurement nobody has been able to take, which is a fact
 * about how much Sync has run rather than about how well it works.
 *
 * **No aggregate over the axes, and this is where one would be most tempting.** Five ratios with a
 * shared subject is exactly the shape that invites a "corpus health score", and the payload even
 * offers `axes_measured_count` to build one from. A scalar averaging a merge rate, a routing
 * accuracy and a token cost would collapse three incommensurable things, and averaging *measured
 * and unmeasured* would put "we could not check" on the same axis as "we checked and it passed".
 * The counts are reported as counts.
 *
 * **A ratio is rendered with its denominator, always.** `denominator_description` is a column
 * rather than a tooltip: a merge rate whose denominator a reader cannot see is a number they cannot
 * check.
 */

import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { Absent } from "@/components/status"
import { TableEmptyState } from "@/components/table-empty"

export interface Axis {
  name: string
  display_name: string
  status: "measured" | "unmeasured"
  has_samples: boolean
  sample_count: number
  provenance: string
  value: number | Record<string, number | null> | null
  groups?: Record<string, { value: number | null; n: number; has_samples: boolean }>
  unit: string
  denominator_description: string
}

/** A ratio as a percentage, a duration as seconds, a token count as itself. */
export function formatValue(value: number, unit: string): string {
  if (unit === "ratio") return `${Math.round(value * 100)}%`
  if (unit === "milliseconds") return `${(value / 1000).toFixed(1)}s`
  return value.toLocaleString()
}

function AxisValue({ axis }: { axis: Axis }) {
  if (axis.status === "unmeasured") {
    // Never "failing", never "0%". An axis with no samples is a measurement nobody could take.
    return <Absent>not measured yet</Absent>
  }

  const groups = Object.entries(axis.groups ?? {})
  if (groups.length > 0) {
    return (
      <span className="flex flex-col gap-field">
        {groups.map(([group, entry]) => (
          <span key={group} className="flex items-baseline gap-row">
            <span className="min-w-0 truncate font-mono text-meta text-ink">{group}</span>
            <span className="shrink-0 font-mono tabular-nums text-meta text-ink-muted">
              {entry.has_samples && entry.value !== null ? (
                <>
                  {formatValue(entry.value, axis.unit)} over {entry.n.toLocaleString()}
                </>
              ) : (
                <Absent>no sample</Absent>
              )}
            </span>
          </span>
        ))}
      </span>
    )
  }

  return (
    <span className="font-mono tabular-nums text-ink">
      {typeof axis.value === "number" ? formatValue(axis.value, axis.unit) : <Absent />}
    </span>
  )
}

export function AxisLedger({ axes }: { axes: readonly Axis[] }) {
  return (
    <TableFrame fill className="rounded-none border-0">
      <Table>
        <TableHeader sticky>
          <TableRow>
            <TableHead>Axis</TableHead>
            <TableHead>Value</TableHead>
            <TableHead>Samples</TableHead>
            <TableHead>Measured over</TableHead>
            <TableHead>Provenance</TableHead>
          </TableRow>
        </TableHeader>
        {axes.length === 0 ? (
          <TableEmptyState
            columns={5}
            headline="The corpus declares no quality axis."
            detail="The route answered and named none. This is the aggregate returning an empty list rather than five axes at nought — a deployment with axes to report would list them here even with no sample behind any of them."
          />
        ) : (
          <TableBody>
            {axes.map((axis) => (
              <TableRow key={axis.name}>
                <TableCell className="text-ink">{axis.display_name}</TableCell>
                <TableCell>
                  <AxisValue axis={axis} />
                </TableCell>
                <TableCell className="font-mono tabular-nums">
                  {axis.sample_count.toLocaleString()}
                </TableCell>
                <TableCell className="text-ink-muted">{axis.denominator_description}</TableCell>
                <TableCell className="font-mono">
                  {/* The payload writes "unmeasured" here when nothing was sampled. Rendering that
                      word as a provenance would name a class of evidence that was never found. */}
                  {axis.has_samples ? axis.provenance : <Absent>no sample</Absent>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        )}
      </Table>
    </TableFrame>
  )
}
