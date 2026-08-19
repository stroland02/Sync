/**
 * Integration changes: what the vendors this codebase uses have published, newest first.
 *
 * The owner's page, 2026-08-18, placed under Integrations rather than beside Findings — and
 * the placement is the point. **A change is a fact about a vendor; a finding is a fact about
 * this codebase.** The same published change produces no finding in a repository that never
 * calls the affected operation, so a feed filed under Findings would imply an exposure the
 * data does not claim. Each row links to the binding surface, which is the screen that joins
 * the two.
 *
 * **The severity here is the vendor change's own, not a detector's judgement**, and the two
 * are different registers: a breaking change to an operation nobody calls is severe as
 * published and harmless here.
 *
 * **The oasdiff caveat is stated on screen rather than buried**, because `CLAUDE.md` names it
 * as the one source that does not converge across runs: a count over oasdiff-derived rows is
 * at-least-once, not a measurement, and the source column is what lets a reader see which
 * rows are which.
 */

import { useQuery } from "@tanstack/react-query"
import { Link, useParams } from "react-router"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { FilterRail, type FilterGroup } from "@/components/filter-rail"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { PageTabs, integrationsTabs } from "@/components/page-tabs"
import { ChangesKpis, type ChangesFacets, SeverityPerIntegration } from "@/features/vendors/changes-dashboards"
import { RelativeTime } from "@/components/relative-time"
import { ErrorState, LoadingState } from "@/components/states"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useFacetParam } from "@/lib/use-facet-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const LIMIT = 50

interface ChangeRow {
  id: string
  vendor_id: string
  from_version: string
  to_version: string
  kind: string
  operation_id: string
  path_ptr: string
  severity: string
  source: string
  detected_at: string
}

interface ChangesPage {
  items: ChangeRow[]
  total: number
  next_offset: number | null
  by_vendor: Record<string, number>
  by_severity: Record<string, number>
  by_vendor_severity: Record<string, Record<string, number>>
  unfiltered_total: number
  vendor_id: string | null
  severity: string | null
}

/**
 * The dashboards' input, read off the page's own payload.
 *
 * `newestDetectedAt` comes from the first row rather than a facet, and that is sound only
 * because the query orders by `detected_at DESC` and the dashboards render on the unfiltered
 * first page. It goes null the moment a narrowing is applied — a "newest change" computed over
 * a filtered page would be the newest *matching* change under a label that does not say so.
 */
function facetsOf(page: ChangesPage): ChangesFacets {
  const unnarrowed = page.vendor_id === null && page.severity === null
  return {
    by_vendor: page.by_vendor,
    by_severity: page.by_severity,
    by_vendor_severity: page.by_vendor_severity,
    unfiltered_total: page.unfiltered_total,
    newestDetectedAt: unnarrowed ? (page.items[0]?.detected_at ?? null) : null,
  }
}

