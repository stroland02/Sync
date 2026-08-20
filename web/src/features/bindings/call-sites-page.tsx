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
import { BindingStatusTag } from "@/components/tag"
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
import { CallSiteDetail } from "@/features/bindings/call-site-drawer"
import {
  DetailLayout,
  useSelectionKeys,
  useSelectionParam,
} from "@/components/detail-layout"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { FooterBar } from "@/layouts/footer-bar"
import { UnknownRoute } from "@/layouts/unknown-route"
import { vendorName } from "@/features/vendors/vendor-name"
import { useFacetParam } from "@/lib/use-facet-param"
import { useFilterListParam } from "@/lib/use-filter-list-param"
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
  { id: "vendor", label: "Vendor" },
  { id: "operation", label: "Operation" },
  { id: "loops", label: "Loops" },
  { id: "status", label: "Status" },
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
  binding_status: string
  sdk_version: string
  indexed_at: string | null
  snippet?: string | null
  snippet_start_line?: number | null
}

interface CallSitesPage {
  repo_id: string
  items: CallSiteRow[]
  total: number
  next_offset: number | null
  by_vendor: Record<string, number>
  by_operation: Record<string, number>
  // Keyed by depth. JSON object keys are strings, so the numeric depth arrives spelled as one.
  by_loop_depth: Record<string, number>
  by_binding_status: Record<string, number>
  unfiltered_total: number
  vendor_ids: string[]
  operation_ids: string[]
  loop_depths: number[]
  binding_statuses: string[]
  path_prefix: string | null
  source_served: boolean
}

