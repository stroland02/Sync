/**
 * The signal-source role's one built panel: what traffic showed up for this repository, what
 * shape it had, and where error rates moved.
 *
 * Extracted out of what used to be the standalone `ObservedTelemetryPage`, now that the
 * Signals level (`signals-page.tsx`) is the screen this content lives on. Two of Sync's five
 * detectors raise findings from watched traffic rather than from source, and the graph holds
 * `observed_call`, `observed_shape` and `observed_error_window` for exactly that reason.
 *
 * **The honesty constraint here is sharper than on most panels.** An observed call proves a
 * call site was exercised. It does not prove the binding is correct, it does not prove the
 * call site still exists in the source, and an absence of observed calls proves nothing at
 * all: it may mean the code path is cold, that telemetry was never wired up for this
 * repository, or that this identifier does not name a repository the index has seen at all.
 * This route answers the same way in all three cases — empty lists — so every empty state
 * below says all three rather than picking one.
 *
 * No composite figure and no chart: `observed_error_window.error_count` has no denominator in
 * its own table, a shape drift is not an error, and an error window is not a verdict. `source`
 * on a shape or error window names the *mechanism* that produced the row (`interceptor`,
 * `error-payload`, `replay`) — never a vendor's name, per `sync.graph.sources`'s own docstring
 * — so nothing here claims to know which product reported it.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { useRepositoryObserved } from "@/api/queries"
import { PageControls } from "@/components/page-controls"
import { RungBadge } from "@/components/provenance"
import { ErrorState, LoadingState } from "@/components/states"
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
import { useOffsetParam } from "@/lib/use-offset-param"

function NothingRecorded({ what, repoId }: { what: string; repoId: string }) {
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      No {what} recorded for <span className="font-mono">{repoId}</span>. That could mean the
      relevant code path has never run since telemetry started, that telemetry was never wired
      up for this repository, or that this identifier does not name a repository the index has
      seen at all — this payload answers the same way in all three cases, so nothing here picks
      one.
    </p>
  )
}

export function SignalSourcePanel({ repoId }: { repoId: string }) {
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
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what={`observed telemetry for ${repoId}`} />}
      {query.isError && <ErrorState error={query.error} what={`observed telemetry for ${repoId}`} />}

      {query.isSuccess && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Observed calls</CardTitle>
              <CardDescription className="max-w-prose">
                One row per unit of work's use of one vendor operation. A row proves the call
                ran at least once; it does not prove the operation it names is the operation
                that was actually called — that is what the rung says.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.calls.total === 0 ? (
                <NothingRecorded what="observed calls" repoId={repoId} />
              ) : (
                <div className="flex flex-col gap-section">
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
                            {call.operation_id === "" ? (
                              <Absent>uncorrelated</Absent>
                            ) : (
                              call.operation_id
                            )}
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
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Response shapes</CardTitle>
              <CardDescription className="max-w-prose">
                What the operations this repository's own traffic names have actually been
                seen to return, joined in through those operations rather than stored per
                repository — a shape is a fact about the vendor, not about who calls it.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.shapes.total === 0 ? (
                <NothingRecorded what="response shapes" repoId={repoId} />
              ) : (
                <div className="flex flex-col gap-section">
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
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Error windows</CardTitle>
              <CardDescription className="max-w-prose">
                How many times one operation failed, over a window an error tracker recorded.
                A count here has no denominator and is not a rate — it says nothing on its own
                about whether traffic is getting worse, only how many failures one window held.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.error_windows.total === 0 ? (
                <NothingRecorded what="error windows" repoId={repoId} />
              ) : (
                <div className="flex flex-col gap-section">
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
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
