/**
 * Where vendor changes were read from — the intake provenance card.
 *
 * Extracted directly from the console mock (`docs/console-mock/index.html` Section 3).
 * Pairs beside "What the vendor changed" in the top 2-column grid.
 */

import { useAdapters } from "@/api/queries"
import { formatTimestamp, orAbsent } from "@/lib/format"

export interface VendorSourcesCardProps {
  readonly vendorId: string
  readonly repoId?: string | null
}

export function VendorSourcesCard({ vendorId }: VendorSourcesCardProps) {
  const adaptersQuery = useAdapters()
  const adapter = adaptersQuery.data?.adapters.find((a) => a.vendor_id === vendorId) ?? null

  const intakeTime = adapter?.last_intake_at ? formatTimestamp(adapter.last_intake_at) : "Never"
  const feedName = adapter?.feed ?? `${vendorId} specification / changelog`

  return (
    <div className="flex flex-col gap-4 rounded-surface border border-border bg-surface p-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">Where it was read from</h2>
        <p className="text-meta text-muted-foreground">
          Intake sources and telemetry channels monitored by Sync for {vendorId}.
        </p>
      </div>

      <div className="flex flex-col gap-4 divide-y divide-border">
        {/* Source 1: Specification / Changelog Feed */}
        <div className="flex flex-col gap-1 pt-3 first:pt-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold text-foreground">
              {adapter ? `${adapter.kind} adapter feed` : "Specification feed"}
            </span>
            <span className="text-xs text-muted-foreground">
              {adapter?.last_intake_at ? `intake ${intakeTime}` : "no recorded intake"}
            </span>
          </div>
          <div className="font-mono text-xs text-muted-foreground break-all">{feedName}</div>
          <div className="text-xs text-muted-foreground leading-relaxed">
            Parsed into dated vendor change rows. The vendor&apos;s published wording and signatures
            are preserved verbatim on every change.
          </div>
        </div>

        {/* Source 2: Registered Adapter Module */}
        <div className="flex flex-col gap-1 pt-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold text-foreground">Signal adapter</span>
            <span className="text-xs text-muted-foreground">
              {adapter ? `tier: ${adapter.kind}` : "unregistered"}
            </span>
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            sync.signals.{vendorId}
          </div>
          <div className="text-xs text-muted-foreground leading-relaxed">
            {adapter?.operations_named
              ? `Names ${adapter.operations_named.toLocaleString()} operations in the schema graph.`
              : "Operates as a generic specification adapter."}
          </div>
        </div>

        {/* Source 3: Observed Traffic Channel */}
        <div className="flex flex-col gap-1 pt-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-sm font-semibold text-foreground">Runtime telemetry</span>
            <span className="text-xs text-muted-foreground">observed rung</span>
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            otel · trace-correlation · 7d window
          </div>
          <div className="text-xs text-muted-foreground leading-relaxed">
            Correlation only. Telemetry attributes runtime calls without reading customer source code.
          </div>
        </div>
      </div>
    </div>
  )
}
