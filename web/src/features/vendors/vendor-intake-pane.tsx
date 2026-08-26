/**
 * Where this integration's record came from, and when anybody last asked for it.
 *
 * Rebuilt from `vendor-sources-card.tsx` (deleted) as the rail pane of the locked record screen.
 * Every claim survives; the card's headings became `FactList` rows so the rail carries the same
 * four sections in a third of the height.
 *
 * `last_change_at` is deliberately not relabelled as an intake time. `AdapterRow` says why: nothing
 * records an intake attempt, only its result, so an adapter polled hourly that has found nothing new
 * for a week reports last week. Calling that "intake" would turn staleness into liveness, which is
 * the distinction this console exists to keep.
 *
 * **This is the deeper half of what the deck's drawer shows.** `vendor-inspector.tsx` names the
 * adapter tier, the feeds and the last attempt from answers it already holds; this pane adds what
 * that drawer cannot reach — the attempt tally by outcome, the decline reason, and the full source
 * string every change row carries.
 */

import { FileInput } from "lucide-react"
import type { ReactNode } from "react"

import { useAdapters } from "@/api/queries"
import { FactList } from "@/components/fact-list"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { AdapterTierTag, Tag } from "@/components/tag"
import { NEVER_DELIVERED_NOTE } from "@/features/settings/adapter-table"

/** No attempt row exists for this vendor. The record's limit, never a claim about the adapter. */
export const NO_INTAKE_RECORD_NOTE =
  "no attempt is recorded — the attempt record began when the table did, which is not the same as nobody having asked"

/** `some_reason_code` read as words: `sync.signals.intake_attempt`'s vocabulary is snake_case. */
function readReason(reason: string): string {
  return reason.replace(/_/g, " ")
}

function AbsentMeta({ children }: { children: string }) {
  return (
    <span className="text-meta">
      <Absent>
        <span>{children}</span>
      </Absent>
    </span>
  )
}

function Section({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-row">
      <h3 className="furniture text-meta text-ink-muted">{heading}</h3>
      {children}
    </section>
  )
}

