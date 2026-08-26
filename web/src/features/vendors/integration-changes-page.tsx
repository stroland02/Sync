/**
 * Integration changes: what the vendors this codebase uses have published, newest first — and
 * whether anything here calls the operation each one names.
 *
 * ## What the rebuild is
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../infrastructure_logs`**, a
 * locked three-pane explorer: a narrowing rail, a dense feed that scrolls under a pinned head, and
 * a ranking of the operations the page names. `ScreenFrame layout="locked"` — the page owns no
 * scrollbar and each pane scrolls its own body. The reference's streaming footer and auto-scroll
 * toggle are **refused**: both claim a liveness this feed does not have. Its histogram strip is
 * refused too, and for the chart rule rather than the honesty one — `/api/integration-changes/
 * over-time` answers this deployment with a single day, and a time histogram of one bar reads as
 * broken.
 *
 * ## The join is the point, and it is made here
 *
 * The owner's page, 2026-08-18, sits under Integrations rather than beside Findings, and the
 * placement is the argument. **A change is a fact about a vendor; a finding is a fact about this
 * codebase.** The same published change produces no finding where nothing calls the affected
 * operation — so a feed filed under Findings would imply an exposure the data does not claim.
 *
 * What the old screen could not do was tell those two apart: a breaking change against an
 * operation nobody calls looked exactly like one against an operation with forty call sites. The
 * repository's call-site census supplies the missing half and `change-binding.ts` makes the join,
 * with three distinct nothings rather than one zero.
 *
 * **The severity is the vendor change's own, not a detector's judgement.** A breaking change to an
 * operation nobody calls is severe as published and harmless here.
 *
 * ## What left, and where it went
 *
 * The change-unit roll-up is gone from this screen. `features/findings/change-unit-groups.tsx`
 * renders the same `/api/change-units` grain, rebuilt, on the screen whose job is findings — and
 * a fact written twice will disagree with itself. Its nine columns were also exactly the clutter
 * a narrow pane cannot hold.
 */

import { useQuery } from "@tanstack/react-query"
import { Radio, SlidersHorizontal } from "lucide-react"
import { useMemo } from "react"
import { useParams } from "react-router"

import { useOverview } from "@/api/queries"
import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { ChipTabs } from "@/components/chip-tabs"
import { TableFrame } from "@/components/data-table"
import { DetailLayout, useSelectionKeys, useSelectionParam } from "@/components/detail-layout"
import { FilterRail, type FilterGroup } from "@/components/filter-rail"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  admits,
  bindingOf,
  bindingSplit,
  censusFromCallSites,
  censusNeverIndexed,
  censusUnanswered,
  isBindingView,
  operationsNamed,
  type BindingView,
  type CallSiteCensus,
} from "@/features/vendors/change-binding"
import { ChangeInspector } from "@/features/vendors/change-inspector"
import { ChangesKpis, type ChangesFacets } from "@/features/vendors/changes-dashboards"
import { ChangesFeed, type ChangeRow } from "@/features/vendors/changes-feed"
import { ChangesOperationsPane } from "@/features/vendors/changes-operations-pane"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { describeRecordWindow } from "@/lib/record-window"
import { useFacetParam } from "@/lib/use-facet-param"
import { useFilterListParam } from "@/lib/use-filter-list-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const LIMIT = 50

/**
 * How much of the call-site census one read may carry.
 *
 * `sync.api.app._MAX_LIMIT` is 500, so this is the cap rather than a preference — and it is why
 * `change-binding.ts` refuses to report an absence from a census that stopped short.
 */
const CENSUS_LIMIT = 500

interface ChangesPage {
  items: ChangeRow[]
  total: number
  next_offset: number | null
  by_vendor: Record<string, number>
  by_severity: Record<string, number>
  by_vendor_severity: Record<string, Record<string, number>>
  unfiltered_total: number
  // The route echoes the narrowing as arrays. It was declared here as `vendor_id: string | null`
  // and `severity: string | null` — fields the payload has never carried — so the unnarrowed check
  // built on them was always false and the "Newest change" tile rendered the absence marker
  // forever. The narrowing is read from the URL below instead, which cannot drift from the payload.
  vendor_ids: string[]
  severities: string[]
}

interface CensusPage {
  items: { vendor_id: string; operation_id: string }[]
  total: number
}

async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as T
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

