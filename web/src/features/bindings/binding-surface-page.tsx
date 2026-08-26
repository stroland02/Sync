/**
 * One vendor operation: every call site the index binds to it, and what the vendor changed.
 *
 * **Rebuilt 2026-08-26 against `docs/stitch_sync_developer_console/.../repository_index_explorer/`,
 * on the owner's report that the screen was "unorganized and has cluttered information".** The
 * measurement behind that word, taken in Chrome at 1280x720 before this rebuild: 1397px of content
 * in a 720px viewport to show **four data rows**, a nine-column table, 346 words in six paragraphs,
 * and `ScreenFrame` at its default `flow` layout — one unbounded column. The rebuild is
 * `layout="locked"`: nothing scrolls as a page and four named regions scroll their own bodies.
 *
 * The reference answers this screen's question in this screen's words — its centre pane is titled
 * *Watched call sites* with a count chip, its left pane chooses the scope, its right pane previews
 * the selected call's source. Three of its nine claims are refused and named where they would have
 * landed: the composite health pill, the invented `Sensitivity` and `Status` columns, and the
 * call-site telemetry figures this route never computes (see `SelectedCallSite` below).
 *
 * ## What each region is, and why it is where it is
 *
 * **Left — the operation's own facts, and the two ways to narrow the table.** The facts used to sit
 * in a 22rem rail beside an empty half-screen; here they are the pane's subject. Their scope is the
 * whole workspace and the table's is the window, which is the disagreement the six deleted
 * paragraphs existed to explain — it is now one visible sentence with the argument behind the ⓘ.
 *
 * **Centre, dominant — the call sites.** Nine columns become five. The four that left are not
 * hidden and not hideable: `call-site-columns.ts` partitions them, and every one is rendered in
 * full for the selected row, which is when a reader actually wants them. B91's ruling that
 * `args_keys`, `response_fields_read` and `loop_depth` are screen gaps rather than payload to
 * retire is honoured — all three are still on screen.
 *
 * **The rung stays first and stays monochrome.** `vendor-findings-table.tsx` carries the argument
 * the honesty guard pins by its "sideways scroll" fragment: the call site is the widest cell, so a
 * rung column further right is a column the layout does not protect. It is not one of the four that
 * moved, and it is not a column-visibility option.
 *
 * **Centre, below — vendor changes**, the one region the reference has no counterpart for. A
 * vertical split rather than a tab pair: tabs would cost no height and hide half the question the
 * screen exists to answer. Recorded as a reversible ruling; the fallback if the split ever starves
 * the call-site table is a chip-tab pair labelled with both counts.
 *
 * **Right — the selected call site**, replacing `BindingDrawer` (deleted with it). The pane stays
 * mounted with nothing selected: a pane that appears and disappears reflows the table under the
 * reader's cursor. `binding-selection.ts` and its URL parameter are unchanged, so Back still closes
 * a selection and a deep link to a call site this page does not hold still opens something saying
 * so.
 *
 * ## Two corrections this rebuild makes rather than reskins
 *
 * **The repository facet was a dead control.** `M14-W386` moved the scope into the route, and the
 * chips went on writing a `repo_id` search parameter that nothing reads — pressing one changed the
 * URL and no rows. They are links to the same operation under that repository now, which is what
 * choosing a repository means once the route is the scope.
 *
 * **The rung claim keeps all three of its branches.** `RungNote`'s three paragraphs said different
 * things — every row rests on `static`, no row carries a rung because a filter excluded them all,
 * no row carries one because none is bound. All three survive as the *value* of the Binding rung
 * fact, in the fewest honest words, with the argument behind its ⓘ.
 */

