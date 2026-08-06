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
 *
 * B91 ruling: `BindingCallSite.args_keys`, `.response_fields_read` and `.loop_depth` are
 * screen gaps, not payload to retire — `parameter_deprecation`, `vendor_change` and
 * `observed_drift` all query the first two, and `loop_depth` is the static evidence a
 * repeated-call finding rests on (`sync.signals.reachability`). All three are now columns
 * below. `ObservedCallRow.server_address` and `.url_template` are the same class of gap one
 * level over, in `features/telemetry`, which this feature does not own.
 */

import { useParams, useSearchParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useBindingSurface } from "@/api/queries"
import type { BindingSurfaceResponse } from "@/api/types"
import { ActiveFilters, FacetChips, FilterBar, PrefixFilter } from "@/components/filters"
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
import { ABSENT, formatTimestamp, orAbsent } from "@/lib/format"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useClearFilters, useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const CALL_SITES_OFFSET_KEY = "call_sites_offset"
const PATH_PREFIX_KEY = "path_prefix"

/**
 * The repository scope, which arrives as a link parameter and is now also a control.
 *
 * `repo_id` was already read here — a link from a repository's own screen carries it so the
 * surface that opens is scoped to where the operator started. It was never settable from this
 * page, so the only way back out of that scope was the browser's Back button. The chips make
 * it a filter, reading and writing the same parameter every existing link already builds.
 */
const REPO_KEY = "repo_id"

/** Both call-site filters clear the call-site page position and leave the changes page alone:
 * the two sets page independently, and narrowing one says nothing about where the other is. */
const CALL_SITE_RESETS = [CALL_SITES_OFFSET_KEY]

/** A string list joined for a table cell, or the absence glyph when the site recorded none. */
function joinOrAbsent(values: string[]): string {
  return values.length === 0 ? ABSENT : values.join(", ")
}

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
function RungNote({ data, filtered }: { data: BindingSurfaceResponse; filtered: boolean }) {
  if (data.call_sites.total === 0 && filtered) {
    // The unfiltered sentence below would be false here: call sites are bound, the filter
    // excluded them. A rung claim about rows a filter removed is a claim about the filter.
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        No call site carries a rung under this filter. That is a fact about the filter and not
        about the operation — the repositories above are the ones the index holds call sites in,
        and they are counted without it.
      </p>
    )
  }
  if (data.call_sites.total === 0) {
    return (
      <p className="max-w-prose text-body text-muted-foreground">
        No call site carries a rung here, because none is bound to this operation — see below
        for what that absence does and does not mean.
      </p>
    )
  }
  return (
    <p className="max-w-prose text-body text-muted-foreground">
      Every call site below rests on the <RungBadge rung="static" /> rung: what the index found
      by reading the source, never a resolution or a correlation step. A stronger rung for this
      same operation — traffic Sync has actually observed calling it — is a separate kind of
      evidence on the repository's own coverage page, never blended into this row.
    </p>
  )
}

/**
 * Which kind of nothing the call-site table is showing.
 *
 * Three, and each is a different fact. Nothing bound at all is an answer about the index. A
 * filter that matched nothing is an answer about the filter, and the repository facet beside
 * it proves the operation is called from somewhere. A page position past the end of a narrowed
 * set is an answer about the URL: the table is not empty, the window is.
 */