async function fetchCallSites(
  repoId: string,
  params: {
    vendorIds: readonly string[]
    operationIds: readonly string[]
    loopDepths: readonly string[]
    bindingStatuses: readonly string[]
    pathPrefix: string | null
    offset: number
  },
  signal?: AbortSignal,
): Promise<CallSitesPage> {
  const query = new URLSearchParams({ limit: String(LIMIT), offset: String(params.offset) })
  // Appended once per value: `?vendor_id=a&vendor_id=b` is the union `_values_param` reads on
  // the other side. Not comma-joined -- a separator that can occur inside a vendor or operation
  // identifier is a parser that is wrong on somebody's repository and wrong silently.
  for (const vendorId of params.vendorIds) query.append("vendor_id", vendorId)
  for (const operationId of params.operationIds) query.append("operation_id", operationId)
  for (const depth of params.loopDepths) query.append("loop_depth", depth)
  for (const status of params.bindingStatuses) query.append("binding_status", status)
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

/**
 * One facet, counted over every call site the *other* filters admit.
 *
 * Returns `null` for a facet with no values rather than an empty fieldset: a legend over nothing
 * reads as a facet that failed to load, and this one simply has nothing to divide.
 *
 * **There is no rung facet, and that is a fact about the table.** `call_site` carries no rung
 * column -- a rung describes a binding, and the binding surface is where one is shown. A facet
 * whose vocabulary held the single value every row has would assert the other rungs exist here.
 */
function facetGroup(
  id: string,
  legend: string,
  counts: Record<string, number>,
  unfilteredLabel: string,
  unfilteredTotal: number,
  selected: readonly string[],
  onSelect: (value: string | null) => void,
  label: (key: string) => string = (key) => key,
): FilterGroup | null {
  const keys = Object.keys(counts).sort()
  if (keys.length === 0) return null
  const [first, ...rest] = keys.map((key) => ({
    value: key,
    label: label(key),
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

/**
 * A loop depth, in the words `schema.sql` uses for it.
 *
 * The bare integer is the wrong label on a rail: `2` beside a count says nothing, and the whole
 * value of this facet is that a reader hunting a call inside a loop can find one. It stays
 * static evidence either way -- a loop that never runs still counts.
 */
/**
 * A binding status, in the rail's own words.
 *
 * The rail's options are what a reader presses to ask a question, so they read as questions
 * answered rather than as the payload's keys. `not checked` rather than `unchecked` because the
 * negation is the whole point of the option and a prefix is easy to skim past.
 */
function describeStatus(status: string): string {
  if (status === "at_risk") return "at risk"
  if (status === "unchecked") return "not checked"
  return status
}

function describeDepth(depth: string): string {
  if (depth === "0") return "0 - once per unit of work"
  if (depth === "1") return "1 - inside a loop"
  return `${depth} - nested ${depth} deep`
}

export function CallSitesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const [offset, setOffset] = useOffsetParam("call_sites_offset")
  // `useFilterParam` rather than `useFacetParam` plus a separate `setOffset`, and the difference
  // is a real defect rather than tidiness: both hooks call `setSearchParams`, and React Router
  // hands the functional form the *current* params rather than a queued value -- so two writes in
  // one handler give the second a `prev` that predates the first, and the offset reset discarded
  // the facet it was meant to accompany. The rail looked pressed and nothing was refetched, which
  // is the owner's report of 2026-08-19. One write does both.
  // Sets rather than single values (M15 Task 4). Operation and loop depth are new here: the
  // payload counted neither, so a reader could not ask "which call sites reach this operation"
  // without going through the binding surface one operation at a time.
  const [vendorIds, toggleVendor, clearVendors] = useFilterListParam("call_sites_vendor", [
    "call_sites_offset",
  ])
  const [operationIds, toggleOperation, clearOperations] = useFilterListParam(
    "call_sites_operation",
    ["call_sites_offset"],
  )
  const [bindingStatuses, toggleStatus, clearStatuses] = useFilterListParam(
    "call_sites_status",
    ["call_sites_offset"],
  )
  const [loopDepths, toggleDepth, clearDepths] = useFilterListParam("call_sites_loops", [
    "call_sites_offset",
  ])
  const [pathPrefix] = useFacetParam("call_sites_path")
  // The open row lives in the URL -- Nango's convention -- and is written as a history push, so
  // Back closes the panel rather than leaving the screen. `useFacetParam` did not push, which
  // would have made Back skip past the whole table.
  const [openSite, setOpenSite] = useSelectionParam("call_sites_open")
  const columns = useColumnVisibility("call-sites", CALL_SITE_COLUMNS)
  const query = useQuery({
    queryKey: ["call-sites", repoId ?? "", vendorIds, operationIds, loopDepths, bindingStatuses, pathPrefix, offset],
    queryFn: ({ signal }) =>
      fetchCallSites(
        repoId ?? "",
        { vendorIds, operationIds, loopDepths, bindingStatuses, pathPrefix, offset },
        signal,
      ),
    enabled: repoId !== undefined,
  })

  const rows = query.data?.items ?? []
  const selectedSite = rows.find((row) => row.id === openSite) ?? null
  // Arrow keys move down the list with the panel open, which is the affordance a beside-the-list
  // panel exists for -- and the reason a modal would have been the wrong form.
  useSelectionKeys(
    rows.map((row) => row.id),
    selectedSite === null ? null : selectedSite.id,
    setOpenSite,
  )

  if (repoId === undefined) return <UnknownRoute />

  // A new narrowing starts at the first page: an offset kept from the previous selection can
  // sit past the narrowed set's end, which renders an empty page over a non-empty answer. Both
  // the toggle and the clear do it in the one write that changes the filter.
  //
  // The rail sends `null` for its unfiltered option and a value for a press.
  function narrow(toggle: (value: string) => void, clear: () => void) {
    return (value: string | null) => (value === null ? clear() : toggle(value))
  }

  const narrowed =
    vendorIds.length > 0 ||
    operationIds.length > 0 ||
    loopDepths.length > 0 ||
    bindingStatuses.length > 0

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
        <div className="grid gap-section lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-stretch">
          {(() => {
            const groups = [
              facetGroup(
                "status",
                "Binding status",
                query.data.by_binding_status,
                "Every status",
                query.data.unfiltered_total,
                bindingStatuses,
                narrow(toggleStatus, clearStatuses),
                describeStatus,
              ),
              facetGroup(
                "vendor",
                "Integration",
                query.data.by_vendor,
                "Every integration",
                query.data.unfiltered_total,
                vendorIds,
                narrow(toggleVendor, clearVendors),
              ),
              facetGroup(
                "operation",
                "Operation",
                query.data.by_operation,
                "Every operation",
                query.data.unfiltered_total,
                operationIds,
                narrow(toggleOperation, clearOperations),
              ),
              facetGroup(
                "loops",
                "Loop depth",
                query.data.by_loop_depth,
                "Every depth",
                query.data.unfiltered_total,
                loopDepths,
                narrow(toggleDepth, clearDepths),
                describeDepth,
              ),
            ].filter((group) => group !== null)
            return groups.length === 0 ? (
              <div />
            ) : (
              <FilterRail
                label="Narrow the call sites"
                countScope="Each count is over every call site the OTHER facets admit, so pressing an option here does not change the numbers beside its own siblings. The record count under the table describes the narrowed set."
                groups={groups as [FilterGroup, ...FilterGroup[]]}
              />
            )
          })()}

          {/* The detail sits beside the table rather than over it (M15 Task 2): a reader
              working down 165 rows should not close one row to reach the next. */}
          <DetailLayout
            title={selectedSite ? `${selectedSite.path}:${selectedSite.line}` : ""}
            onClose={() => setOpenSite(null)}
            detail={
              selectedSite ? (
                <CallSiteDetail
                  site={selectedSite}
                  sourceServed={query.data?.source_served ?? false}
                />
              ) : null
            }
            list={
              <>
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
                unit: narrowed
                  ? `call site${query.data.total === 1 ? "" : "s"} matching this narrowing`
                  : `call site${query.data.total === 1 ? "" : "s"} in ${repoId}`,
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
                    {columns.isVisible("status") && <TableHead>Status</TableHead>}
                    {columns.isVisible("args") && <TableHead>Arguments sent</TableHead>}
                    {columns.isVisible("reads") && <TableHead>Response fields read</TableHead>}
                    {columns.isVisible("sdk") && <TableHead>SDK version</TableHead>}
                    {columns.isVisible("indexed") && <TableHead>Indexed</TableHead>}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.length === 0 && (
                    <TableEmptyRow colSpan={columns.visible.size}>
                      {narrowed && query.data.unfiltered_total > 0 ? (
                        <>
                          <span className="text-ink">No call site matches this narrowing.</span>{" "}
                          The index holds {query.data.unfiltered_total.toLocaleString()} call
                          sites here and none of them matches every facet pressed — clear the
                          rail&rsquo;s selections to see them.
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
                        <TableCell className="text-meta">{vendorName(site.vendor_id)}</TableCell>
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
                      {columns.isVisible("status") && (
                        <TableCell>
                          <BindingStatusTag status={site.binding_status} />
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
                unfilteredTotal={narrowed ? query.data.unfiltered_total : undefined}
                onOffsetChange={setOffset}
              />
              <p className="max-w-prose text-meta text-muted-foreground">
                Loops is how many loops enclose the call, from the code itself: zero is once per
                unit of work, one is a page of results becoming one call each, two is quadratic.
                A loop that never runs still counts — this is what the code says, not what ran.
              </p>
            </MetricPanel>
              </>
            }
          />


        </div>
      )}
    </section>
  )
}
