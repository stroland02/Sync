/**
 * Errors and incidents for one vendor: every call site an open finding touches.
 *
 * The rung column is per row and is the one to weigh a finding by. The envelope's rung
 * below the table is a property of the page and goes null the moment the page mixes rungs,
 * which is exactly when the per-row column stops being redundant.
 *
 * The operation column links into the Binding surface level. `repoId`, when the caller has
 * one, rides along so the surface that opens is scoped to it.
 *
 * **The call site is the way into the finding, and there is no finding-id column.** Measured at
 * `--scale 10000`: a 32-character id in a 164px column wrapped to three lines, and the call-site
 * path beside it wrapped to four, which is what put a body row at 76px and eleven rows above the
 * fold on a two-and-a-half-thousand-row table. An opaque hash is not something a reader reads —
 * it is something they click — so the click moved to the cell that names the row in the operator's
 * own terms, and the column it used to occupy went to the path. `break-words` stays on that path:
 * it is what keeps the rung column on screen at 1280px, because a customer's 200-character path
 * grows a row taller instead of pushing provenance out of the viewport. The id itself is not lost;
 * it is the heading of the page the link opens, and it rides the link's accessible name so a
 * screen reader announces which finding a path leads to.
 *
 * `repoId` also narrows the query itself. It is not a hint the table decorates a link with: a
 * page fetched for the fleet and rendered under a repository's name is a false claim about that
 * repository, so the same value reaches `GET /api/vendors/{vendor_id}` as `repo_id` and the
 * answer comes back naming the scope it was computed in.
 *
 * Two filters sit *inside* that scope rather than beside it. A customer repository puts
 * thousands of rows behind this table where the fixture puts five, and the two questions an
 * operator arrives with — which severity, and which part of the tree — are both columns the
 * graph already stores. Every one of the three narrowings is a SQL predicate on the same query:
 * `sync.dashboard.graph_views.vendor_findings` applies them ahead of its own `LIMIT`, so the
 * denominator under a filtered page is the filtered denominator, and choosing a severity inside
 * a selected repository narrows that repository rather than replacing it with the fleet.
 *
 * **The severity chips are counted over the scope, not over the page.** They are the option list
 * the filter is set from — the same repository and the same vendor, without the severity or the
 * path currently chosen, because an option list narrowed by the filter it sets collapses to
 * whatever is already selected. So they disagree with the range under the table whenever a
 * filter is on, and the screen says which is which rather than leaving a reader to assume.
 *
 * **`severity_total` is the panel's figure, and `total` deliberately is not.** M7-W174 put this
 * level on the substrate, and the two counts in this envelope answer different questions: `total`
 * is what the current filter matched and is already asserted by the range in the footer bar, while
 * `severity_total` is what this vendor has open in this scope before any narrowing. A headline that
 * moved every time a chip was clicked would be the panel restating the footer rather than naming
 * its own grain. `docs/superpowers/briefs/2026-08-07-substrate-api-services.md` carries the mapping
 * this port was gated on, and it is what to read before porting a level, not this docstring.
 *
 * **M7-W195 moved the three controls out of this panel and into the page's own control bar.** Every
 * paragraph above still holds — what each narrows, what the chips are counted over, why they
 * disagree with the range under the table. Only their position changed, and the gap report measured
 * why: they sat inside a card body under a heading, a figure and a caption, on a screen whose
 * control bar did not exist. `VendorFindingsControls` below carries why the filter state is one
 * shared hook rather than two derivations.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorFindings } from "@/api/queries"
import type { FindingOrder, VendorFindingsPage } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { ActiveFilters, FacetChips, PrefixFilter, type FacetOption } from "@/components/filters"
import { MetricPanel } from "@/components/metric-panel"
import { OrderChoice } from "@/components/ordering"
import { ProvenanceStrip, RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import { ControlBar } from "@/layouts/control-bar"
import { FooterBar } from "@/layouts/footer-bar"
import { orAbsent } from "@/lib/format"
import { useClearFilters, useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const OFFSET_KEY = "findings_offset"
const SEVERITY_KEY = "severity"
const PATH_KEY = "path"
const ORDER_KEY = "order"

/** Both filters clear the page position: an offset measured against the old set means nothing
 * against the new one, and a page past the end of a narrowed set is an empty table that reads
 * as "nothing matches".
 *
 * The ordering clears it too, for a related reason that is not the same one. A filter changes
 * which rows exist; an ordering changes which rows a given offset names. Offset 250 in one
 * ordering is fifty different findings in the other, so holding the position across a re-order
 * would move the window under the reader while the count under it stayed still. */