function CallSitesEmptyState({
  data,
  repoId,
  filters,
  offset,
}: {
  data: BindingSurfaceResponse
  repoId: string | null
  filters: { label: string; value: string }[]
  offset: number
}) {
  const bound = data.repositories.reduce((sum, repo) => sum + repo.call_site_count, 0)

  if (data.call_sites.total > 0) {
    return (
      <EmptyState
        headline={`This page is past the end of the ${data.call_sites.total.toLocaleString()} call sites that match.`}
        detail={`The API answered with an empty list at offset ${offset}. Call sites match here — this window is not over them. Go back to the first page to see them.`}
      />
    )
  }
  if (filters.length > 0) {
    return (
      <EmptyState
        headline="No call site matches this filter."
        detail={
          `The API answered with an empty list for ${filters.map((f) => `${f.label} ${f.value}`).join(" and ")}. ` +
          `The index holds ${bound.toLocaleString()} call ${bound === 1 ? "site" : "sites"} on this ` +
          `operation across ${data.repositories.length} ` +
          `${data.repositories.length === 1 ? "repository" : "repositories"}, so this is what the ` +
          "filter excluded and not what the index is missing — clear it to see the rest."
        }
      />
    )
  }
  return (
    <EmptyState
      headline="No call site in the index is bound to this operation."
      detail={
        repoId === null
          ? "The API answered with an empty list. Either nothing in any indexed repository calls this operation, or nothing indexed does — the index cannot tell the two apart."
          : `The API answered with an empty list scoped to ${repoId}. Either nothing in this repository calls the operation, or this repository has not been indexed at all — the index cannot tell the two apart.`
      }
    />
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
  const [callSitesOffset, setCallSitesOffset] = useOffsetParam(CALL_SITES_OFFSET_KEY)
  const [changesOffset, setChangesOffset] = useOffsetParam("changes_offset")
  const [pathPrefix, setPathPrefix] = useFilterParam(PATH_PREFIX_KEY, CALL_SITE_RESETS)
  const setRepoId = useFilterParam(REPO_KEY, CALL_SITE_RESETS)[1]
  const clearCallSiteFilters = useClearFilters([REPO_KEY, PATH_PREFIX_KEY], CALL_SITE_RESETS)
  const query = useBindingSurface(vendorId, operationId, {
    repoId: repoId ?? undefined,
    pathPrefix: pathPrefix ?? undefined,
    callSitesLimit: DEFAULT_LIMIT,
    callSitesOffset,
    changesLimit: DEFAULT_LIMIT,
    changesOffset,
  })

  const activeFilters = [
    ...(repoId === null ? [] : [{ label: "repository", value: repoId }]),
    ...(pathPrefix === null ? [] : [{ label: "path", value: pathPrefix }]),
  ]

  return (
    <section className="flex flex-col gap-8">
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
      <p className="max-w-prose text-body text-muted-foreground">
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
            <CardContent className="flex flex-col gap-section">
              <FilterBar>
                <FacetChips
                  legend="Repository"
                  options={query.data.repositories.map((repo) => ({
                    value: repo.repo_id,
                    count: repo.call_site_count,
                  }))}
                  selected={repoId}
                  onSelect={setRepoId}
                  allLabel="Every repository"
                  countScope="Counted over every call site the index holds on this operation, not over the table below — these are the choices available, so they stay the same whichever one is selected and whatever the path filter is set to."
                />
                <PrefixFilter
                  legend="Call site path"
                  value={pathPrefix}
                  onSubmit={setPathPrefix}
                  placeholder="src/billing/"
                  note="Matched as a prefix of the call site's path, never as a substring. It narrows the call sites only: a vendor change has no position in your codebase, so the table below it is untouched."
                />
              </FilterBar>
              <ActiveFilters filters={activeFilters} onClear={clearCallSiteFilters} />
              {query.data.call_sites.items.length === 0 ? (
                <CallSitesEmptyState
                  data={query.data}
                  repoId={repoId}
                  filters={activeFilters}
                  offset={callSitesOffset}
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
                        <TableHead>Argument keys</TableHead>
                        <TableHead>Response fields read</TableHead>
                        <TableHead>Loop depth</TableHead>
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
                          <TableCell className="font-mono">
                            {joinOrAbsent(site.args_keys)}
                          </TableCell>
                          <TableCell className="font-mono">
                            {joinOrAbsent(site.response_fields_read)}
                          </TableCell>
                          <TableCell className="font-mono">{site.loop_depth}</TableCell>
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
              <RungNote data={query.data} filtered={activeFilters.length > 0} />
              <p className="max-w-prose text-body text-muted-foreground">
                Either this operation has never had a call site here, or it had one that was
                later retracted — this table cannot tell the two apart.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Vendor changes</CardTitle>
              <CardDescription className="max-w-prose">
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
