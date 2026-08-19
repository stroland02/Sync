/**
 * Call sites: the raw material of the graph, browsable.
 *
 * Every other screen shows what Sync concluded — findings, runs, solutions. This shows what it
 * *read*: each place in the codebase that calls a vendor API, with the symbol, the operation it
 * bound to, and the position. The owner's gap, named 2026-08-18: "you can see findings but
 * cannot browse your own call sites."
 *
 * **The rung is not a column here, and that is a fact about the table rather than an omission.**
 * A rung describes a *binding* — how the system knows a site reaches an operation — and
 * `call_site` rows carry no rung of their own; the finding does. Rendering one would be
 * inventing an attribution, which is the defect the rung exists to prevent. The binding surface
 * is where a rung is shown, and each row links to it.
 *
 * **Retracted sites are absent, everywhere and deliberately.** A site the last index pass
 * stopped finding is not a place this codebase calls the vendor. The count under the table is
 * of what the filters admit, and the rail's counts are over everything the *other* filters
 * admit — the two answer different questions and each says which.
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
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { MetricPanel } from "@/components/metric-panel"
import { ErrorState, LoadingState } from "@/components/states"
import {
  ColumnVisibilityMenu,
  useColumnVisibility,
  type ColumnSpec,
} from "@/components/column-visibility"
import { CallSitesDashboards } from "@/features/bindings/call-sites-dashboards"
import { CallSiteDrawer } from "@/features/bindings/call-site-drawer"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useFacetParam } from "@/lib/use-facet-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const LIMIT = 50

/**
 * What the table can show, and what it shows by default.
 *
 * M15 Task 1: the payload records fifteen fields per call site and the page drew five. The screen
 * is wide now, so the rest are offered rather than dropped -- and the default set stays the five
 * a reader scans, because a table that opens with everything is as unreadable as one that opens
 * with too little.
 *
 * `File` is not hideable: it is the row's identity, and a table of call sites with no address is
 * a list of things a reader cannot go and look at.
 */
const CALL_SITE_COLUMNS: readonly ColumnSpec[] = [
  { id: "path", label: "File", hideable: false },
  { id: "symbol", label: "Symbol" },
  { id: "vendor", label: "Integration" },
  { id: "operation", label: "Operation" },
  { id: "loops", label: "Loops" },
  { id: "args", label: "Arguments sent", defaultVisible: false },
  { id: "reads", label: "Response fields read", defaultVisible: false },
  { id: "sdk", label: "SDK version", defaultVisible: false },
  { id: "indexed", label: "Indexed", defaultVisible: false },
]

interface CallSiteRow {
  id: string
  repo_id: string
  path: string
  line: number
  col: number
  vendor_id: string
  operation_id: string
  symbol: string
  args_keys: string[]
  response_fields_read: string[]
  loop_depth: number
  sdk_version: string
  indexed_at: string | null
}

interface CallSitesPage {
  repo_id: string
  items: CallSiteRow[]
  total: number
  next_offset: number | null
  by_vendor: Record<string, number>
  unfiltered_total: number
  vendor_id: string | null
  path_prefix: string | null
}