const RESETS = [OFFSET_KEY]

/**
 * The three narrowings this level offers, read from the URL, with what is currently on.
 *
 * **One definition, two consumers, and that is why it exists.** M7-W195 moved the controls out of
 * this panel's body and into the page's own control bar, which put the bar that *sets* these
 * parameters and the empty state that has to *explain* them in two components. Deriving
 * `activeFilters` twice would be one fact written twice — the two lists would agree today and
 * silently disagree the first time a fourth narrowing is added to one of them.
 *
 * The query is not held here. `useVendorFindings` is keyed on the vendor, the scope and all four
 * narrowings, so the bar and the table asking the same question share one fetch rather than
 * issuing two.
 */
function useVendorFindingFilters() {
  const [severity, setSeverity] = useFilterParam(SEVERITY_KEY, RESETS)
  const [pathPrefix, setPathPrefix] = useFilterParam(PATH_KEY, RESETS)
  // Sent as whatever the URL holds, including a value the API does not have. The API resolves it
  // and echoes the ordering it applied, and the control renders *that* — so a hand-edited URL
  // cannot leave the screen naming an arrangement the rows are not in.
  const [order, setOrder] = useFilterParam(ORDER_KEY, RESETS)

  // `repo_id` is deliberately not among the keys this clears. It is the scope the level above
  // selected, not a filter this table offers, and a control labelled "clear all filters" that
  // silently widened the page to the fleet would undo a choice made on another screen.
  const clearAll = useClearFilters([SEVERITY_KEY, PATH_KEY], RESETS)

  const activeFilters = [
    ...(severity === null ? [] : [{ label: "severity", value: severity }]),
    ...(pathPrefix === null ? [] : [{ label: "path", value: pathPrefix }]),
  ]

  return { severity, setSeverity, pathPrefix, setPathPrefix, order, setOrder, activeFilters, clearAll }
}

