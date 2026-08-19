/**
 * Observed telemetry for one repository: calls, shapes and error windows, in one panel.
 *
 * Moved out of `codebase-page.tsx` on 2026-08-18: the card is telemetry through and through —
 * it renders the three telemetry tables and reads the observed route — and it had grown to a
 * third of a page file whose own subject is the Codebase level. `CLAUDE.md` names a file grown
 * past one clear responsibility as a signal, and this was that signal. Nothing about the
 * rendering moved with the file.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import type { ObservedTelemetryResponse } from "@/api/types"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RungBadge } from "@/components/provenance"
import { Button } from "@/components/ui/button"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { formatTimestamp } from "@/lib/format"
import { ErrorWindowsTable } from "@/features/telemetry/error-windows-table"
import { ObservedCallsTable } from "@/features/telemetry/observed-calls-table"
import { ObservedShapesTable } from "@/features/telemetry/observed-shapes-table"
import { FooterBar } from "@/layouts/footer-bar"
import { useOffsetParam } from "@/lib/use-offset-param"

/** A section inside the telemetry panel. Furniture register, `h3` under the panel's own `h2`. */
function TelemetrySection({
  title,
  hint,
  children,
}: {
  title: string
  /** Explanation on demand — never a protected sentence, which stays in the section body. */
  hint?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex flex-col gap-section">
      <div className="flex items-center gap-row">
        <h3 className="furniture text-meta text-ink-muted">{title}</h3>
        {hint}
      </div>
      {children}
    </div>
  )
}

/**
 * The page-level rung for the telemetry half, in prose rather than through `ProvenanceStrip`
 * — this payload carries no feed-fetch timestamp or context-savings figure to fill that
 * component's envelope with, the same reasoning `binding-surface-page.tsx` documents.
 *
 * It stays a paragraph beneath the table rather than moving into `FooterBar`'s `left` slot, because
 * the branch that matters most is the one with no rows and therefore no footer at all.
 */
function TelemetryRungNote({ data }: { data: ObservedTelemetryResponse }) {
  if (data.calls.total === 0) {
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        {data.telemetry_attached_at === null
          ? "No call has ever been observed for this repository — silence, not a measured zero: no traffic source was ever attached to watch."
          : "No call has been observed for this repository, and a traffic source was watching — a measured zero rather than silence."}
      </p>
    )
  }
  const rungs = new Set(data.calls.items.map((call) => call.binding_rung))
  if (rungs.size === 1) {
    const [only] = rungs
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        Every observed call below rests on the <RungBadge rung={only} /> rung.
      </p>
    )
  }
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      Mixed: the observed calls below carry more than one rung — some correlate to a known
      operation and some do not. The rung column on each row says which is which.
    </p>
  )
}