async function fetchCallSites(
  repoId: string,
  params: { vendorId: string | null; pathPrefix: string | null; offset: number },
  signal?: AbortSignal,
): Promise<CallSitesPage> {
  const query = new URLSearchParams({ limit: String(LIMIT), offset: String(params.offset) })
  if (params.vendorId !== null) query.set("vendor_id", params.vendorId)
  if (params.pathPrefix) query.set("path_prefix", params.pathPrefix)
  const path = `/api/repositories/${encodeURIComponent(repoId)}/call-sites?${query.toString()}`
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as CallSitesPage
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

/** The vendor facet, counted over every call site the other filters admit. */
function vendorGroup(
  data: CallSitesPage,
  selected: string | null,
  onSelect: (value: string | null) => void,
): FilterGroup | null {
  const vendors = Object.keys(data.by_vendor).sort()
  if (vendors.length === 0) return null
  const [first, ...rest] = vendors.map((vendor) => ({
    value: vendor,
    label: vendor,
    count: { kind: "counted" as const, value: data.by_vendor[vendor] ?? 0 },
  }))
  return {
    id: "vendor",
    legend: "Integration",
    selected,
    onSelect,
    unfiltered: {
      label: "Every integration",
      count: { kind: "counted", value: data.unfiltered_total },
    },
    options: [first, ...rest],
  }
}

export function CallSitesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("call_sites_offset")
  const [vendorId, setSelectedVendor] = useFacetParam("call_sites_vendor")
  const [pathPrefix] = useFacetParam("call_sites_path")
  // The open row lives in the URL, which is the half of Nango's drawer convention that matters:
  // a reader handing a colleague a link hands them the row they are looking at, not the page.
  const [openSite, setOpenSite] = useFacetParam("call_sites_open")
  const columns = useColumnVisibility("call-sites", CALL_SITE_COLUMNS)
  const query = useQuery({
    queryKey: ["call-sites", repoId ?? "", vendorId, pathPrefix, offset],
    queryFn: ({ signal }) =>
      fetchCallSites(repoId ?? "", { vendorId, pathPrefix, offset }, signal),
    enabled: repoId !== undefined,
  })

  if (repoId === undefined) return <UnknownRoute />

  // A new narrowing starts at the first page: an offset kept from the previous selection can
  // sit past the narrowed set's end, which renders an empty page over a non-empty answer.
  function setVendor(next: string | null) {
    setSelectedVendor(next)
    setOffset(0)
  }

  return (
    <section className="flex min-w-0 flex-col gap-8">
      <Breadcrumbs trail={[{ label: "Call sites" }]} />

      {/* Dashboards C1, C2, C3. Its own read on its own key, deliberately outside the table's
          success branch: the topology answers a different question over the same rows, and a
          failure to page the table is no reason to withhold the shape of what was indexed. */}
      <CallSitesDashboards repoId={repoId} />

      {query.isPending && <LoadingState what={`the call sites in ${repoId}`} />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what={`the call sites in ${repoId}`}
          onRetry={() => void query.refetch()}
        />
      )}

      {query.isSuccess && (
        <div className="grid gap-section lg:grid-cols-[16rem_minmax(0,1fr)] lg:items-start">
          {(() => {
            const group = vendorGroup(query.data, vendorId, setVendor)
            return group === null ? (
              <div />
            ) : (
              <FilterRail
                label="Narrow the call sites"
                countScope="Counted across every call site the index holds for this codebase. The record count under the table describes the narrowed set."
                groups={[group]}
              />
            )
          })()}

          <MetricPanel
            label="Call sites"
            hint={
              <InfoHint label="About call sites">
                Every place this codebase calls an integration&rsquo;s API, as the last index
                pass found it. A site the pass stopped finding is retracted and absent here —
                it is not a place this codebase calls the vendor, though a finding raised
                against it stays addressable. There is no rung column: a rung describes a
                binding, and the binding surface is where one is shown.
              </InfoHint>
            }
            metric={{
              value: query.data.total.toLocaleString(),
              unit:
                vendorId === null
                  ? `call site${query.data.total === 1 ? "" : "s"} in ${repoId}`
                  : `call site${query.data.total === 1 ? "" : "s"} calling ${vendorId}`,
            }}
          >
            {/* The reader chooses which of the fifteen recorded fields to see. Above the table
                rather than in a settings screen: the choice belongs where its effect is. */}
            <div className="flex justify-end">
              <ColumnVisibilityMenu
                columns={CALL_SITE_COLUMNS}
                isVisible={columns.isVisible}
                onToggle={columns.toggle}
              />
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  {columns.isVisible("path") && <TableHead>File</TableHead>}
                  {columns.isVisible("symbol") && <TableHead>Symbol</TableHead>}
                  {columns.isVisible("vendor") && <TableHead>Integration</TableHead>}
                  {columns.isVisible("operation") && <TableHead>Operation</TableHead>}
                  {columns.isVisible("loops") && <TableHead>Loops</TableHead>}
                  {columns.isVisible("args") && <TableHead>Arguments sent</TableHead>}
                  {columns.isVisible("reads") && <TableHead>Response fields read</TableHead>}
                  {columns.isVisible("sdk") && <TableHead>SDK version</TableHead>}
                  {columns.isVisible("indexed") && <TableHead>Indexed</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {query.data.items.length === 0 && (
                  <TableEmptyRow colSpan={columns.visible.size}>
                    {vendorId !== null && query.data.unfiltered_total > 0 ? (
                      <>
                        <span className="text-ink">No call site matches this narrowing.</span>{" "}
                        The index holds {query.data.unfiltered_total.toLocaleString()} call
                        sites here and none of them calls {vendorId} — clear the rail&rsquo;s
                        selection to see them.
                      </>
                    ) : (
                      <>
                        <span className="text-ink">No call site in this codebase.</span> The
                        index answered and found no call to any integration it can watch — a
                        measured zero if a pass has run, and nothing at all if none has. The
                        Overview&rsquo;s Getting started says which.
                      </>
                    )}
                  </TableEmptyRow>
                )}
                {query.data.items.map((site) => (
                  <TableRow
                    key={site.id}
                    onClick={() => setOpenSite(site.id)}
                    className="cursor-pointer"
                  >
                    {columns.isVisible("path") && (
                      <TableCell className="font-mono text-meta">
                        <span className="break-all">{site.path}</span>
                        <span className="text-ink-muted">
                          :{site.line}:{site.col}
                        </span>
                      </TableCell>
                    )}
                    {columns.isVisible("symbol") && (
                      <TableCell className="font-mono">{site.symbol}</TableCell>
                    )}
                    {columns.isVisible("vendor") && (
                      <TableCell className="font-mono text-meta">{site.vendor_id}</TableCell>
                    )}
                    {columns.isVisible("operation") && (
                    <TableCell className="font-mono text-meta">
                      {/* The binding surface is where this site's rung and its vendor changes
                          live — the operation is the address of that screen. */}
                      <Link
                        to={`/repositories/${encodeURIComponent(repoId)}/bindings/vendors/${encodeURIComponent(site.vendor_id)}/operations/${encodeURIComponent(site.operation_id)}`}
                        className="underline underline-offset-2"
                        onClick={(event) => event.stopPropagation()}
                      >
                        {site.operation_id}
                      </Link>
                    </TableCell>
                    )}
                    {columns.isVisible("loops") && (
                      <TableCell className="font-mono text-meta tabular-nums">
                        {site.loop_depth}
                      </TableCell>
                    )}
                    {columns.isVisible("args") && (
                      <TableCell className="text-meta text-ink-muted">
                        {/* Keys only, never values -- `graph-grain.md`'s shapes-not-values rule,
                            and the empty case says which nothing it is. */}
                        {site.args_keys.length === 0 ? (
                          <Absent>none recorded</Absent>
                        ) : (
                          <span className="font-mono">{site.args_keys.join(", ")}</span>
                        )}
                      </TableCell>
                    )}
                    {columns.isVisible("reads") && (
                      <TableCell className="text-meta text-ink-muted">
                        {site.response_fields_read.length === 0 ? (
                          <Absent>none recorded</Absent>
                        ) : (
                          <span className="font-mono">{site.response_fields_read.join(", ")}</span>
                        )}
                      </TableCell>
                    )}
                    {columns.isVisible("sdk") && (
                      <TableCell className="font-mono text-meta">
                        {site.sdk_version ? site.sdk_version : <Absent>not recorded</Absent>}
                      </TableCell>
                    )}
                    {columns.isVisible("indexed") && (
                      <TableCell className="text-meta text-ink-muted">
                        {site.indexed_at === null ? (
                          <Absent>no date</Absent>
                        ) : (
                          <RelativeTime iso={site.indexed_at} />
                        )}
                      </TableCell>
                    )}
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
              unfilteredTotal={vendorId !== null ? query.data.unfiltered_total : undefined}
              onOffsetChange={setOffset}
            />
            <p className="max-w-prose text-meta text-muted-foreground">
              Loops is how many loops enclose the call, from the code itself: zero is once per
              unit of work, one is a page of results becoming one call each, two is quadratic.
              A loop that never runs still counts — this is what the code says, not what ran.
            </p>
          </MetricPanel>

          {/* The row's detail, opened from the row and addressable from the URL -- Nango's
              convention (`references/notes/nango-integration-architecture.md` §4), taken because
              15 recorded fields do not fit a scannable row and a reader handing a colleague a
              link should be handing them the row they are looking at. */}
          <CallSiteDrawer
            site={query.data.items.find((row) => row.id === openSite) ?? null}
            onClose={() => setOpenSite(null)}
          />
        </div>
      )}
    </section>
  )
}
