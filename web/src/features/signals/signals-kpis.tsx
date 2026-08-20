/**
 * The live-signals page's opening facts (owner ruling 2026-08-19: this page is the Observe
 * stage's instrument, so the strip leads with measured traffic rather than table row counts).
 *
 * **Absence apart from zero is still the whole job.** `telemetry_attached_at` is null when
 * nothing has ever been attached — a different fact from an attached source that reported
 * nothing. Every tile reads `<Absent>` in the first case and a figure in the second.
 *
 * **The error tile is a sentence, not a percentage.** A rate never travels without its
 * denominator, and requests with no status leave both sides of the division — the tile's note
 * says how many did.
 */

import type { ObservedTelemetryResponse } from "@/api/types"
import { KpiStrip } from "@/components/kpi-strip"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { rateSentence } from "@/features/telemetry/traffic"

export function SignalsKpis({ observed }: { observed: ObservedTelemetryResponse }) {
  const attached = observed.telemetry_attached_at !== null
  const totals = observed.totals

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
          label: "Requests observed",
          value: attached ? (
            totals.requests.toLocaleString()
          ) : (
            <Absent>never attached</Absent>
          ),
          note: attached
            ? totals.unstatused > 0
              ? `statused requests; ${totals.unstatused.toLocaleString()} more carried no status`
              : "requests that carried a status"
            : "no source has ever reported",
          figure: attached,
        },
        {
          label: "Errored",
          value: attached ? rateSentence(totals.errors, totals.requests) : (
            <Absent>never attached</Absent>
          ),
          note: attached
            ? "4xx and 5xx over statused requests, pooled across operations"
            : "nothing was watching to fail",
          figure: false,
        },
        {
          label: "Operations covered",
          value: attached ? (
            `${totals.operations_observed.toLocaleString()} of ${totals.operations_indexed.toLocaleString()}`
          ) : (
            <Absent>never attached</Absent>
          ),
          note: attached
            ? "indexed operations traffic has named — the rest are unwatched, not idle"
            : "the index binds operations; nothing has watched them",
          figure: false,
        },
      ]}
    />
  )
}
