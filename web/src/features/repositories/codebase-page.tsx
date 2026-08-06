/**
 * Codebase: the selected repository, and the root of everything beneath it.
 *
 * `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:397` names this
 * level "Codebase (the selected repository)" and the amended hierarchy (`:433`) keeps it —
 * this screen did not exist until the 2026-08-05 reconciliation found the console had no way
 * to select one, and everything below it (`/vendors/:id`, `/detectors`, the old `/codebase`)
 * was answering fleet-wide for exactly that reason. This is the fix: pick a repository here,
 * and drill down from it into the vendor rows below.
 *
 * Three view models, three questions, and none of them confirms another.
 *
 * `overview_summary` scoped to this repository answers "what is currently wrong here" — the
 * question the design document says a user actually arrives with. `index_coverage` answers
 * "how much of this codebase has Sync read" from `call_site` alone. `observed_telemetry`
 * answers "what traffic did Sync see" from three tables that carry no bearing on what the
 * static index found — a call site can exist with no traffic observed, and traffic can arrive
 * that correlates to no known call site. Three cards rather than one keeps those boundaries
 * visible instead of implying any of them confirms the others, and there is deliberately no
 * figure combining them: a scalar over "what is broken", "what we read" and "what we watched"
 * would collapse three different kinds of not-knowing onto one axis.
 *
 * Every figure on this screen and on every screen below it is scoped to `repoId`. The three
 * routes it reads take the repository — `/api/overview`, `/api/repositories/{repo}/coverage`
 * and `/api/repositories/{repo}/observed` — and each answer names the scope it was computed
 * in, so picking a different repository changes every number here rather than some of them.
 */

import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import type { ObservedTelemetryResponse } from "@/api/types"
import { PageControls } from "@/components/page-controls"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ErrorWindowsTable } from "@/features/telemetry/error-windows-table"
import { ObservedCallsTable } from "@/features/telemetry/observed-calls-table"
import { ObservedShapesTable } from "@/features/telemetry/observed-shapes-table"
import { IndexCoverageCard } from "@/features/repositories/index-coverage-card"
import { OpenFindingsCard } from "@/features/repositories/open-findings-card"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useOffsetParam } from "@/lib/use-offset-param"

/**
 * The page-level rung for the telemetry half, in prose rather than through `ProvenanceStrip`
 * — this payload carries no feed-fetch timestamp or context-savings figure to fill that
 * component's envelope with, the same reasoning `binding-surface-page.tsx` documents.
 */
function TelemetryRungNote({ data }: { data: ObservedTelemetryResponse }) {
  if (data.calls.total === 0) {
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        No call has ever been observed for this repository — silence, not a measured zero:
        nothing here says whether a traffic source was ever watching.
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

function ObservedTelemetryCard({ repoId }: { repoId: string }) {
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
    <Card>
      <CardHeader>
        <CardTitle>Observed telemetry</CardTitle>
        <CardDescription className="max-w-prose">
          What traffic showed up for this repository, what shape it had, and how often it
          failed. A row here is evidence a call site was exercised — it is not proof the
          binding correlating it to an operation is correct. The specification's own Signals
          level (design doc line 435) holds this traffic as the signal-source role's one panel,
          beside the vendor role and the human-surface role —{" "}
          <Link
            to={`/repositories/${encodeURIComponent(repoId)}/observed`}
            className="underline underline-offset-2"
          >
            see it grouped with the other two roles, on the Signals screen
          </Link>{" "}
          — rather than reading this card alone as the whole level.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-section">
        {query.isPending && <LoadingState what={`observed telemetry for ${repoId}`} />}
        {query.isError && (
          <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} />
        )}

        {query.isSuccess && (
          <>
            <div className="flex flex-col gap-section">
              <h3 className="text-section">Calls</h3>
              {query.data.calls.total === 0 ? (
                <EmptyState
                  headline="No call has been observed for this repository."
                  detail="The API answered with an empty list. Either nothing has watched this repository's traffic, or nothing arrived while it was watching — this view cannot tell the two apart."
                />
              ) : (
                <>
                  <ObservedCallsTable calls={query.data.calls.items} />
                  <PageControls
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
            </div>

            <div className="flex flex-col gap-section">
              <h3 className="text-section">Shapes</h3>
              <p className="max-w-prose text-body text-muted-foreground">
                What the operations this repository calls have looked like on the wire, scoped
                to the vendor/operation pairs this repository's own calls above name — a shape
                is a vendor-wide fact, not a per-repository one, so nothing here belongs to this
                repository alone.
              </p>
              {query.data.shapes.total === 0 ? (
                <EmptyState
                  headline="No shape recorded for this repository's operations."
                  detail="Either no traffic for these operations has been shaped yet, or this repository's calls did not correlate to any operation."
                />
              ) : (
                <>
                  <ObservedShapesTable shapes={query.data.shapes.items} />
                  <PageControls
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
            </div>

            <div className="flex flex-col gap-section">
              <h3 className="text-section">Error windows</h3>
              <p className="max-w-prose text-body text-muted-foreground">
                Failure counts have no denominator in this table — a count is not a rate, and
                this view does not compute one.
              </p>
              {query.data.error_windows.total === 0 ? (
                <EmptyState
                  headline="No error window recorded for this repository."
                  detail="Either nothing has tracked errors for this repository, or nothing tracked ever recorded a window — this view cannot tell the two apart."
                />
              ) : (
                <>
                  <ErrorWindowsTable windows={query.data.error_windows.items} />
                  <PageControls
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
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

export function CodebasePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Fleet", to: "/" }, { label: repoId }]} />
      <h1 className="font-mono text-page">{repoId}</h1>
      <OpenFindingsCard repoId={repoId} />
      <IndexCoverageCard repoId={repoId} />
      <ObservedTelemetryCard repoId={repoId} />
    </section>
  )
}
