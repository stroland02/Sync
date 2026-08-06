/**
 * One vendor operation: every call site the index binds to it, and what the vendor changed.
 *
 * `sync.dashboard.graph_views.binding_surface` reads `GraphStore` alone, never `GraphSurface`
 * — an aggregate across every repository the index has seen is a real question and a detector
 * per finding is not what is asking it here.
 *
 * Not a `Provenance` page. `ProvenanceStrip` renders an envelope `whats_at_risk` and
 * `whats_changed` genuinely carry — a feed-fetch timestamp and a context-savings figure this
 * route never computes. Forcing that shape here would invent two fields the transport does
 * not send, which is exactly what keeps `WorkflowState` and `RunsPage` off it elsewhere in
 * this console; the honest page-level rung sentence below is written in prose instead, the
 * fourth such sentence beside the three `ProvenanceStrip` already carries.
 */

import { useParams, useSearchParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useBindingSurface } from "@/api/queries"
import type { BindingSurfaceResponse } from "@/api/types"
import { PageControls } from "@/components/page-controls"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
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

function describeScope(vendorId: string, operationId: string, repoId: string | null): string {
  return repoId === null
    ? `${vendorId}/${operationId}, every repository the index has seen`
    : `${vendorId}/${operationId}, scoped to ${repoId}`
}

/**
 * The page-level rung, in prose rather than through `ProvenanceStrip`.
 *
 * `binding_surface` hardcodes every call-site row to `static` — a call site is what the
 * static index found, so a row built from it alone can honestly carry no other rung. That
 * makes the page-level claim provable rather than merely asserted: there is nothing here for
 * the rungs to mix over, unlike a page assembled from more than one detector's findings.
 */
function RungNote({ data }: { data: BindingSurfaceResponse }) {
  if (data.call_sites.total === 0) {
    return (
      <p className="text-body text-muted-foreground">
        No call site carries a rung here, because none is bound to this operation — see below
        for what that absence does and does not mean.
      </p>
    )
  }
  return (
    <p className="text-body text-muted-foreground">
      Every call site below rests on the <RungBadge rung="static" /> rung: what the index found
      by reading the source, never a resolution or a correlation step. A stronger rung for this
      same operation — traffic Sync has actually observed calling it — is a separate kind of
      evidence on the repository's own coverage page, never blended into this row.
    </p>
  )
}

function BindingSurfaceDetail({
  vendorId,
  operationId,
  repoId,
}: {
  vendorId: string
  operationId: string
  repoId: string | null
}) {
  const [callSitesOffset, setCallSitesOffset] = useOffsetParam("call_sites_offset")
  const [changesOffset, setChangesOffset] = useOffsetParam("changes_offset")
  const query = useBindingSurface(vendorId, operationId, {
    repoId: repoId ?? undefined,
    callSitesLimit: DEFAULT_LIMIT,
    callSitesOffset,
    changesLimit: DEFAULT_LIMIT,
    changesOffset,
  })

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs
        trail={[
          { label: "Fleet", to: "/" },
          { label: vendorId, to: `/vendors/${encodeURIComponent(vendorId)}` },
          { label: operationId },
        ]}
      />
      <h1 className="font-mono text-page">
        {vendorId} / {operationId}
      </h1>
      <p className="text-body text-muted-foreground">
        {describeScope(vendorId, operationId, repoId)}.
      </p>

      {query.isPending && <LoadingState what={`bindings for ${vendorId}/${operationId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`bindings for ${vendorId}/${operationId}`} />
      )}

      {query.isSuccess && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Call sites</CardTitle>
              <CardDescription>
                What in the codebase calls this operation, and how the system knows it does.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {query.data.call_sites.total === 0 ? (
                <EmptyState
                  headline="No call site in the index is bound to this operation."
                  detail={
                    repoId === null
                      ? "The API answered with an empty list. Either nothing in any indexed repository calls this operation, or nothing indexed does — the index cannot tell the two apart."
                      : `The API answered with an empty list scoped to ${repoId}. Either nothing in this repository calls the operation, or this repository has not been indexed at all — the index cannot tell the two apart.`
                  }
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Repository</TableHead>
                        <TableHead>Call site</TableHead>
                        <TableHead>Symbol</TableHead>
                        <TableHead>SDK version</TableHead>
                        <TableHead>Rung</TableHead>
                        <TableHead>Indexed at</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.call_sites.items.map((site) => (
                        <TableRow key={`${site.repo_id}-${site.path}-${site.line}-${site.col}`}>
                          <TableCell className="font-mono">{site.repo_id}</TableCell>
                          <TableCell className="font-mono">
                            {site.path}:{site.line}:{site.col}
                          </TableCell>
                          <TableCell className="font-mono">
                            <Formatted value={orAbsent(site.symbol)} />
                          </TableCell>
                          <TableCell className="font-mono">
                            <Formatted value={orAbsent(site.sdk_version)} />
                          </TableCell>
                          <TableCell>
                            <RungBadge rung={site.binding_rung} />
                          </TableCell>
                          <TableCell className="font-mono text-meta">
                            <Formatted value={formatTimestamp(site.indexed_at)} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <PageControls
                    offset={callSitesOffset}
                    limit={DEFAULT_LIMIT}
                    shown={query.data.call_sites.items.length}
                    total={query.data.call_sites.total}
                    nextOffset={query.data.call_sites.next_offset}
                    busy={query.isFetching}
                    onOffsetChange={setCallSitesOffset}
                  />
                </>
              )}
              <RungNote data={query.data} />
              <p className="text-body text-muted-foreground">
                Either this operation has never had a call site here, or it had one that was
                later retracted — this table cannot tell the two apart.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Vendor changes</CardTitle>
              <CardDescription>
                What the vendor changed about this operation, whether or not a call site above
                is affected. A vendor change is not a binding and carries no rung — it is
                evidence about the vendor, not about the codebase.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {query.data.changes.total === 0 ? (
                <EmptyState
                  headline="The vendor has never changed this operation."
                  detail="The API answered with an empty list. No ingested feed names a change against this operation — that is an answer, not a failure."
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Detected</TableHead>
                        <TableHead>Kind</TableHead>
                        <TableHead>Severity</TableHead>
                        <TableHead>Path</TableHead>
                        <TableHead>Versions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {query.data.changes.items.map((change) => (
                        <TableRow key={change.change_id}>
                          <TableCell className="font-mono text-meta">
                            <Formatted value={formatTimestamp(change.detected_at)} />
                          </TableCell>
                          <TableCell>{change.kind}</TableCell>
                          <TableCell>{change.severity}</TableCell>
                          <TableCell className="font-mono">
                            <Formatted value={orAbsent(change.path_ptr)} />
                          </TableCell>
                          <TableCell className="font-mono">
                            <Formatted value={orAbsent(change.from_version)} /> →{" "}
                            <Formatted value={orAbsent(change.to_version)} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <PageControls
                    offset={changesOffset}
                    limit={DEFAULT_LIMIT}
                    shown={query.data.changes.items.length}
                    total={query.data.changes.total}
                    nextOffset={query.data.changes.next_offset}
                    busy={query.isFetching}
                    onOffsetChange={setChangesOffset}
                  />
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </section>
  )
}

export function BindingSurfacePage() {
  const { vendorId, operationId } = useParams<{ vendorId: string; operationId: string }>()
  const [searchParams] = useSearchParams()
  if (vendorId === undefined || operationId === undefined) return <UnknownRoute />
  const repoId = searchParams.get("repo_id")
  return <BindingSurfaceDetail vendorId={vendorId} operationId={operationId} repoId={repoId} />
}