function bindingSurfaceHref(vendorId: string, operation: string, repoId: string | null): string {
  const path = `/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operation)}`
  return repoId === null ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`
}

function severityOptions(page: VendorFindingsPage): FacetOption[] {
  return Object.entries(page.severity_counts)
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
}

/**
 * Which kind of nothing this is.
 *
 * Three, and they are three different facts about the graph. A dataset with no open findings is
 * an answer about the codebase. A filter that matched nothing is an answer about the filter. A
 * page position past the end of a narrowed set is an answer about the URL — the table is not
 * empty, the window is. Rendering one sentence for all three is how a console tells an operator
 * their code is clean when what actually happened is that they typed a directory that does not
 * exist.
 */
function FindingsEmptyState({
  vendorId,
  repoId,
  page,
  filters,
  offset,
}: {
  vendorId: string
  repoId: string | null
  page: VendorFindingsPage
  filters: { label: string; value: string }[]
  offset: number
}) {
  // Every sentence below names the repository scope it found nothing in, or says it looked
  // across the fleet. The scope and the filters are different reasons for an empty table, and a
  // reader who cannot tell which is which cannot act on either.
  const scope =
    repoId === null ? "any repository the index has seen" : repoId

  if (page.total > 0) {
    return (
      <EmptyState
        headline={`This page is past the end of the ${page.total.toLocaleString()} findings that match.`}
        detail={`The API answered with an empty page at offset ${offset}. There are findings here — this window is not over them. Go back to the first page to see them.`}
      />
    )
  }
  if (filters.length > 0) {
    return (
      <EmptyState
        headline={`No open finding for ${vendorId} in ${scope} matches this filter.`}
        detail={
          `The API answered with an empty page for ${filters.map((f) => `${f.label} ${f.value}`).join(" and ")}. ` +
          `${vendorId} holds ${page.severity_total.toLocaleString()} open ` +
          `${page.severity_total === 1 ? "finding" : "findings"} in ${scope}, so this is what the ` +
          "filter excluded and not what the codebase is missing — clear it to see the rest."
        }
      />
    )
  }
  return (
    <EmptyState
      headline={
        repoId === null
          ? `No open findings for ${vendorId} in any repository the index has seen.`
          : `No open findings for ${vendorId} in ${repoId}.`
      }
      detail="The API answered with an empty page. Either nothing in this codebase calls that vendor, or nothing that does is currently at risk."
    />
  )
}

/**
 * The one question the bar and the table both ask, so they cannot ask two.
 *
 * Every narrowing is in the query key, which is what makes calling this in two components one
 * fetch rather than two.
 */
function useFindingsPage(
  vendorId: string,
  repoId: string | null,
  filters: ReturnType<typeof useVendorFindingFilters>,
  offset: number,
) {
  return useVendorFindings(vendorId, {
    limit: DEFAULT_LIMIT,
    offset,
    repoId: repoId ?? undefined,
    severity: filters.severity ?? undefined,
    path: filters.pathPrefix ?? undefined,
    order: (filters.order ?? undefined) as FindingOrder | undefined,
  })
}

/**
 * The three narrowings, in the page's own control bar rather than in a card body.
 *
 * `reports/2026-08-07-console-fidelity-gaps.md` Surface 3 row 3 measured where these used to sit:
 * inside `VendorFindingsCard`'s body at `y=469-585`, under a panel heading, a figure and a caption,
 * on a screen whose control bar did not exist. They set `?severity`, `?path` and `?order`, all
 * three of which reach `GET /api/vendors/{id}` and narrow the query rather than the rows already
 * fetched.
 *
 * **Nothing renders until the payload lands, and that is not a loading state.** The severity chips
 * are built from `severity_counts` and the ordering control renders the ordering the API says it
 * applied, so a bar drawn before the answer arrives would either be empty or be guessing. The panel
 * below carries `LoadingState`, which is the sentence that says a query is in flight; a second
 * marker here would be the same fact twice.
 */
export function VendorFindingsControls({
  vendorId,
  repoId = null,
}: {
  vendorId: string
  repoId?: string | null
}) {
  const [offset] = useOffsetParam(OFFSET_KEY)
  const filters = useVendorFindingFilters()
  const query = useFindingsPage(vendorId, repoId, filters, offset)

  if (!query.isSuccess) return null
  const page = query.data

  return (
    <div className="flex flex-col gap-section">
      <ControlBar>
        <FacetChips
          legend="Severity"
          options={severityOptions(page)}
          selected={filters.severity}
          onSelect={filters.setSeverity}
          allLabel="Every severity"
          countScope={`Counted across all ${page.severity_total.toLocaleString()} open findings for ${vendorId} in ${repoId === null ? "any repository the index has seen" : repoId}, not across the page below — these are the choices available, so they stay the same whichever one is selected.`}
        />
        <PrefixFilter
          legend="Call site path"
          value={filters.pathPrefix}
          onSubmit={filters.setPathPrefix}
          placeholder="src/billing/"
          note="Matched as a prefix of the call site's path, never as a substring: src/billing reaches src/billing/charge.ts and not lib/src/billing.ts."
        />
        <OrderChoice
          legend="Order"
          applied={page.order}
          severityOrder={page.severity_order}
          onSelect={filters.setOrder}
        />
      </ControlBar>
      <ActiveFilters filters={filters.activeFilters} onClear={filters.clearAll} />
      {/* What these narrow, said where they are set. This screen carries two tables and these
          three reach one of them: `whats_changed` takes none of these parameters, because what a
          vendor published is a fact about the vendor and has no severity in your codebase and no
          path in it either. A bar above two panels that did not say which one it moves would be
          claiming the wider scope by position. */}
      <p className="max-w-prose text-meta text-muted-foreground">
        All three narrow the errors and incidents table alone. The vendor changes below it are not
        narrowed by any of them.
      </p>
    </div>
  )
}

export function VendorFindingsCard({
  vendorId,
  repoId = null,
}: {
  vendorId: string
  repoId?: string | null
}) {
  const [offset, setOffset] = useOffsetParam(OFFSET_KEY)
  const filters = useVendorFindingFilters()
  const query = useFindingsPage(vendorId, repoId, filters, offset)
  const activeFilters = filters.activeFilters

  if (query.isPending) return <LoadingState what={`open findings for ${vendorId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`open findings for ${vendorId}`} onRetry={() => void query.refetch()} />
  }

  const page = query.data

  return (
    <MetricPanel
      label="Errors and incidents"
      metric={{
        value: page.severity_total.toLocaleString(),
        unit: `open ${page.severity_total === 1 ? "finding" : "findings"}${
          repoId === null ? " across every repository the index has seen" : ` in ${repoId}`
        }`,
      }}
      caption={
        <p className="max-w-prose">
          Call sites that an open finding touches
          {repoId === null ? (
            <>
              , in every repository the index has seen — this table is not scoped to one
              codebase, because nothing selected one on the way here
            </>
          ) : (
            <>
              {" "}
              in <span className="font-mono">{repoId}</span>, and in no other repository
            </>
          )}
          . The rung on each row says how the system knows the site is bound to the operation.
        </p>
      }
    >
      {page.items.length === 0 ? (
        <FindingsEmptyState
          vendorId={vendorId}
          repoId={repoId}
          page={page}
          filters={activeFilters}
          offset={offset}
        />
      ) : (
        <>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Severity</TableHead>
                {/* Rung sits ahead of the call site so it stays on screen at 1280px without a
                    sideways scroll: the call site is the widest cell in this table — a path
                    from a customer repository — and no fixture here is long enough to prove
                    that on its own. */}
                <TableHead>Rung</TableHead>
                <TableHead>Call site</TableHead>
                <TableHead>Symbol</TableHead>
                <TableHead>Operation</TableHead>
                <TableHead>Change kind</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((row) => (
                <TableRow key={row.finding_id}>
                  <TableCell>{row.severity}</TableCell>
                  <TableCell>
                    <RungBadge rung={row.binding_source} />
                  </TableCell>
                  <TableCell className="font-mono">
                    <Link
                      to={`/findings/${encodeURIComponent(row.finding_id)}`}
                      className="underline underline-offset-2"
                      aria-label={`Finding ${row.finding_id} at ${row.file} line ${row.line}`}
                    >
                      {row.file}:{row.line}
                    </Link>
                  </TableCell>
                  <TableCell className="font-mono">
                    <Formatted value={orAbsent(row.symbol)} />
                  </TableCell>
                  <TableCell className="font-mono">
                    {row.operation ? (
                      <Link
                        to={bindingSurfaceHref(vendorId, row.operation, repoId)}
                        className="underline underline-offset-2"
                      >
                        {row.operation}
                      </Link>
                    ) : (
                      <Formatted value={orAbsent(row.operation)} />
                    )}
                  </TableCell>
                  <TableCell>
                    <Formatted value={orAbsent(row.change_kind)} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <p className="max-w-prose text-meta text-muted-foreground">
            Each call site opens its finding. The finding's full id is the heading of that page —
            this table shows the path instead, because an opaque 32-character hash cost three
            wrapped lines in every row and told a reader nothing they could read.
          </p>
          {/* The filtered-total caveat is what the footer bar's `left` slot exists for: it says
              what the count beside it is counted over, which is the one thing a range under a
              narrowed table cannot say for itself. */}
          <FooterBar
            offset={offset}
            limit={DEFAULT_LIMIT}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            busy={query.isFetching}
            onOffsetChange={setOffset}
            left={
              activeFilters.length > 0 ? (
                <p className="max-w-prose text-body text-muted-foreground">
                  That range counts the findings this filter matched, not every finding{" "}
                  {vendorId} has in{" "}
                  {repoId === null ? "any repository the index has seen" : repoId}:{" "}
                  {page.severity_total.toLocaleString()} are open there in total.
                </p>
              ) : undefined
            }
          />
        </>
      )}
      <ProvenanceStrip
        provenance={page}
        bindingNullLabel={
          // An empty page has no rungs to disagree, so "mixed" would invent a conflict.
          page.items.length === 0
            ? "none: there is no finding here to attribute"
            : "mixed: the findings on this page do not all rest on one rung"
        }
      />
    </MetricPanel>
  )
}