function fetchChanges(
  params: { vendorIds: readonly string[]; severities: readonly string[]; offset: number },
  signal?: AbortSignal,
): Promise<ChangesPage> {
  const query = new URLSearchParams({ limit: String(LIMIT), offset: String(params.offset) })
  // Appended once per value: `?vendor_id=a&vendor_id=b` is the union, and it is what
  // `sync.api.app._values_param` reads. A comma-joined value would need a separator that cannot
  // occur inside a vendor identifier, and there is no such character.
  for (const vendorId of params.vendorIds) query.append("vendor_id", vendorId)
  for (const severity of params.severities) query.append("severity", severity)
  return fetchJson<ChangesPage>(`/api/integration-changes?${query.toString()}`, signal)
}

function fetchCensus(repoId: string, signal?: AbortSignal): Promise<CensusPage> {
  return fetchJson<CensusPage>(
    `/api/repositories/${encodeURIComponent(repoId)}/call-sites?limit=${CENSUS_LIMIT}`,
    signal,
  )
}

function facetGroup(
  id: string,
  legend: string,
  counts: Record<string, number>,
  unfilteredLabel: string,
  unfilteredTotal: number,
  selected: readonly string[],
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
    unfiltered: { label: unfilteredLabel, count: { kind: "counted", value: unfilteredTotal } },
    options: [first, ...rest],
  }
}