async function fetchChanges(
  params: { vendorId: string | null; severity: string | null; offset: number },
  signal?: AbortSignal,
): Promise<ChangesPage> {
  const query = new URLSearchParams({ limit: String(LIMIT), offset: String(params.offset) })
  if (params.vendorId !== null) query.set("vendor_id", params.vendorId)
  if (params.severity !== null) query.set("severity", params.severity)
  const path = `/api/integration-changes?${query.toString()}`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as ChangesPage
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

function facetGroup(
  id: string,
  legend: string,
  counts: Record<string, number>,
  unfilteredLabel: string,
  unfilteredTotal: number,
  selected: string | null,
  onSelect: (value: string | null) => void,
): FilterGroup | null {
  const keys = Object.keys(counts).sort()
  if (keys.length === 0) return null
  const [first, ...rest] = keys.map((key) => ({
    value: key,
    label: key,
    count: { kind: "counted" as const, value: counts[key] ?? 0 },
  }))
  return {
    id,
    legend,
    selected,
    onSelect,
    unfiltered: {
      label: unfilteredLabel,
      count: { kind: "counted", value: unfilteredTotal },
    },
    options: [first, ...rest],
  }
}

export function IntegrationChangesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("changes_offset")
  const [vendorId, setSelectedVendor] = useFacetParam("changes_vendor")
  const [severity, setSelectedSeverity] = useFacetParam("changes_severity")
  const query = useQuery({
    queryKey: ["integration-changes", vendorId, severity, offset],
    queryFn: ({ signal }) => fetchChanges({ vendorId, severity, offset }, signal),
  })

  if (repoId === undefined) return <UnknownRoute />

  function narrow(setter: (value: string | null) => void) {
    return (value: string | null) => {
      setter(value)
      setOffset(0)
    }
  }

  const groups: FilterGroup[] = []
  if (query.isSuccess) {
    const vendorFacet = facetGroup(
      "vendor",
      "Integration",
      query.data.by_vendor,
      "Every integration",
      query.data.unfiltered_total,
      vendorId,
      narrow(setSelectedVendor),
    )
    const severityFacet = facetGroup(
      "severity",
      "Severity as published",
      query.data.by_severity,
      "Every severity",
      query.data.unfiltered_total,
      severity,
      narrow(setSelectedSeverity),
    )
    if (vendorFacet !== null) groups.push(vendorFacet)
    if (severityFacet !== null) groups.push(severityFacet)
  }

  return (
    <section className="flex min-w-0 flex-col gap-8">
      <div className="flex flex-col gap-field">
        <Breadcrumbs trail={[{ label: "Integrations" }]} />
        <PageTabs label="Integrations" tabs={integrationsTabs(repoId)} />
      </div>

      {query.isPending && <LoadingState what="the integration changes" />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what="the integration changes"
          onRetry={() => void query.refetch()}
        />
      )}

      {query.isSuccess && (
        <>
          {/* Dashboards G1 and G3, off facets the page already fetched -- neither costs a
              request, and both describe the whole record rather than the narrowed table. */}
          <ChangesKpis facets={facetsOf(query.data)} />
          <SeverityPerIntegration facets={facetsOf(query.data)} />
        </>
      )}

      {query.isSuccess && (
        <div className="grid gap-section lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start">
          {groups.length > 0 ? (
            <FilterRail
              label="Narrow the changes"
              countScope="Counted across every change the graph holds, whichever option is pressed. The record count under the table describes the narrowed set."
              groups={groups as [FilterGroup, ...FilterGroup[]]}
            />
          ) : (
            <div />
          )}

          <MetricPanel
            label="Integration changes"
            hint={
              <InfoHint label="About integration changes">
                What each integration published between the versions Sync compared, newest
                first. A change is a fact about the vendor — it becomes a fact about this
                codebase only where a call site binds to the operation, which is what a finding
                is. The severity is the change&rsquo;s own as published, not a judgement about
                this codebase.
              </InfoHint>
            }
            metric={{
              value: query.data.total.toLocaleString(),
              unit: `change${query.data.total === 1 ? "" : "s"} recorded`,
            }}
          >
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Detected</TableHead>
                  <TableHead>Integration</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Versions</TableHead>
                  <TableHead>Source</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.length === 0 && (
                  <TableEmptyRow colSpan={7}>
                    {vendorId !== null || severity !== null ? (
                      <>
                        <span className="text-ink">No change matches this narrowing.</span> The
                        graph holds {query.data.unfiltered_total.toLocaleString()} changes —
                        clear the rail&rsquo;s selections to see them.
                      </>
                    ) : (
                      <>
                        <span className="text-ink">No integration change recorded.</span> The
                        graph was asked and holds none: no adapter has delivered a change yet.
                        That is an answer about what has been fetched, not a claim that the
                        vendors published nothing.
                      </>
                    )}
                  </TableEmptyRow>
                )}
                {query.data.items.map((change) => (
                  <TableRow key={change.id}>
                    <TableCell className="font-mono text-meta">
                      <RelativeTime iso={change.detected_at} />
                    </TableCell>
                    <TableCell className="font-mono text-meta">{change.vendor_id}</TableCell>
                    <TableCell className="font-mono text-meta">
                      <Link
                        to={`/repositories/${encodeURIComponent(repoId)}/bindings/vendors/${encodeURIComponent(change.vendor_id)}/operations/${encodeURIComponent(change.operation_id)}`}
                        className="underline underline-offset-2"
                      >
                        {change.operation_id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono text-meta">{change.kind}</TableCell>
                    <TableCell>
                      <span className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted">
                        {change.severity}
                      </span>
                    </TableCell>
                    <TableCell className="font-mono text-meta text-ink-muted">
                      {change.from_version} → {change.to_version}
                    </TableCell>
                    <TableCell className="font-mono text-meta text-ink-muted">
                      {change.source}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <FooterBar
              offset={offset}
              limit={LIMIT}
              shown={query.data.items.length}
              total={query.data.total}
              nextOffset={query.data.next_offset}
              busy={query.isFetching}
              unfilteredTotal={
                vendorId !== null || severity !== null ? query.data.unfiltered_total : undefined
              }
              onOffsetChange={setOffset}
            />
            <p className="max-w-prose text-meta text-muted-foreground">
              Rows whose source is <span className="font-mono">oasdiff</span> are at-least-once
              rather than converged: that tool returns a different answer between runs over
              identical bytes, so a count over them is not a measurement of how much a vendor
              changed. Every other source converges.
            </p>
          </MetricPanel>
        </div>
      )}
    </section>
  )
}