import { useState, type ReactNode } from "react"
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react"
import { Link, useParams } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useBindingSurface } from "@/api/queries"
import type { BindingSurfaceResponse } from "@/api/types"
import { CodeSnippet, absentSnippetReason } from "@/components/code-snippet"
import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { DetailClose } from "@/components/detail-layout"
import { type Fact, FactList } from "@/components/fact-list"
import { PrefixFilter } from "@/components/filters"
import { InfoHint } from "@/components/info-hint"
import { PageControls } from "@/components/page-controls"
import { PanelPane } from "@/components/pane"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { ChangeKindTag, SeverityTag } from "@/components/tag"
import {
  BINDING_KEY,
  bindingKey,
  selectBinding,
  type BindingSelection,
} from "@/features/bindings/binding-selection"
import {
  CALL_SITE_TABLE_COLUMNS,
  nextSortDirection,
  sortCallSites,
  type SortState,
} from "@/features/bindings/call-site-columns"
import { joinOrAbsent } from "@/features/bindings/call-site-fields"
import { Pending } from "@/features/findings/pending"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp, orAbsent, pathAfter } from "@/lib/format"
import { bindingSurfaceHref } from "@/lib/hrefs"
import { describeRecordWindow } from "@/lib/record-window"
import { chipSurface } from "@/lib/selectable-surface"
import { useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"
import { cn } from "@/lib/utils"

const CALL_SITES_OFFSET_KEY = "call_sites_offset"
const CHANGES_OFFSET_KEY = "changes_offset"
const PATH_PREFIX_KEY = "path_prefix"

/** The path filter clears the call-site page position and leaves the changes page alone: the two
 * sets page independently, and narrowing one says nothing about where the other is. */
const CALL_SITE_RESETS = [CALL_SITES_OFFSET_KEY]

const QUESTION = "What calls this operation, on what evidence, and what the vendor changed about it."

/**
 * Call sites bound to this operation across every repository, before any filter on this page.
 *
 * `repositories` is the facet's own scope rather than the table's: it is the list of repositories
 * the operation is called from, so it stays the same whichever one the reader is in. That makes it
 * the right denominator for a stated fact about the operation and the wrong one for the table,
 * which is why the figure in the centre pane is a different figure and each says which.
 */
function boundCallSites(data: BindingSurfaceResponse): number {
  return data.repositories.reduce((sum, repo) => sum + repo.call_site_count, 0)
}

/** A recorded figure in the register the reference gives its count chips. */
function Chip({ children }: { children: ReactNode }) {
  return (
    <span className="furniture rounded-control border border-line px-field py-0.5 font-mono text-meta text-ink">
      {children}
    </span>
  )
}

/**
 * The page-level rung, as the value of a fact rather than as three paragraphs.
 *
 * `binding_surface` hardcodes every call-site row to `static` — a call site is what the static
 * index found, so a row built from it alone can honestly carry no other rung. The two empty
 * branches are different claims and neither is the badge: under a filter that matched nothing the
 * absence is a fact about the filter, and with nothing bound it is a fact about the index.
 */
function rungFact(data: BindingSurfaceResponse | null, filtered: boolean): ReactNode {
  const hint = (
    <InfoHint label="About the binding rung">
      The rung records how a binding was established, never how much to trust it. Every row here is{" "}
      <code className="font-mono">static</code> because this route reads what the index found by
      reading the source — never a resolution or a correlation step. A stronger rung for the same
      operation, traffic Sync has actually observed calling it, is a separate kind of evidence on the
      repository&rsquo;s coverage page and is never blended into these rows.
    </InfoHint>
  )
  if (data === null) return hint
  if (data.call_sites.total === 0 && filtered) {
    return (
      <span className="flex items-center gap-field">
        <Absent>none under this filter</Absent>
        {hint}
      </span>
    )
  }
  if (data.call_sites.total === 0) {
    return (
      <span className="flex items-center gap-field">
        <Absent>none bound, so none carried</Absent>
        {hint}
      </span>
    )
  }
  return (
    <span className="flex items-center gap-field">
      <RungBadge rung="static" />
      {hint}
    </span>
  )
}

/**
 * The operation's own facts, label left and value right.
 *
 * Three states per counted fact and they are three different claims. `<Pending>` says the query is
 * in flight. `<Absent>` says the query failed, which is not a count of zero, and the error state
 * beside it names what failed. A number says the number.
 */
function operationFacts(
  vendorId: string,
  operationId: string,
  data: BindingSurfaceResponse | null,
  failed: boolean,
  filtered: boolean
): Fact[] {
  const counted = (value: number) => {
    if (data !== null) return value.toLocaleString()
    return failed ? <Absent>the API did not answer</Absent> : <Pending />
  }

  return [
    { label: "Vendor", value: <span className="font-mono break-words">{vendorId}</span> },
    { label: "Operation", value: <span className="font-mono break-words">{operationId}</span> },
    { label: "Binding rung", value: rungFact(data, filtered) },
    { label: "Call sites bound", value: counted(data ? boundCallSites(data) : 0) },
    { label: "Repositories", value: counted(data ? data.repositories.length : 0) },
    { label: "Vendor changes", value: counted(data ? data.changes.total : 0) },
  ]
}

/**
 * Which repositories call this operation, with their counts, each a link to its own surface.
 *
 * **Not a filter, and that is a correction rather than a downgrade.** These were chips writing a
 * `repo_id` search parameter, which stopped being read the day `M14-W386` moved the scope into the
 * route: the control looked pressed and no row moved. The workspace is the route now, so choosing
 * a repository is going to that repository's binding surface — a real destination with a real
 * address, which is also what makes the choice shareable.
 *
 * There is no "every repository" option. The route requires a workspace, so a fleet-wide chip would
 * be an address that does not exist.
 */
function RepositoryFacet({
  data,
  repoId,
  vendorId,
  operationId,
}: {
  data: BindingSurfaceResponse
  repoId: string
  vendorId: string
  operationId: string
}) {
  if (data.repositories.length === 0) return null

  return (
    <div className="flex min-w-0 flex-col gap-row">
      <span className="furniture flex items-center gap-field text-meta text-ink-muted">
        Repository
        <InfoHint label="About the repository counts">
          Counted over every call site the index holds on this operation, with neither the workspace
          nor the path filter applied — an option list narrowed by the filter it sets collapses to
          whatever is already selected and leaves no way back to the rest. So these numbers and the
          figure on the call-site pane answer two different questions, and the one that moves with a
          filter is the one beside the table.
        </InfoHint>
      </span>
      <div className="flex flex-wrap items-center gap-row">
        {data.repositories.map((repo) => (
          <Link
            key={repo.repo_id}
            to={bindingSurfaceHref(repo.repo_id, vendorId, operationId)}
            // The current repository is marked by `aria-current` as well as by the surface step,
            // so the selection is readable without colour.
            aria-current={repo.repo_id === repoId ? "page" : undefined}
            className={cn(
              "inline-flex min-w-0 items-center gap-field rounded-control border px-field py-0.5 text-meta",
              chipSurface(repo.repo_id === repoId)
            )}
          >
            <span className="font-mono break-all">{repo.repo_id}</span>
            <span className="text-ink-muted">{repo.call_site_count.toLocaleString()}</span>
          </Link>
        ))}
      </div>
    </div>
  )
}

/**
 * Which kind of nothing the call-site table is showing.
 *
 * Three, and each is a different fact. Nothing bound at all is an answer about the index. A filter
 * that matched nothing is an answer about the filter, and the repository facet beside it proves the
 * operation is called from somewhere. A page position past the end of a narrowed set is an answer
 * about the URL: the table is not empty, the window is.
 */
function CallSitesEmptyState({
  data,
  repoId,
  pathPrefix,
  offset,
}: {
  data: BindingSurfaceResponse
  repoId: string
  pathPrefix: string | null
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
  if (pathPrefix !== null) {
    return (
      <EmptyState
        headline="No call site matches this filter."
        detail={
          `The API answered with an empty list for paths under ${pathPrefix}. ` +
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
      detail={`The API answered with an empty list scoped to ${repoId}. Either nothing in this workspace calls the operation, or this workspace has not been indexed at all — the index cannot tell the two apart.`}
      command="uv run sync index --repo <git-remote>"
    />
  )
}

/**
 * The right pane's body: the selected call site, or which nothing stands in its place.
 *
 * **The reference's `Call site telemetry` foot is refused whole.** `P95 latency 124ms`,
 * `Error rate (1h) 0.02%` and `Last observed …` are three figures this route never computes —
 * call-level telemetry lives in `features/telemetry` over `ObservedCallRow`, which this feature does
 * not own. The rate would also arrive with no denominator on screen, and a last-observed time reads
 * staleness as liveness. The slot is kept and filled with the call site's own indexed fields, which
 * is where the four columns that left the table land.
 *
 * The window itself is `CodeSnippet`, which renders only what the index captured — there is no
 * "show more" that could read past it. When there is none, `absentSnippetReason` says **which**
 * nothing: a deployment that withholds source, or a row written before capture existed.
 */
function SelectedCallSite({
  selection,
  data,
}: {
  selection: BindingSelection
  data: BindingSurfaceResponse
}) {
  if (selection.kind === "none") {
    return (
      <p className="text-body text-ink-muted">
        No call site is selected. Choosing one in the table shows the source window the index
        captured for it, and the four fields the table does not carry: repository, SDK version,
        argument keys and response fields read.
      </p>
    )
  }

  if (selection.kind === "unresolved") {
    return (
      <div className="flex flex-col gap-field">
        <p className="font-mono text-meta break-words">{selection.key}</p>
        <p className="text-body text-muted-foreground">
          A binding address names a call site by repository, path, line and column. This page holds{" "}
          {data.call_sites.items.length.toLocaleString()} call{" "}
          {data.call_sites.items.length === 1 ? "site" : "sites"} and none of them is that one —
          which could mean a filter excludes it, that it is on another page, or that the index holds
          no such call site at all. Nothing here can tell those apart, so none is picked: clear the
          filter and return to the first page, and if it is still not listed then this operation has
          no such binding.
        </p>
      </div>
    )
  }

  const site = selection.site

  return (
    <>
      <p className="font-mono text-meta break-all text-ink select-all">
        {site.path}:{site.line}:{site.col}
      </p>
      {typeof site.snippet === "string" && site.snippet_start_line != null ? (
        <CodeSnippet
          code={site.snippet}
          startLine={site.snippet_start_line}
          markLine={site.line}
          label={`Call site, ${site.path}:${site.line}`}
        />
      ) : (
        <p className="text-meta text-ink-muted">{absentSnippetReason(data.source_served)}</p>
      )}
      <FactList
        facts={[
          { label: "Repository", value: <span className="font-mono break-all">{site.repo_id}</span> },
          {
            label: "Symbol",
            value: (
              <span className="font-mono break-words">
                <Formatted value={orAbsent(site.symbol)} />
              </span>
            ),
          },
          {
            label: "SDK version",
            value: (
              <span className="font-mono">
                <Formatted value={orAbsent(site.sdk_version)} />
              </span>
            ),
          },
          {
            label: "Argument keys",
            value: (
              <span className="font-mono break-words">
                <Formatted value={joinOrAbsent(site.args_keys)} />
              </span>
            ),
          },
          {
            label: "Response fields read",
            value: (
              <span className="font-mono break-words">
                <Formatted value={joinOrAbsent(site.response_fields_read)} />
              </span>
            ),
          },
          { label: "Loop depth", value: <span className="font-mono">{site.loop_depth}</span> },
          {
            label: "Indexed at",
            value: (
              <span className="font-mono">
                <Formatted value={formatTimestamp(site.indexed_at)} />
              </span>
            ),
          },
        ]}
      />
    </>
  )
}

/** A column heading that states its type and, where ordering it means something, sorts it. */
function CallSiteHead({
  column,
  sort,
  onSort,
}: {
  column: (typeof CALL_SITE_TABLE_COLUMNS)[number]
  sort: SortState | null
  onSort: (next: (current: SortState | null) => SortState | null) => void
}) {
  const type = (
    <span className="text-muted-foreground text-meta font-normal">{column.type}</span>
  )
  if (!column.sortBy) {
    return (
      <TableHead>
        <span className="flex items-baseline gap-field">
          <span>{column.label}</span>
          {type}
        </span>
      </TableHead>
    )
  }
  const direction = sort?.key === column.key ? sort.direction : null
  // The direction is drawn, not implied by the rows moving: a reader arriving at a sorted table
  // has to see which column did it without pressing anything.
  const Glyph = direction === "asc" ? ArrowUp : direction === "desc" ? ArrowDown : ChevronsUpDown
  return (
    <TableHead
      aria-sort={
        direction === null ? "none" : direction === "asc" ? "ascending" : "descending"
      }
    >
      <button
        type="button"
        onClick={() => onSort((current) => nextSortDirection(current, column.key))}
        className="flex items-baseline gap-field text-left"
        aria-label={`Sort by ${column.label}`}
      >
        <span>{column.label}</span>
        {type}
        <Glyph aria-hidden="true" className="size-3 shrink-0 text-ink-muted" />
      </button>
    </TableHead>
  )
}

function BindingSurfaceDetail({
  vendorId,
  operationId,
  repoId,
}: {
  vendorId: string
  operationId: string
  repoId: string
}) {
  const [callSitesOffset, setCallSitesOffset] = useOffsetParam(CALL_SITES_OFFSET_KEY)
  const [changesOffset, setChangesOffset] = useOffsetParam(CHANGES_OFFSET_KEY)
  const [pathPrefix, setPathPrefix] = useFilterParam(PATH_PREFIX_KEY, CALL_SITE_RESETS)
  // No `resets`, unlike the filter beside it. Opening a detail does not change which rows exist,
  // so the page position measured against them is still the right one.
  const [openBinding, setBinding] = useFilterParam(BINDING_KEY)

  /**
   * Which column orders this page of call sites, if any.
   *
   * Component state rather than a search parameter, and that is a narrower claim than the filter
   * beside it: a filter changes *which* rows the server returns, so it belongs in an address a
   * reader can send to somebody. A sort reorders the page already on screen and does not reach the
   * server, so putting it in the URL would promise that a shared link reproduces an ordering across
   * a page boundary, which it would not.
   */
  const [sort, setSort] = useState<SortState | null>(null)
  const query = useBindingSurface(vendorId, operationId, {
    repoId,
    pathPrefix: pathPrefix ?? undefined,
    callSitesLimit: DEFAULT_LIMIT,
    callSitesOffset,
    changesLimit: DEFAULT_LIMIT,
    changesOffset,
  })

  /**
   * The chassis band counts the call sites and nothing else, though two sets page on this screen.
   *
   * `StatusBand` renders one pager, and the call-site table is the set this screen exists to
   * window — 2,500 rows against a handful of vendor changes. The changes keep their own pager
   * pinned under their own table, where it sits beside the rows it moves.
   *
   * Every branch of the one query is answered: a records segment counts nothing until the payload
   * is here, so a pending or failed read says which silence it is rather than reporting zero.
   */
  const status: StatusSegment[] = query.isSuccess
    ? [
        {
          kind: "records",
          label: "Call sites",
          text: describeRecordWindow(
            callSitesOffset,
            query.data.call_sites.items.length,
            { count: query.data.call_sites.total, boundReached: false },
            pathPrefix === null ? `call site in ${repoId}` : "call site under this path",
            pathPrefix === null ? `call sites in ${repoId}` : "call sites under this path"
          ),
          paging: {
            offset: callSitesOffset,
            limit: DEFAULT_LIMIT,
            shown: query.data.call_sites.items.length,
            total: query.data.call_sites.total,
            nextOffset: query.data.call_sites.next_offset,
            busy: query.isFetching,
            onOffsetChange: setCallSitesOffset,
          },
        },
      ]
    : [
        {
          kind: "none",
          why: query.isError
            ? `the bindings for ${vendorId}/${operationId} did not answer`
            : `asking for the bindings on ${vendorId}/${operationId}`,
        },
      ]

  const selection = query.isSuccess
    ? selectBinding(openBinding, query.data.call_sites.items)
    : ({ kind: "none" } as BindingSelection)
  const selectedLine = selection.kind === "resolved" ? selection.site.line : null

  return (
    // No `controls` band. Both narrowings live in the left pane, where they sit beside the counts
    // they change; a full-width band above four panes would spend ~50px of a locked column saying
    // what the pane already says.
    <ScreenFrame layout="locked" status={status} subtitle={QUESTION}>
      {/* Three tracks at `xl`, one column below it. The flanks are fixed and the centre takes the
          slack, so the table never loses width to a pane that has nothing more to show. Below `xl`
          the three stack into equal thirds and each still scrolls its own body — a locked screen
          stamps `data-screen="locked"` at every width, so a page that expected to scroll would be
          clipped instead. */}
      <div className="grid min-h-0 min-w-0 flex-1 grid-rows-3 gap-section xl:grid-cols-[15rem_minmax(0,1fr)_20rem] xl:grid-rows-1 2xl:grid-cols-[15rem_minmax(0,1fr)_28rem]">
        <PanelPane
          label="This operation"
          bodyClassName="flex min-w-0 flex-col gap-section p-section"
        >
          <FactList
            facts={operationFacts(
              vendorId,
              operationId,
              query.isSuccess ? query.data : null,
              query.isError,
              pathPrefix !== null
            )}
          />
          {/* The scope claim, visible. The argument for why it disagrees with the figure on the
              call-site pane is behind the facet's ⓘ. */}
          <p className="text-meta text-ink-muted">
            Counted across every repository, before the narrowings below.
          </p>

          {query.isSuccess && (
            <RepositoryFacet
              data={query.data}
              repoId={repoId}
              vendorId={vendorId}
              operationId={operationId}
            />
          )}

          <PrefixFilter
            legend="Call site path"
            value={pathPrefix}
            onSubmit={setPathPrefix}
            placeholder="src/billing/"
            note="Matched as a prefix, never as a substring."
            hint={
              <InfoHint label="About the path filter">
                It narrows the call sites only. A vendor change has no position in your codebase, so
                the changes table is untouched by it — and the repository counts above are the option
                list this filter is set from, so they are counted without it.
              </InfoHint>
            }
          />
        </PanelPane>

        {/* The centre column is a vertical split: the call sites dominant, the vendor changes a
            shorter sibling with its own scroll and its own pager. Typical cardinality is 2,500
            against a handful, which is why the split is 2:1 rather than even. */}
        <div className="grid min-h-0 min-w-0 grid-rows-[minmax(0,2fr)_minmax(0,1fr)] gap-section">
          <PanelPane
            scroll={false}
            label="Call sites"
            hint={
              <InfoHint label="About the call-site window">
                Every place this workspace&rsquo;s indexed source calls the operation. The figure
                beside this label is the window on screen against the set the filters admit; the
                figures in the pane on the left are counted across every repository and do not move
                when a filter does. The chassis band under the page spells the same window in words.
              </InfoHint>
            }
            actions={
              query.isSuccess ? (
                <Chip>
                  {query.data.call_sites.items.length.toLocaleString()} of{" "}
                  {query.data.call_sites.total.toLocaleString()}
                </Chip>
              ) : undefined
            }
            footer={
              query.isSuccess && query.data.call_sites_common_directory ? (
                <span className="min-w-0 truncate">
                  Paths shown under{" "}
                  <code className="font-mono text-ink">
                    {query.data.call_sites_common_directory}
                  </code>{" "}
                  — the prefix and the cell together are the whole path, nothing is shortened away.
                </span>
              ) : undefined
            }
          >
            {query.isPending && (
              <div className="min-h-0 flex-1 overflow-auto p-section">
                <LoadingState what={`bindings for ${vendorId}/${operationId}`} />
              </div>
            )}
            {query.isError && (
              <div className="min-h-0 flex-1 overflow-auto p-section">
                <ErrorState
                  error={query.error}
                  what={`bindings for ${vendorId}/${operationId}`}
                  onRetry={() => void query.refetch()}
                />
              </div>
            )}
            {query.isSuccess &&
              (query.data.call_sites.items.length === 0 ? (
                <div className="min-h-0 flex-1 overflow-auto p-section">
                  <CallSitesEmptyState
                    data={query.data}
                    repoId={repoId}
                    pathPrefix={pathPrefix}
                    offset={callSitesOffset}
                  />
                </div>
              ) : (
                // The frame is what makes the head stick: it moves the scroll onto the vendored
                // table container, which is the element a `sticky` thead has to sit inside.
                // Borderless because the pane already draws the border.
                <TableFrame fill className="rounded-none border-0">
                  <Table>
                    <TableHeader sticky>
                      <TableRow>
                        {CALL_SITE_TABLE_COLUMNS.map((column) => (
                          <CallSiteHead
                            key={column.key}
                            column={column}
                            sort={sort}
                            onSort={setSort}
                          />
                        ))}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sortCallSites(query.data.call_sites.items, sort).map((site) => {
                        const selected = openBinding === bindingKey(site)
                        return (
                          <TableRow
                            key={bindingKey(site)}
                            data-state={selected ? "selected" : undefined}
                          >
                            <TableCell>
                              <RungBadge rung={site.binding_rung} />
                            </TableCell>
                            <TableCell className="font-mono">
                              {/* A button rather than a `Link`: the selection is a search parameter
                                  on this same address, so a right-click "open in new tab" would
                                  land on a screen with no page position and no filter — which is
                                  not where the reader is looking. `useFilterParam` still pushes the
                                  history entry, so Back closes it.

                                  The marker is the second channel beside the row's surface step, so
                                  the selection is legible without colour. */}
                              <button
                                type="button"
                                onClick={() => setBinding(selected ? null : bindingKey(site))}
                                aria-pressed={selected}
                                className="text-left underline underline-offset-2 break-words"
                                aria-label={`Binding at ${site.path} line ${site.line} in ${site.repo_id}`}
                              >
                                <span aria-hidden="true">{selected ? "▸ " : ""}</span>
                                {pathAfter(query.data.call_sites_common_directory, site.path)}:
                                {site.line}:{site.col}
                              </button>
                            </TableCell>
                            <TableCell className="font-mono">
                              <Formatted value={orAbsent(site.symbol)} />
                            </TableCell>
                            <TableCell className="font-mono">{site.loop_depth}</TableCell>
                            <TableCell className="font-mono text-meta">
                              <Formatted value={formatTimestamp(site.indexed_at)} />
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </TableFrame>
              ))}
          </PanelPane>

          <PanelPane
            scroll={false}
            label="Vendor changes"
            hint={
              <InfoHint label="About vendor changes">
                What the vendor changed about this operation, whether or not a call site above is
                affected. It is evidence about the vendor rather than about your codebase, so nothing
                in it was read out of your source and no rung applies. Whether a call site above is
                affected by one is a detector&rsquo;s answer, and a detector&rsquo;s answer is a
                finding rather than a row here.
              </InfoHint>
            }
            actions={
              <span className="text-meta text-ink-muted">Vendor evidence — carries no rung.</span>
            }
            footer={
              query.isSuccess && query.data.changes.total > 0 ? (
                <span className="ml-auto">
                  <PageControls
                    offset={changesOffset}
                    limit={DEFAULT_LIMIT}
                    shown={query.data.changes.items.length}
                    total={query.data.changes.total}
                    nextOffset={query.data.changes.next_offset}
                    busy={query.isFetching}
                    onOffsetChange={setChangesOffset}
                  />
                </span>
              ) : undefined
            }
          >
            {query.isSuccess ? (
              query.data.changes.total === 0 ? (
                <div className="min-h-0 flex-1 overflow-auto p-section">
                  <EmptyState
                    headline="The vendor has never changed this operation."
                    detail="The API answered with an empty list. No ingested feed names a change against this operation — that is an answer, not a failure."
                    command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
                  />
                </div>
              ) : (
                <TableFrame fill className="rounded-none border-0">
                  <Table>
                    <TableHeader sticky>
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
                          <TableCell>
                            <ChangeKindTag kind={change.kind} />
                          </TableCell>
                          <TableCell>
                            <SeverityTag severity={change.severity} />
                          </TableCell>
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
                </TableFrame>
              )
            ) : (
              <div className="min-h-0 flex-1 overflow-auto p-section">
                <p className="text-body text-ink-muted">
                  {query.isError
                    ? "The read that carries the vendor changes did not answer, so nothing here is a count of zero."
                    : "Still asking for this operation's vendor changes."}
                </p>
              </div>
            )}
          </PanelPane>
        </div>

        {/* Mounted whether or not anything is selected: a pane that appears and disappears reflows
            the table under the reader's cursor, and an address naming a call site this page does
            not hold has to open something that says so. */}
        <PanelPane
          label={selectedLine === null ? "Selected call site" : `Selected call site — line ${selectedLine}`}
          actions={
            selection.kind === "none" ? undefined : (
              <DetailClose onClose={() => setBinding(null)} />
            )
          }
          bodyClassName="flex min-w-0 flex-col gap-section p-section"
        >
          {query.isSuccess ? (
            <SelectedCallSite selection={selection} data={query.data} />
          ) : (
            <p className="text-body text-ink-muted">
              {query.isError
                ? "The call sites did not answer, so there is nothing here to select from."
                : "Still asking for this operation's call sites."}
            </p>
          )}
        </PanelPane>
      </div>
    </ScreenFrame>
  )
}

export function BindingSurfacePage() {
  const { vendorId, operationId, repoId } = useParams<{
    vendorId: string
    operationId: string
    repoId: string
  }>()
  if (vendorId === undefined || operationId === undefined || repoId === undefined) {
    return <UnknownRoute />
  }
  // **The route is the scope**, and it used to be a query string: this read
  // `searchParams.get("repo_id")` while the route carries `:repoId`, so an address naming a
  // workspace could still render a fleet-wide claim -- the screen contradicting its own URL.
  return (
    <BindingSurfaceDetail vendorId={vendorId} operationId={operationId} repoId={repoId} />
  )
}
