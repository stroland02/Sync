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
import { Formatted, Status, type StatusTone } from "@/components/status"
import { formatTimestamp } from "@/lib/format"

/** The intake attempt vocabulary's own judgement, on the console's one carve-out for a run outcome. */
const OUTCOME_TONE: Record<string, StatusTone> = {
  success: "good",
  declined: "warning",
  failed: "critical",
}

/** `some_reason_code` read as words, since `sync.signals.intake_attempt`'s vocabulary is snake_case. */
function readReason(reason: string): string {
  return reason.replace(/_/g, " ")
}

export interface VendorSourcesCardProps {
  readonly vendorId: string
  readonly repoId?: string | null
}

export function VendorSourcesCard({ vendorId }: VendorSourcesCardProps) {
  const adaptersQuery = useAdapters()
  const adapter = adaptersQuery.data?.adapters.find((a) => a.vendor_id === vendorId) ?? null

  return (
    <div className="flex h-full flex-col gap-section rounded-surface border border-border bg-surface p-section">
      <div className="flex flex-col gap-field">
        <h2 className="text-emphasis font-semibold tracking-tight text-foreground">Where it was read from</h2>
        <p className="text-meta text-muted-foreground">
          The adapter serving {vendorId}, and what the graph holds from it.
        </p>
      </div>

      {adapter === null ? (
        <p className="text-meta text-muted-foreground leading-relaxed">
          No adapter is registered for {vendorId}. Any changes the graph holds for this vendor
          were delivered by an adapter that no longer serves it.
        </p>
      ) : (
        <div className="flex flex-col gap-section divide-y divide-border">
          <div className="flex flex-col gap-field pt-section first:pt-0">
            <div className="flex items-baseline justify-between gap-row">
              <span className="text-body font-semibold text-foreground">{adapter.kind} adapter</span>
              <span className="text-meta text-muted-foreground">
                {adapter.last_change_at === null ? (
                  "no change recorded"
                ) : (
                  <>last change {formatTimestamp(adapter.last_change_at)}</>
                )}
              </span>
            </div>
            <div className="font-mono text-meta text-muted-foreground break-all">
              <Formatted value={adapter.source} />
            </div>
            <div className="text-meta text-muted-foreground leading-relaxed">
              Parsed into dated vendor change rows. The vendor&apos;s published wording and
              signatures are preserved verbatim on every change. The time above is when the
              newest of those rows was detected — not when the adapter was last asked, which
              nothing records.
            </div>
          </div>

          <div className="flex flex-col gap-field pt-section">
            <div className="flex items-baseline justify-between gap-row">
              <span className="text-body font-semibold text-foreground">What it has delivered</span>
              <span className="text-meta text-muted-foreground">
                {adapter.changes === null ? (
                  "never delivered"
                ) : (
                  <>{adapter.changes.toLocaleString()} changes</>
                )}
              </span>
            </div>
            <div className="text-meta text-muted-foreground leading-relaxed">
              {adapter.operations === null
                ? "This adapter has delivered nothing, so the graph holds no operations from it."
                : `Those rows name ${adapter.operations.toLocaleString()} distinct operations.`}
            </div>
          </div>

          <div className="flex flex-col gap-field pt-section">
            <div className="flex items-baseline justify-between gap-row">
              <span className="text-body font-semibold text-foreground">Recorded sources</span>
            </div>
            <div className="font-mono text-meta text-muted-foreground break-all">
              <Formatted value={adapter.sources === null ? null : adapter.sources.join(" · ")} />
            </div>
            <div className="text-meta text-muted-foreground leading-relaxed">
              The <span className="font-mono">source</span> value every change row from this
              adapter carries, which is how a row is traced back to what produced it.
            </div>
          </div>

          {/* Intake attempts: on `AdapterRow` since the field split from `last_change_at`, and
              unrendered until now — the right column carried three short sections against the
              left's chart and table, and this is the fourth fact the payload already held rather
              than invented filler. `last_attempt_at` is the field `last_change_at`'s own docstring
              points at: a healthy, quiet adapter has a recent attempt and an old change. */}
          <div className="flex flex-col gap-field pt-section">
            <div className="flex items-baseline justify-between gap-row">
              <span className="text-body font-semibold text-foreground">Intake attempts</span>
              {adapter.last_attempt_outcome !== null && (
                <Status
                  tone={OUTCOME_TONE[adapter.last_attempt_outcome] ?? "warning"}
                  label={adapter.last_attempt_outcome}
                />
              )}
            </div>
            {adapter.last_attempt_at === null ? (
              <div className="text-meta text-muted-foreground leading-relaxed">
                No attempt is recorded for this adapter. The record began after this vendor was
                registered, so a null here is a limit of the record rather than a claim nothing
                was ever asked.
              </div>
            ) : (
              <>
                <div className="text-meta text-muted-foreground">
                  Last asked {formatTimestamp(adapter.last_attempt_at)}
                  {adapter.last_attempt_outcome === "success" &&
                    adapter.last_attempt_changes !== null &&
                    ` — returned ${adapter.last_attempt_changes.toLocaleString()} change${adapter.last_attempt_changes === 1 ? "" : "s"}`}
                </div>
                {adapter.last_attempt_reason !== null && (
                  <div className="text-meta text-muted-foreground leading-relaxed">
                    {readReason(adapter.last_attempt_reason)}
                  </div>
                )}
              </>
            )}
            {Object.keys(adapter.attempts).length > 0 && (
              <div className="flex flex-wrap gap-section text-meta text-muted-foreground">
                {/* Only outcomes that occurred are keys — `AdapterRow.attempts`'s own contract —
                    so this never prints an outcome at nought that was never measured. */}
                {Object.entries(adapter.attempts)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([outcome, count]) => (
                    <span key={outcome}>
                      {outcome} <span className="font-mono text-foreground">{count.toLocaleString()}</span>
                    </span>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
