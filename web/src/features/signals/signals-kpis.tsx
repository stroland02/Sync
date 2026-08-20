/**
 * Dashboard S1: the Logs → Signals page's opening facts.
 *
 * **Absence apart from zero is the whole job of this strip**, and the payload supports it
 * exactly. `telemetry_attached_at` is null when nothing has ever been attached, which is a
 * different fact from an attached source that reported nothing — the first means Sync was never
 * in a position to see traffic, the second means it looked and saw none. Every tile here reads
 * `<Absent>` in the first case and a figure in the second, and the two are never merged.
 *
 * **These counts are page totals, not observation counts.** `calls`, `shapes` and
 * `error_windows` each arrive as a page envelope whose `total` is the count of *rows* the graph
 * holds — and an `observed_shape` row is a distinct
 * `(vendor, operation, field path, json type, source)` tuple with its own `sample_count`, not one
 * observation. So the shapes tile says *distinct shapes*, never *observations*, because those
 * differ by orders of magnitude on any real traffic.
 *
 * **No error rate.** Error windows over calls observed would be a ratio across two tables with
 * different grains and different retention, and a percentage built that way is the composite this
 * console refuses. The counts sit beside each other.
 */

import type { ObservedTelemetryResponse } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"

export function SignalsKpis({ observed }: { observed: ObservedTelemetryResponse }) {
  const attached = observed.telemetry_attached_at !== null

  /** A figure when a source has been attached, and the reason for nothing when none has. */
  function count(total: number) {
    if (!attached) return <Absent>never attached</Absent>
    return total.toLocaleString()
  }

  return (
    <KpiStrip
      items={[
        {
          label: "Telemetry attached",
          value: attached ? (
            <RelativeTime iso={observed.telemetry_attached_at!} />
          ) : (
            <Absent>no source attached</Absent>
          ),
          note: attached
            ? "since then, traffic Sync saw is recorded here"
            : "so nothing below is a measurement of quiet — Sync was never watching",
          figure: false,
        },
        {
          label: "Calls observed",
          value: count(observed.calls.total),
          note: attached ? "distinct calls recorded" : "no source has ever reported",
          figure: attached,
        },
        {
          label: "Shapes recorded",
          value: count(observed.shapes.total),
          // Rows, not observations: a shape row is a distinct field-path-and-type tuple carrying
          // its own sample count, so these differ by orders of magnitude on real traffic.
          note: attached ? "distinct field shapes, not observations" : "nothing to shape",
          figure: attached,
        },
        {
          label: "Error windows",
          value: count(observed.error_windows.total),
          note: attached ? "intervals with errors recorded" : "nothing was watching to record one",
          figure: attached,
        },
      ]}
    />
  )
}
