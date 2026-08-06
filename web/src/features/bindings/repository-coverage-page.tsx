/**
 * One repository: what the index has actually indexed, per vendor, and what telemetry showed
 * up for it.
 *
 * Two view models, two questions. `index_coverage` answers "how much of this codebase has
 * Sync read" from `call_site` alone. `observed_telemetry` answers "what traffic did Sync see"
 * from three tables that carry no bearing on what the static index found — a call site can
 * exist with no traffic observed, and traffic can arrive that correlates to no known call
 * site. Rendering them as two cards rather than one keeps that boundary visible instead of
 * implying either one confirms the other.
 */

import { useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryCoverage, useRepositoryObserved } from "@/api/queries"
import type { ObservedTelemetryResponse } from "@/api/types"
import { PageControls } from "@/components/page-controls"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useOffsetParam } from "@/lib/use-offset-param"

function IndexCoverageCard({ repoId }: { repoId: string }) {
  const query = useRepositoryCoverage(repoId)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Index coverage</CardTitle>
        <CardDescription>
          Call sites the index holds for this repository, per vendor. A vendor absent from the
          table is not zero — it is a question this view cannot answer: whether the indexer
          looked and found nothing, or nothing declares which package to look for.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isPending && <LoadingState what={`index coverage for ${repoId}`} />}
        {query.isError && (
          <ErrorState error={query.error} what={`index coverage for ${repoId}`} />
        )}
        {query.isSuccess &&
          (query.data.total_call_sites === 0 ? (
            <EmptyState
              headline={`The index holds no call site for ${repoId}.`}
              detail="This repository was never indexed, or it was indexed and nothing bound to a vendor was found. Those are the same answer here: the index has no configuration table, so a repository it has never seen a call site from is indistinguishable from one nobody ever configured."
            />
          ) : (
            <div className="flex flex-col gap-4">
              <p className="text-body">
                <span className="font-mono text-emphasis">{query.data.total_call_sites}</span>{" "}
                call site{query.data.total_call_sites === 1 ? "" : "s"} indexed.
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Vendor</TableHead>
                    <TableHead>Call sites</TableHead>
                    <TableHead>Last indexed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(query.data.by_vendor)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([vendorId, count]) => (
                      <TableRow key={vendorId}>
                        <TableCell className="font-mono">{vendorId}</TableCell>
                        <TableCell className="font-mono">{count}</TableCell>
                        <TableCell className="font-mono text-meta">
                          {/* Optional access, not the type contract: `last_indexed` shares
                              `by_vendor`'s key set by construction on every current build of
                              `index_coverage`. The guard is here only because the console's own
                              dev API process can be older than the code it is serving while a
                              deploy is mid-flight, and a stale response must not crash the page
                              that reads it. */}
                          <Formatted
                            value={formatTimestamp(query.data.last_indexed?.[vendorId])}
                          />
                        </TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
              <p className="text-body text-muted-foreground">
                "Last indexed" is the newest indexing timestamp among that vendor's call sites —
                staleness, not a promise the index is current. A repository re-scanned weeks ago
                reports the same value every day after, until another re-index moves it.
              </p>
            </div>
          ))}
      </CardContent>
    </Card>
  )
}

/**
 * The page-level rung for the telemetry half, in prose rather than through `ProvenanceStrip`
 * — this payload carries no feed-fetch timestamp or context-savings figure to fill that
 * component's envelope with, the same reasoning `binding-surface-page.tsx` documents.
 */