export function ObservedTelemetryCard({ repoId }: { repoId: string }) {
  const [callsOffset, setCallsOffset] = useOffsetParam("calls_offset")
  const [shapesOffset, setShapesOffset] = useOffsetParam("shapes_offset")
  const [errorWindowsOffset, setErrorWindowsOffset] = useOffsetParam("error_windows_offset")
  const query = useRepositoryObserved(repoId, {
    callsLimit: DEFAULT_LIMIT,
    callsOffset,
    shapesLimit: DEFAULT_LIMIT,
    shapesOffset,
    errorWindowsLimit: DEFAULT_LIMIT,
    errorWindowsOffset,
  })

  return (
    <div className="flex min-w-0 flex-col gap-section">
      {query.isPending && <LoadingState what={`observed telemetry for ${repoId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} onRetry={() => void query.refetch()} />
      )}

      {query.isSuccess && (
        <MetricPanel
          label="Observed telemetry"
          // The one qualification stays in front of the data; the rest of the explanation moves
          // behind the ⓘ and into Settings → Pages (owner direction 2026-08-18). The Signals
          // screen keeps a visible route: the button below the panel label's row.
          hint={
            <InfoHint label="About observed telemetry">
              What traffic showed up for this repository, what shape it had, and how often it
              failed. The Signals screen holds this traffic as the signal-source role&rsquo;s
              panel, beside the vendor role and the human-surface role, rather than this card
              being the whole level.
            </InfoHint>
          }
          caption={
            <div className="flex flex-wrap items-center justify-between gap-row">
              <p className="max-w-prose">
                A row here is evidence a call site was exercised — not proof the binding
                correlating it to an operation is correct.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link to={`/repositories/${encodeURIComponent(repoId)}/observed`}>
                  Open Signals
                </Link>
              </Button>
            </div>
          }
        >
          <TelemetrySection title="Calls">
            {query.data.calls.total === 0 ? (
              /* Two facts, and they are not the same screen. `telemetry_attached_at` is what
                 separates them, and before the payload carried it this card genuinely could not
                 and said so. Saying so now would be claiming a limit that no longer exists. */
              query.data.telemetry_attached_at === null ? (
                <EmptyState
                  headline="Telemetry was never attached to this repository."
                  detail="Nothing has watched this repository's traffic, so there is nothing to have observed. This is the absence of a measurement rather than a measurement of nought — no call site here has been shown unexercised, only unwatched. Fold in a captured export to attach one:"
                  command={`uv run python -m sync ingest --repo-id ${repoId} --vendor stripe --payload <otlp.json>`}
                />
              ) : (
                <EmptyState
                  headline="Telemetry is attached, and no call arrived."
                  detail={`Traffic has been watched for this repository since ${formatTimestamp(query.data.telemetry_attached_at)}, and nothing arrived in the window this answer covers. That is a measured nought: the call sites the index found were not exercised, rather than not looked at.`}
                />
              )
            ) : (
              <>
                <ObservedCallsTable calls={query.data.calls.items} />
                <FooterBar
                  offset={callsOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.calls.items.length}
                  total={query.data.calls.total}
                  nextOffset={query.data.calls.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setCallsOffset}
                />
              </>
            )}
            <TelemetryRungNote data={query.data} />
          </TelemetrySection>

          <TelemetrySection
            title="Shapes"
            hint={
              <InfoHint label="About shapes">
                What the operations this repository calls have looked like on the wire, scoped to
                the vendor/operation pairs this repository&rsquo;s own calls name.
              </InfoHint>
            }
          >
            {/* The scope qualification stays visible: a shape is a vendor-wide fact, and a
                reader who misses that reads vendor data as this repository's. */}
            <p className="max-w-prose text-body text-muted-foreground">
              A shape is a vendor-wide fact, not a per-repository one — nothing in this table
              belongs to this repository alone.
            </p>
            {query.data.shapes.total === 0 ? (
              <EmptyState
                headline="No shape recorded for this repository's operations."
                detail="Either no traffic for these operations has been shaped yet, or this repository's calls did not correlate to any operation."
              />
            ) : (
              <>
                <ObservedShapesTable shapes={query.data.shapes.items} />
                <FooterBar
                  offset={shapesOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.shapes.items.length}
                  total={query.data.shapes.total}
                  nextOffset={query.data.shapes.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setShapesOffset}
                />
              </>
            )}
          </TelemetrySection>

          <TelemetrySection title="Error windows">
            <p className="max-w-prose text-body text-muted-foreground">
              Failure counts have no denominator in this table — a count is not a rate, and
              this view does not compute one.
            </p>
            {query.data.error_windows.total === 0 ? (
              query.data.telemetry_attached_at === null ? (
                <EmptyState
                  headline="Telemetry was never attached, so no error window could be recorded."
                  detail="Nothing has watched this repository's traffic. An empty table here is the absence of a measurement, not a repository that ran without failing."
                />
              ) : (
                <EmptyState
                  headline="No error window recorded for this repository."
                  detail="A traffic source has been watching and recorded no failure window in the period this answer covers. That is a measured nought, and it is still not a success rate — this view has no denominator and does not compute one."
                />
              )
            ) : (
              <>
                <ErrorWindowsTable windows={query.data.error_windows.items} />
                <FooterBar
                  offset={errorWindowsOffset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.error_windows.items.length}
                  total={query.data.error_windows.total}
                  nextOffset={query.data.error_windows.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setErrorWindowsOffset}
                />
              </>
            )}
          </TelemetrySection>
        </MetricPanel>
      )}
    </div>
  )
}