export function IntegrationChangesPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const scope = repoId ?? ""
  const [offset, setOffset] = useOffsetParam("changes_offset")
  // Sets rather than single values (M15 Task 4): the narrowing a reviewer actually wants here is
  // breaking *and* deprecation -- two of the five-member severity vocabulary -- and no sequence of
  // presses reached it while a facet held one value.
  const [vendorIds, toggleVendor, clearVendors] = useFilterListParam("changes_vendor", [
    "changes_offset",
  ])
  const [severities, toggleSeverity, clearSeverities] = useFilterListParam("changes_severity", [
    "changes_offset",
  ])
  const [rawView, setView] = useFacetParam("changes_binding")
  const view: BindingView = isBindingView(rawView) ? rawView : "all"
  const [openChange, setOpenChange] = useSelectionParam("changes_open")

  const query = useQuery({
    queryKey: ["integration-changes", vendorIds, severities, offset],
    queryFn: ({ signal }) => fetchChanges({ vendorIds, severities, offset }, signal),
  })
  const censusQuery = useQuery({
    queryKey: ["call-site-census", scope],
    queryFn: ({ signal }) => fetchCensus(scope, signal),
    enabled: repoId !== undefined,
  })
  // The three-way that separates a census of nothing from a repository nobody has looked at.
  // `last_index_run` is the only field that carries it; a `max(indexed_at)` answers neither.
  const overview = useOverview(repoId)

  const census = useMemo<CallSiteCensus>(() => {
    if (censusQuery.isError) return censusUnanswered("the call-site census did not answer")
    if (!censusQuery.isSuccess) return censusUnanswered("the call-site census has not answered yet")
    if (censusQuery.data.total > 0) {
      return censusFromCallSites(censusQuery.data.items, censusQuery.data.total)
    }
    if (!overview.isSuccess) {
      return censusUnanswered(
        "the census holds no call site and the index history did not answer, so a repository that " +
          "calls nothing cannot be told from one nobody has indexed",
      )
    }
    return overview.data.last_index_run === null ? censusNeverIndexed() : censusFromCallSites([], 0)
  }, [censusQuery.isError, censusQuery.isSuccess, censusQuery.data, overview.isSuccess, overview.data])

  const rows = useMemo(() => query.data?.items ?? [], [query.data])
  const split = useMemo(() => bindingSplit(rows, census), [rows, census])
  const shown = useMemo(
    () => rows.filter((row) => admits(view, bindingOf(census, row.vendor_id, row.operation_id))),
    [rows, view, census],
  )
  const operations = useMemo(() => operationsNamed(rows, census), [rows, census])
  useSelectionKeys(
    useMemo(() => shown.map((row) => row.id), [shown]),
    openChange,
    setOpenChange,
  )

  if (repoId === undefined) return <UnknownRoute />

  const narrowed = vendorIds.length > 0 || severities.length > 0
  const facets: ChangesFacets | null =
    query.data === undefined
      ? null
      : {
          by_vendor: query.data.by_vendor,
          by_severity: query.data.by_severity,
          by_vendor_severity: query.data.by_vendor_severity,
          unfiltered_total: query.data.unfiltered_total,
          // The newest row of a narrowed page is the newest *matching* change, which is a
          // different claim from the one the tile makes — so it withholds while narrowed.
          newestDetectedAt: narrowed ? null : (query.data.items[0]?.detected_at ?? null),
        }

  // The screen states what it is showing whether or not the query has answered: a band that
  // appears only on success renders "not asked yet" and "asked and empty" as the same nothing.
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Changes",
          text: describeRecordWindow(
            offset,
            query.data.items.length,
            { count: query.data.total, boundReached: false },
            narrowed ? "change matching this narrowing" : "change",
            narrowed ? "changes matching this narrowing" : "changes",
          ),
          paging: {
            offset,
            limit: LIMIT,
            shown: query.data.items.length,
            total: query.data.total,
            unfilteredTotal: narrowed ? query.data.unfiltered_total : undefined,
            nextOffset: query.data.next_offset,
            busy: query.isFetching,
            onOffsetChange: setOffset,
          },
        },
        {
          // The claim, in the fewest honest words: a count over oasdiff rows is at-least-once, and
          // the Source column is the channel that says which rows those are. The argument — that
          // the tool returns a different answer between runs over identical bytes — is behind the
          // feed's ⓘ and in full on any oasdiff row's drawer. Measured 2026-08-26: as a paragraph
          // it made the chassis status band 132px of a 768px viewport, which is a sixth of the
          // screen spent restating what the column already distinguishes.
          kind: "note",
          text:
            "A count over oasdiff-sourced rows is at-least-once rather than converged. The Source " +
            "column says which rows those are; every other source converges.",
        },
      ]
    : [{ kind: "none", why: query.isError ? "the changes did not answer" : "asking for the changes" }]

  const selected = shown.find((row) => row.id === openChange) ?? null

  const chipCount = (value: number) =>
    census.kind === "counted"
      ? ({ kind: "counted", value } as const)
      : ({
          kind: "unanswered",
          why:
            census.kind === "never-indexed"
              ? "this repository has never been indexed, so no call site was looked for"
              : census.why,
        } as const)

  return (
    <ScreenFrame
      status={status}
      layout="locked"
      subtitle="What the integrations this codebase calls have published, and whether anything here calls the operation each change names."
    >
      {/* Outside the grid, not inside it: the strip portals into the chassis stats bar and renders
          no box here, but its in-page fallback would otherwise claim one of the grid's two cells
          and displace a pane. */}
      {facets !== null && <ChangesKpis facets={facets} />}

      <section className="grid min-h-0 min-w-0 flex-1 grid-rows-[minmax(0,1fr)] gap-field xl:grid-cols-[15rem_minmax(0,1fr)]">
        {/* The rail's cell is always occupied, even where there is no rail to draw. A grid whose
            first child is missing puts the feed in the 15rem track instead. */}
        {(() => {
            if (!query.isSuccess) return <div className="hidden xl:block" />
            const groups = [
              facetGroup(
                "vendor",
                "Integration",
                query.data.by_vendor,
                "Every integration",
                query.data.unfiltered_total,
                vendorIds,
                (value) => (value === null ? clearVendors() : toggleVendor(value)),
              ),
              facetGroup(
                "severity",
                "Severity as published",
                query.data.by_severity,
                "Every severity",
                query.data.unfiltered_total,
                severities,
                (value) => (value === null ? clearSeverities() : toggleSeverity(value)),
              ),
            ].filter((group) => group !== null)
            return groups.length === 0 ? (
              <div className="hidden xl:block" />
            ) : (
              <PanelPane
                label="Narrow the changes"
                icon={SlidersHorizontal}
                className="hidden xl:flex"
              >
                <FilterRail
                  fill
                  label="Narrow the changes"
                  countScope="Counted across every change the graph holds, whichever option is pressed. The record count under the feed describes the narrowed set."
                  groups={groups as [FilterGroup, ...FilterGroup[]]}
                />
              </PanelPane>
            )
        })()}

        <div className="grid min-h-0 min-w-0 grid-rows-[minmax(0,1fr)] gap-field 2xl:grid-cols-[minmax(0,1fr)_22rem]">
          {query.isPending ? (
            <LoadingState what="the integration changes" />
          ) : query.isError ? (
            <ErrorState
              error={query.error}
              what="the integration changes"
              onRetry={() => void query.refetch()}
            />
          ) : (
            <DetailLayout
              docked
              title={selected === null ? "Change" : `${selected.vendor_id} / ${selected.operation_id}`}
              subtitle={selected === null ? undefined : selected.kind}
              onClose={() => setOpenChange(null)}
              detail={
                openChange === null ? null : selected === null ? (
                  <p className="max-w-prose text-body text-ink-muted">
                    The selected change is not on this page of the feed. Clear the binding chips or
                    the rail to bring it back.
                  </p>
                ) : (
                  <ChangeInspector
                    change={selected}
                    binding={bindingOf(census, selected.vendor_id, selected.operation_id)}
                    repoId={repoId}
                  />
                )
              }
              list={
                <PanelPane
                  scroll={false}
                  icon={Radio}
                  label="Published changes"
                  hint={
                    <InfoHint label="About the changes feed">
                      What each integration published between the versions Sync compared, newest
                      first. A change is a fact about the vendor; it becomes a fact about this
                      codebase where a call site binds the operation, which is what the Binds here
                      column reads and what a finding is. The severity is the change&rsquo;s own as
                      published, not a judgement about this codebase. Rows sourced from oasdiff are
                      at-least-once rather than converged: that tool returns a different answer
                      between runs over identical bytes, so a count over them is not a measurement
                      of how much a vendor changed.
                    </InfoHint>
                  }
                  actions={
                    <ChipTabs
                      label="Changes by whether this codebase calls the operation"
                      activeId={view}
                      onSelect={(next) => setView(next === "all" ? null : next)}
                      options={[
                        {
                          id: "all",
                          label: "Every change",
                          count: { kind: "counted", value: split.total },
                        },
                        { id: "bound", label: "Called here", count: chipCount(split.bound) },
                        {
                          id: "unbound",
                          label: "Not called here",
                          count: chipCount(split.notBound),
                        },
                      ]}
                    />
                  }
                  footer={
                    <span className="min-w-0 truncate">
                      {view === "all"
                        ? `${split.total.toLocaleString()} change${split.total === 1 ? "" : "s"} on this page`
                        : `${shown.length.toLocaleString()} of ${split.total.toLocaleString()} changes on this page`}
                      {split.notCounted > 0 && (
                        <>
                          {" — "}
                          {split.notCounted.toLocaleString()} could not be joined to a call site
                        </>
                      )}
                      {" · the chips divide this page, not the record"}
                    </span>
                  }
                >
                  {shown.length === 0 ? (
                    <div className="min-h-0 flex-1 overflow-auto p-section">
                      {rows.length > 0 ? (
                        <EmptyState
                          headline={
                            view === "bound"
                              ? "No change on this page names an operation this codebase calls."
                              : "No change on this page names an operation this codebase leaves alone."
                          }
                          detail={`The page holds ${rows.length.toLocaleString()} changes. The chips divide the page in hand rather than the record, so a change of this kind may sit on another page.`}
                        />
                      ) : narrowed ? (
                        <EmptyState
                          headline="No change matches this narrowing."
                          detail={`The graph holds ${query.data.unfiltered_total.toLocaleString()} changes — clear the rail's selections to see them.`}
                        />
                      ) : (
                        <EmptyState
                          headline="No integration change recorded."
                          detail="The graph was asked and holds none: no adapter has delivered a change yet. That is an answer about what has been fetched, not a claim that the vendors published nothing."
                        />
                      )}
                    </div>
                  ) : (
                    // The frame is what makes the head stick: it moves the scroll onto the vendored
                    // table container, which is the element a `sticky` thead has to sit inside.
                    <TableFrame fill className="rounded-none border-0">
                      <ChangesFeed
                        repoId={repoId}
                        rows={shown}
                        bindingOfRow={(row) => bindingOf(census, row.vendor_id, row.operation_id)}
                        selectedId={openChange}
                        onSelect={(id) => setOpenChange(id === openChange ? null : id)}
                      />
                    </TableFrame>
                  )}
                </PanelPane>
              }
            />
          )}

          {query.isSuccess && (
            <ChangesOperationsPane
              className="hidden 2xl:flex"
              repoId={repoId}
              operations={operations}
              changesOnPage={rows.length}
            />
          )}
        </div>
      </section>
    </ScreenFrame>
  )
}