function TelemetryRungNote({ data }: { data: ObservedTelemetryResponse }) {
  if (data.calls.total === 0) {
    return (
      <p className="text-body text-muted-foreground">
        No call has ever been observed for this repository — silence, not a measured zero:
        nothing here says whether a traffic source was ever watching.
      </p>
    )
  }
  const rungs = new Set(data.calls.items.map((call) => call.binding_rung))
  if (rungs.size === 1) {
    const [only] = rungs
    return (
      <p className="text-body text-muted-foreground">
        Every observed call below rests on the <RungBadge rung={only} /> rung.
      </p>
    )
  }
  return (
    <p className="text-body text-muted-foreground">
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
        <CardDescription>
          What traffic showed up for this repository, what shape it had, and how often it
          failed. A row here is evidence a call site was exercised — it is not proof the
          binding correlating it to an operation is correct.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {query.isPending && <LoadingState what={`observed telemetry for ${repoId}`} />}
        {query.isError && (
          <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} />
        )}

        {query.isSuccess && (
          <>
            <div className="flex flex-col gap-3">
              <h3 className="text-section">Calls</h3>
              {query.data.calls.total === 0 ? (
                <EmptyState
                  headline="No call has been observed for this repository."
                  detail="The API answered with an empty list. Either nothing has watched this repository's traffic, or nothing arrived while it was watching — this view cannot tell the two apart."
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Rung</TableHead>
                        <TableHead>Vendor / operation</TableHead>
                        <TableHead>Trace</TableHead>
                        <TableHead>Calls</TableHead>
                        <TableHead>Distinct targets</TableHead>
                        <TableHead>Repeated</TableHead>
                        <TableHead>Errors</TableHead>
                        <TableHead>Last seen</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.calls.items.map((call) => (
                        <TableRow key={call.trace_id}>
                          <TableCell>
                            <RungBadge rung={call.binding_rung} />
                          </TableCell>
                          <TableCell className="font-mono">
                            {call.vendor_id} /{" "}
                            {call.operation_id === "" ? <Absent>uncorrelated</Absent> : call.operation_id}
                          </TableCell>
                          <TableCell className="font-mono text-meta">{call.trace_id}</TableCell>
                          <TableCell className="font-mono">{call.call_count}</TableCell>
                          <TableCell className="font-mono">{call.distinct_targets}</TableCell>
                          <TableCell className="font-mono">{call.repeated_calls}</TableCell>
                          <TableCell className="font-mono">{call.error_count}</TableCell>
                          <TableCell className="font-mono text-meta">
                            <Formatted value={formatTimestamp(call.last_seen)} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
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

            <div className="flex flex-col gap-3">
              <h3 className="text-section">Shapes</h3>
              <p className="text-body text-muted-foreground">
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
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Vendor / operation</TableHead>
                        <TableHead>Field</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Nullable seen</TableHead>
                        <TableHead>Source</TableHead>
                        <TableHead>Samples</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.shapes.items.map((shape) => (
                        <TableRow
                          key={`${shape.vendor_id}-${shape.operation_id}-${shape.field_path}`}
                        >
                          <TableCell className="font-mono">
                            {shape.vendor_id} / {shape.operation_id}
                          </TableCell>
                          <TableCell className="font-mono">{shape.field_path}</TableCell>
                          <TableCell className="font-mono">{shape.json_type}</TableCell>
                          <TableCell>{shape.nullable_seen ? "yes" : "no"}</TableCell>
                          <TableCell className="font-mono">{shape.source}</TableCell>
                          <TableCell className="font-mono">{shape.sample_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
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

            <div className="flex flex-col gap-3">
              <h3 className="text-section">Error windows</h3>
              <p className="text-body text-muted-foreground">
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
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Rung</TableHead>
                        <TableHead>Vendor / operation</TableHead>
                        <TableHead>Status class</TableHead>
                        <TableHead>Window</TableHead>
                        <TableHead>Errors</TableHead>
                        <TableHead>Issues</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.error_windows.items.map((window, index) => (
                        <TableRow
                          key={`${window.vendor_id}-${window.operation_id}-${window.window_start}-${index}`}
                        >
                          <TableCell>
                            <RungBadge rung={window.binding_rung} />
                          </TableCell>
                          <TableCell className="font-mono">
                            {window.vendor_id} /{" "}
                            <Formatted value={orAbsent(window.operation_id)} />
                          </TableCell>
                          <TableCell className="font-mono">{window.status_class}</TableCell>
                          <TableCell className="font-mono text-meta">
                            <Formatted value={formatTimestamp(window.window_start)} /> →{" "}
                            <Formatted value={formatTimestamp(window.window_end)} />
                          </TableCell>
                          <TableCell className="font-mono">{window.error_count}</TableCell>
                          <TableCell className="font-mono">{window.issue_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
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

export function RepositoryCoveragePage() {
  const { repoId } = useParams<{ repoId: string }>()
  if (repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs
        trail={[
          { label: "Fleet", to: "/" },
          { label: "Bindings", to: "/bindings" },
          { label: repoId },
        ]}
      />
      <h1 className="font-mono text-page">{repoId}</h1>
      <IndexCoverageCard repoId={repoId} />
      <ObservedTelemetryCard repoId={repoId} />
    </section>
  )
}