export function VendorIntakePane({ vendorId }: { vendorId: string }) {
  const query = useAdapters()
  const adapter = query.data?.adapters.find((row) => row.vendor_id === vendorId) ?? null

  return (
    <PanelPane
      label="Where the record comes from"
      icon={FileInput}
      hint={
        <InfoHint label={`About ${vendorId}'s intake record`}>
          <p>
            The adapter serving {vendorId} and what the graph holds from it. Every change row on
            this screen arrived through it, and the <span className="font-mono">source</span> value
            below is how a row is traced back to what produced it.
          </p>
          <p>
            The newest change is not an intake time. Nothing records when an adapter was last asked
            except the attempt row, so a quiet healthy adapter and an adapter nobody runs are
            indistinguishable without it — which is why both are here rather than one.
          </p>
        </InfoHint>
      }
      bodyClassName="flex min-w-0 flex-col gap-section p-section"
    >
      {query.isPending && <LoadingState what={`the adapter serving ${vendorId}`} />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what={`the adapter serving ${vendorId}`}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.isSuccess && adapter === null && (
        <p className="max-w-prose text-meta text-ink-muted">
          No adapter is registered for {vendorId}. Any changes the graph holds for this vendor were
          delivered by an adapter that no longer serves it.
        </p>
      )}
      {query.isSuccess && adapter !== null && (
        <>
          <Section heading="The adapter">
            <FactList
              facts={[
                { label: "Tier", value: <AdapterTierTag tier={adapter.kind} /> },
                {
                  label: "Served from",
                  value: (
                    <span className="font-mono text-meta break-all">
                      <Formatted value={adapter.source} />
                    </span>
                  ),
                },
              ]}
            />
            <p className="max-w-prose text-meta text-ink-muted">
              Parsed into dated vendor change rows. The vendor&rsquo;s published wording and
              signatures are preserved verbatim on every change.
            </p>
          </Section>

          <Section heading="What it has delivered">
            <FactList
              facts={[
                {
                  label: "Change rows",
                  value:
                    adapter.changes === null ? (
                      <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta>
                    ) : (
                      <span className="font-mono tabular-nums">
                        {adapter.changes.toLocaleString()}
                      </span>
                    ),
                },
                {
                  // Never `?? 0`: `changes` and `operations` go null together, but a fallback here
                  // would print a measured nought for a read that returned nothing the day that
                  // stops being true.
                  label: "Operations named",
                  value:
                    adapter.operations === null ? (
                      <AbsentMeta>
                        this adapter has delivered nothing, so the graph holds no operations from it
                      </AbsentMeta>
                    ) : (
                      <span className="font-mono tabular-nums">
                        {adapter.operations.toLocaleString()}
                      </span>
                    ),
                },
                {
                  label: "Newest change detected",
                  value:
                    adapter.last_change_at === null ? (
                      <AbsentMeta>no change recorded</AbsentMeta>
                    ) : (
                      <span className="font-mono text-meta">
                        <RelativeTime iso={adapter.last_change_at} />
                      </span>
                    ),
                },
              ]}
            />
            <p className="max-w-prose text-meta text-ink-muted">
              That time is when the newest of those rows was detected — not when the adapter was
              last asked, which is the attempt below.
            </p>
            <div className="flex min-w-0 flex-col gap-field">
              <span className="furniture text-meta text-ink-muted">Feeds the rows arrived on</span>
              {adapter.sources === null || adapter.sources.length === 0 ? (
                <AbsentMeta>{NEVER_DELIVERED_NOTE}</AbsentMeta>
              ) : (
                <div className="flex min-w-0 flex-wrap gap-field">
                  {adapter.sources.map((source) => (
                    <Tag key={source}>{source}</Tag>
                  ))}
                </div>
              )}
            </div>
          </Section>

          <Section heading="Last intake attempt">
            {adapter.last_attempt_at === null ? (
              <AbsentMeta>{NO_INTAKE_RECORD_NOTE}</AbsentMeta>
            ) : (
              <FactList
                facts={[
                  {
                    label: "Asked",
                    value: (
                      <span className="font-mono text-meta">
                        <RelativeTime iso={adapter.last_attempt_at} />
                      </span>
                    ),
                  },
                  {
                    label: "Outcome",
                    value:
                      adapter.last_attempt_outcome === null ? (
                        <AbsentMeta>no outcome is recorded against that attempt</AbsentMeta>
                      ) : (
                        <Tag
                          tone={
                            adapter.last_attempt_outcome === "success"
                              ? "good"
                              : adapter.last_attempt_outcome === "failed"
                                ? "critical"
                                : "warning"
                          }
                        >
                          {adapter.last_attempt_outcome}
                        </Tag>
                      ),
                  },
                  {
                    label: "Returned",
                    value:
                      adapter.last_attempt_changes === null ? (
                        <AbsentMeta>no row count is recorded against that attempt</AbsentMeta>
                      ) : (
                        <span className="font-mono tabular-nums">
                          {adapter.last_attempt_changes.toLocaleString()}
                        </span>
                      ),
                  },
                  {
                    label: "Reason",
                    value:
                      adapter.last_attempt_reason === null ? (
                        <AbsentMeta>none — a successful attempt records no reason</AbsentMeta>
                      ) : (
                        <Tag>{readReason(adapter.last_attempt_reason)}</Tag>
                      ),
                  },
                ]}
              />
            )}
            {Object.keys(adapter.attempts).length > 0 && (
              <div className="flex min-w-0 flex-col gap-field">
                <span className="furniture text-meta text-ink-muted">Attempts by outcome</span>
                <div className="flex min-w-0 flex-wrap gap-section text-meta text-ink-muted">
                  {/* Only outcomes that occurred are keys — `AdapterRow.attempts`'s own contract —
                      so this never prints an outcome at nought that was never measured. */}
                  {Object.entries(adapter.attempts)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([outcome, count]) => (
                      <span key={outcome}>
                        {outcome}{" "}
                        <span className="font-mono tabular-nums text-ink">
                          {count.toLocaleString()}
                        </span>
                      </span>
                    ))}
                </div>
              </div>
            )}
          </Section>
        </>
      )}
    </PanelPane>
  )
}
