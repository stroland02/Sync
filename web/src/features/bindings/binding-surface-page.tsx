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
 *
 * ---
 *
 * **M7-W164 moved this screen onto the chassis, and two of its decisions are about density
 * rather than composition, because this is the console's densest screen.**
 *
 * *No stat tiles.* `FactList` sits beside the header, where it costs nothing above the fold; a
 * row of `FactTile`s under it would cost about a hundred vertical pixels on a screen whose
 * scarce resource is rows above the fold on a 2,500-row table. Every count a tile row would
 * have carried is already on screen — the repository facet counts them per repository, and the
 * footer bar counts the page against the total.
 *
 * *No card around either table.* A `Card` costs 32px of horizontal room, and this table is the
 * one place in the console where 32px changes a row's height. B115 records that the row falls
 * from 77px to 57px at 1,170px of table width; the card was inside that budget. The two regions
 * are told apart by their headings and by the rule each footer bar draws under itself, which is
 * what separates them on a screen that is one subject rather than two.
 *
 * ## Ported onto the vendored substrate by M7-W176
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-binding-surface.md` is the mapping table this port
 * was gated on. Read that before porting a level, not this docstring.
 *
 * **This is the level where the substrate is refused on a number.** Every level before it put its
 * regions inside the vendored `Card`, which costs its contents 32px of horizontal room. Measured at
 * 1440x900 against the 2,500-row scale fixture, the call-site table's rows stand at 56px with
 * 1097px to draw in and at 76px with 1081px — so a card does not merely cost twenty pixels a row,
 * it clears a cliff sixteen pixels wide with nothing to spare. B115 recorded the same effect before
 * the substrate existed and the two paragraphs above are what it left behind; this port re-measured
 * it on the ported anatomy and kept the arrangement. The changes table would fit in a card and does
 * not get one either, because one ringed panel beside one bare table on a screen that is one
 * subject draws a grouping claim across a boundary that is not there.
 *
 * What the substrate does land on this level: both tables take the Studio anatomy through
 * `components/data-table`, and the vendored `Card` composes the drawer, where 32px buys something
 * and costs no row anything.
 *
 * **The rung moves to the first column.** It was eighth of nine — the last table in the console
 * still ordering it that way, and the widest. `vendor-findings-table.tsx` carries the argument in
 * the comment this repository's honesty guard pins by its "sideways scroll" fragment: the call site
 * is the widest cell, and a rung column that is safe only because no fixture has yet been long
 * enough is protected by the fixture rather than by the layout. The identifying column is therefore
 * second, which departs from Studio's anatomy on the console's own rule.
 */

import { useParams, useSearchParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useBindingSurface } from "@/api/queries"
import type { BindingSurfaceResponse } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { type Fact, FactList } from "@/components/fact-list"
import { ActiveFilters, FacetChips, PrefixFilter } from "@/components/filters"
import { RungBadge } from "@/components/provenance"
import { Skeleton } from "@/components/skeleton"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { BindingDrawer } from "@/features/bindings/binding-drawer"
import {
  BINDING_KEY,
  bindingKey,
  selectBinding,
} from "@/features/bindings/binding-selection"
import { joinOrAbsent } from "@/features/bindings/call-site-fields"
import { formatTimestamp, orAbsent, pathAfter } from "@/lib/format"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { ControlBar } from "@/layouts/control-bar"
import { DetailGrid } from "@/layouts/detail-grid"
import { FooterBar } from "@/layouts/footer-bar"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"
import { useClearFilters, useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const DEFAULT_QUESTION =
  "A vendor shipped a breaking change — what call sites does it hit?"

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

/**
 * Call sites bound to this operation across every repository, before any filter on this page.
 *
 * `repositories` is the facet's own scope rather than the table's: it is the option list the
 * repository chips are built from, so it stays the same whichever chip is selected. That makes it
 * the right denominator for a stated fact about the operation and the wrong one for the table,
 * which is why the number under the table is a different number and the sentence beside the facts
 * says so.
 */
function boundCallSites(data: BindingSurfaceResponse): number {
  return data.repositories.reduce((sum, repo) => sum + repo.call_site_count, 0)
}

/**
 * The operation's own facts, label left and value right, beside the header rather than under it.
 *
 * Three states per counted fact and they are three different claims. A `Skeleton` says the query
 * is in flight — `components/skeleton.tsx` carries why that is not one of `states.tsx`'s five
 * sentences. `<Absent>` says the query failed, which is not the same as a count of zero, and the
 * error state under it names what failed. A number says the number.
 */
function operationFacts(
  vendorId: string,
  operationId: string,
  repoId: string | null,
  data: BindingSurfaceResponse | null,
  failed: boolean
): Fact[] {
  const counted = (value: number, width: string) => {
    if (data !== null) return value.toLocaleString()
    return failed ? <Absent>the API did not answer</Absent> : <Skeleton width={width} />
  }

  return [
    { label: "Vendor", value: <span className="font-mono">{vendorId}</span> },
    { label: "Operation", value: <span className="font-mono">{operationId}</span> },
    {
      label: "Repository scope",
      value:
        repoId === null ? (
          "Every repository the index has seen"
        ) : (
          <span className="font-mono">{repoId}</span>
        ),
    },
    { label: "Call sites bound", value: counted(data ? boundCallSites(data) : 0, "w-16") },
    { label: "Repositories", value: counted(data ? data.repositories.length : 0, "w-10") },
    { label: "Vendor changes", value: counted(data ? data.changes.total : 0, "w-10") },
    // Hardcoded because the payload hardcodes it, and `RungNote` below carries the argument. A
    // badge rather than the word so the page-level rung and the column read as the same claim.
    { label: "Binding rung", value: <RungBadge rung="static" /> },
  ]
}

/**
 * What the counts beside the header are counted over, which is not what the table is counted over.
 *
 * The two disagree whenever a filter is on, and that is deliberate rather than a defect: an option
 * list narrowed by the filter it sets collapses to whatever is already selected. So the screen says
 * which number answers which question instead of leaving a reader to assume they agree.
 */
function ScopeNote({ repoId }: { repoId: string | null }) {
  return (
    <p className="max-w-prose text-body text-ink-muted">
      {repoId === null ? null : (
        <>
          The call-site table below is scoped to <code className="font-mono">{repoId}</code>.{" "}
        </>
      )}
      The counts beside this are taken across every repository the index has seen, whatever is
      selected below — they are the choices available, not the rows on screen. The range under the
      table is the number that moves when a filter is set.
    </p>
  )
}

/**
 * The directory every call site on this page shares, stated once so the column does not repeat it.
 *
 * Measured on 2026-08-06 at 1440x900 against `--scale 10000`: the path column wanted 854px on one
 * line and was granted 572px, because eight other columns are ahead of it — and **65% of what it
 * held was a prefix identical on all 2,500 rows**. Four columns were wrapping to three lines at
 * once, so the row stood at 76px and eleven fit above the fold.
 *
 * This is not a truncation and nothing is hidden. The whole path is the sentence below plus the
 * cell beside it, and both are on screen; a reader matching a row to their editor needs the
 * filename and line, which is exactly what the cell keeps. `break-words` stays on that cell, so a
 * customer-supplied path with no break opportunity still grows the row instead of overflowing the
 * column and pushing the rung out of the viewport.
 *
 * Empty means the rows share no directory — two trees calling one operation — and then the column
 * carries the whole path and this says nothing. `pathAfter` is what makes that fallback one branch
 * rather than a slice that would render `ing/charges/create.ts` and read like a real file.
 *
 * **It stays above the table rather than moving into the footer bar's `left` slot**, which that
 * component's docstring offers it. A reader meets this sentence to understand a column they are
 * about to read; under the table it would arrive after the reading it exists to make possible.
 */
function SharedDirectoryNote({ directory }: { directory: string }) {
  // Truthiness rather than `=== ""`, and it earned that during this item's own measurement: a dev
  // API still serving the Python from before the field existed sent no key at all, and the strict
  // comparison let `undefined` through to render "Every call site below is under , so...". The
  // payload always carries a string, so this is not a condition the API can produce — it is a
  // sentence that must not be able to render half-formed, which is a different bar.
  if (!directory) return null

  return (
    <p className="max-w-prose text-body text-muted-foreground">
      Every call site below is under <code className="font-mono">{directory}</code>, so the call-site
      column carries what follows it. The whole path is that prefix and the cell together — nothing
      here is shortened away.
    </p>
  )
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
  const bound = boundCallSites(data)

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
  question,
}: {
  vendorId: string
  operationId: string
  repoId: string | null
  question: string
}) {
  const [callSitesOffset, setCallSitesOffset] = useOffsetParam(CALL_SITES_OFFSET_KEY)
  const [changesOffset, setChangesOffset] = useOffsetParam("changes_offset")
  const [pathPrefix, setPathPrefix] = useFilterParam(PATH_PREFIX_KEY, CALL_SITE_RESETS)
  const setRepoId = useFilterParam(REPO_KEY, CALL_SITE_RESETS)[1]
  // No `resets`, unlike every other parameter on this screen. Opening a detail does not change
  // which rows exist, so the page position measured against them is still the right one.
  const [openBinding, setBinding] = useFilterParam(BINDING_KEY)
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
    <>
      {/* The one place on this screen where a region sits beside another. `lg:` rather than `xl:`
          so both measured viewports get it, and `minmax(0,...)` on the facts column so a long
          repository id shrinks the column instead of widening the grid past the frame. */}
      <DetailGrid
        railSide="end"
        rail={
          <FactList
            facts={operationFacts(
              vendorId,
              operationId,
              repoId,
              query.isSuccess ? query.data : null,
              query.isError
            )}
          />
        }
      >
        <PageHeader
          // Fleet and the vendor are the top bar's, derived from this same address. The
          // operation stays: it is deeper than the vendor, which is where that trail stops.
          // M7-W195.
          trail={<Breadcrumbs trail={[{ label: operationId }]} />}
          title={
            <span className="font-mono">
              {vendorId} / {operationId}
            </span>
          }
          question={question}
        />
        <ScopeNote repoId={repoId} />
      </DetailGrid>

      {query.isPending && <LoadingState what={`bindings for ${vendorId}/${operationId}`} />}
      {query.isError && (
        <ErrorState error={query.error} what={`bindings for ${vendorId}/${operationId}`} />
      )}

      {query.isSuccess && (
        <>
          <section className="flex flex-col gap-section">
            <div className="flex flex-col gap-field">
              <h2 className="text-section">Call sites</h2>
              <p className="max-w-prose text-body text-ink-muted">
                What in the codebase calls this operation, and how the system knows it does.
              </p>
            </div>
            <ControlBar>
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
            </ControlBar>
            <ActiveFilters filters={activeFilters} onClear={clearCallSiteFilters} />
            <SharedDirectoryNote directory={query.data.call_sites_common_directory} />
            {query.data.call_sites.items.length === 0 ? (
              <CallSitesEmptyState
                data={query.data}
                repoId={repoId}
                filters={activeFilters}
                offset={callSitesOffset}
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    {/* Rung first, on `vendor-findings-table.tsx`'s argument: the call site is the
                        widest cell in this table and no fixture here is long enough to prove it, so
                        a rung column further right is a column the layout does not protect. */}
                    <TableHead>Rung</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Call site</TableHead>
                    <TableHead>Symbol</TableHead>
                    <TableHead>SDK version</TableHead>
                    <TableHead>Argument keys</TableHead>
                    <TableHead>Response fields read</TableHead>
                    <TableHead>Loop depth</TableHead>
                    <TableHead>Indexed at</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.call_sites.items.map((site) => (
                    <TableRow
                      key={bindingKey(site)}
                      data-state={openBinding === bindingKey(site) ? "selected" : undefined}
                    >
                      <TableCell>
                        <RungBadge rung={site.binding_rung} />
                      </TableCell>
                      <TableCell className="font-mono">{site.repo_id}</TableCell>
                      <TableCell className="font-mono">
                        {/* A button rather than a `Link`: the drawer is a search parameter on this
                            same address, so a right-click "open in new tab" would land on a screen
                            with no page position and no filters — which is not where the reader is
                            looking. `useFilterParam` still pushes the history entry, so Back
                            closes it. */}
                        <button
                          type="button"
                          onClick={() => setBinding(bindingKey(site))}
                          className="text-left underline underline-offset-2 break-words"
                          aria-label={`Binding at ${site.path} line ${site.line} in ${site.repo_id}`}
                        >
                          {pathAfter(query.data.call_sites_common_directory, site.path)}:
                          {site.line}:{site.col}
                        </button>
                      </TableCell>
                      <TableCell className="font-mono">
                        <Formatted value={orAbsent(site.symbol)} />
                      </TableCell>
                      <TableCell className="font-mono">
                        <Formatted value={orAbsent(site.sdk_version)} />
                      </TableCell>
                      <TableCell className="font-mono">
                        <Formatted value={joinOrAbsent(site.args_keys)} />
                      </TableCell>
                      <TableCell className="font-mono">
                        <Formatted value={joinOrAbsent(site.response_fields_read)} />
                      </TableCell>
                      <TableCell className="font-mono">{site.loop_depth}</TableCell>
                      <TableCell className="font-mono text-meta">
                        <Formatted value={formatTimestamp(site.indexed_at)} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <RungNote data={query.data} filtered={activeFilters.length > 0} />
            <FooterBar
              offset={callSitesOffset}
              limit={DEFAULT_LIMIT}
              shown={query.data.call_sites.items.length}
              total={query.data.call_sites.total}
              nextOffset={query.data.call_sites.next_offset}
              busy={query.isFetching}
              onOffsetChange={setCallSitesOffset}
              left={
                <p className="max-w-prose text-body text-muted-foreground">
                  Either this operation has never had a call site here, or it had one that was
                  later retracted — this table cannot tell the two apart.
                </p>
              }
            />
          </section>

          <section className="flex flex-col gap-section">
            <div className="flex flex-col gap-field">
              <h2 className="text-section">Vendor changes</h2>
              <p className="max-w-prose text-body text-ink-muted">
                What the vendor changed about this operation, whether or not a call site above is
                affected. A vendor change is not a binding and carries no rung — it is evidence
                about the vendor, not about the codebase.
              </p>
            </div>
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
                <FooterBar
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
          </section>

          {/* Mounted beside the list rather than inside the table, so the drawer's contents are
              not remounted by a row re-render and so a URL that names a call site this page does
              not hold still opens something that says so. */}
          <BindingDrawer
            selection={selectBinding(openBinding, query.data.call_sites.items)}
            data={query.data}
            onClose={() => setBinding(null)}
          />
        </>
      )}
    </>
  )
}

export interface BindingSurfacePageProps {
  readonly question?: string
}

export function BindingSurfacePage({ question = DEFAULT_QUESTION }: BindingSurfacePageProps) {
  const { vendorId, operationId } = useParams<{ vendorId: string; operationId: string }>()
  const [searchParams] = useSearchParams()
  if (vendorId === undefined || operationId === undefined) return <UnknownRoute />
  const repoId = searchParams.get("repo_id")
  return (
    <BindingSurfaceDetail
      vendorId={vendorId}
      operationId={operationId}
      repoId={repoId}
      question={question}
    />
  )
}
