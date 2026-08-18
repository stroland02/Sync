/**
 * Where vendor changes were read from — the intake provenance card.
 *
 * The mock (`docs/console-mock/index.html` Section 3) gives this card its composition. It does
 * not give it its claims: three fields it showed — an intake time, a feed name, and a count of
 * operations the adapter names — are not on `AdapterRow` and never were, so each rendered
 * `undefined` and fell through to a hard-coded string that read as fact. What the payload does
 * carry is rendered here instead, and what it does not carry is rendered as absence.
 *
 * `last_change_at` is deliberately not relabelled as an intake time. `AdapterRow` says why:
 * nothing records an intake attempt, only its result, so an adapter polled hourly that has
 * found nothing new for a week reports last week. Calling that "intake" would turn staleness
 * into liveness, which is the distinction this console exists to keep.
 */

import { useAdapters } from "@/api/queries"
import { Formatted } from "@/components/status"
import { formatTimestamp } from "@/lib/format"

export interface VendorSourcesCardProps {
  readonly vendorId: string
  readonly repoId?: string | null
}

export function VendorSourcesCard({ vendorId }: VendorSourcesCardProps) {
  const adaptersQuery = useAdapters()
  const adapter = adaptersQuery.data?.adapters.find((a) => a.vendor_id === vendorId) ?? null

  return (
    <div className="flex flex-col gap-4 rounded-surface border border-border bg-surface p-4">
      <div className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">Where it was read from</h2>
        <p className="text-meta text-muted-foreground">
          The adapter serving {vendorId}, and what the graph holds from it.
        </p>
      </div>

      {adapter === null ? (
        <p className="text-xs text-muted-foreground leading-relaxed">
          No adapter is registered for {vendorId}. Any changes the graph holds for this vendor
          were delivered by an adapter that no longer serves it.
        </p>
      ) : (
        <div className="flex flex-col gap-4 divide-y divide-border">
          <div className="flex flex-col gap-1 pt-3 first:pt-0">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-semibold text-foreground">{adapter.kind} adapter</span>
              <span className="text-xs text-muted-foreground">
                {adapter.last_change_at === null ? (
                  "no change recorded"
                ) : (
                  <>last change {formatTimestamp(adapter.last_change_at)}</>
                )}
              </span>
            </div>
            <div className="font-mono text-xs text-muted-foreground break-all">
              <Formatted value={adapter.source} />
            </div>
            <div className="text-xs text-muted-foreground leading-relaxed">
              Parsed into dated vendor change rows. The vendor&apos;s published wording and
              signatures are preserved verbatim on every change. The time above is when the
              newest of those rows was detected — not when the adapter was last asked, which
              nothing records.
            </div>
          </div>

          <div className="flex flex-col gap-1 pt-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-semibold text-foreground">What it has delivered</span>
              <span className="text-xs text-muted-foreground">
                {adapter.changes === null ? (
                  "never delivered"
                ) : (
                  <>{adapter.changes.toLocaleString()} changes</>
                )}
              </span>
            </div>
            <div className="text-xs text-muted-foreground leading-relaxed">
              {adapter.operations === null
                ? "This adapter has delivered nothing, so the graph holds no operations from it."
                : `Those rows name ${adapter.operations.toLocaleString()} distinct operations.`}
            </div>
          </div>

          <div className="flex flex-col gap-1 pt-3">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-sm font-semibold text-foreground">Recorded sources</span>
            </div>
            <div className="font-mono text-xs text-muted-foreground break-all">
              <Formatted value={adapter.sources === null ? null : adapter.sources.join(" · ")} />
            </div>
            <div className="text-xs text-muted-foreground leading-relaxed">
              The <span className="font-mono">source</span> value every change row from this
              adapter carries, which is how a row is traced back to what produced it.
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
