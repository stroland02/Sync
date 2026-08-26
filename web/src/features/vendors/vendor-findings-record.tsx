/**
 * Errors and incidents for one vendor: every call site an open finding touches.
 *
 * Rebuilt from `vendor-findings-table.tsx` (deleted) as a pane body. The panel, its caption, its
 * headline figure and its separate controls component are gone; the claims each carried are not.
 *
 * **The three narrowings sit inside the pane they narrow.** `M7-W195` moved them out to the page's
 * control bar, and that bar bought a full-width band above two tables with a sentence under it
 * explaining which one it moved. In a locked composition the two records are never on screen at
 * once, so position answers what the sentence used to: the controls are in the record's own head,
 * and the changes record has none.
 *
 * **The severity chips are counted over the scope, not over the page.** They are the option list the
 * filter is set from — the same repository and the same vendor, without the severity or the path
 * currently chosen, because an option list narrowed by the filter it sets collapses to whatever is
 * already selected. So they disagree with the range under the table whenever a filter is on, and
 * the screen says which is which rather than leaving a reader to assume.
 *
 * **`severity_total` and `total` answer different questions.** `total` is what the current filter
 * matched and is asserted by the range in the footer; `severity_total` is what this vendor has open
 * in this scope before any narrowing. The footer's `left` slot is where their disagreement is said.
 *
 * `repoId` narrows the query itself rather than decorating a link: a page fetched for the fleet and
 * rendered under a repository's name is a false claim about that repository.
 */

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorFindings } from "@/api/queries"
import type { FindingOrder, VendorFindingsPage } from "@/api/types"
import { ActiveFilters, FacetChips, PrefixFilter, type FacetOption } from "@/components/filters"
import { OrderChoice } from "@/components/ordering"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { TableFrame } from "@/components/data-table"
import { FindingsTable } from "@/features/findings/findings-table"
import { FooterBar } from "@/layouts/footer-bar"
import { useClearFilters, useFilterParam } from "@/lib/use-filter-param"
import { useOffsetParam } from "@/lib/use-offset-param"

const OFFSET_KEY = "findings_offset"
const SEVERITY_KEY = "severity"
const PATH_KEY = "path"
const ORDER_KEY = "order"

/**
 * Both filters clear the page position: an offset measured against the old set means nothing
 * against the new one, and a page past the end of a narrowed set is an empty table that reads as
 * "nothing matches".
 *
 * The ordering clears it too, for a related reason that is not the same one. A filter changes which
 * rows exist; an ordering changes which rows a given offset names. Offset 250 in one ordering is
 * fifty different findings in the other, so holding the position across a re-order would move the
 * window under the reader while the count under it stayed still.
 */
const RESETS = [OFFSET_KEY]

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

function severityOptions(page: VendorFindingsPage): FacetOption[] {
  return Object.entries(page.severity_counts)
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
}

/**
 * Which kind of nothing this is.
 *
 * Three, and they are three different facts about the graph. A dataset with no open findings is an
 * answer about the codebase. A filter that matched nothing is an answer about the filter. A page
 * position past the end of a narrowed set is an answer about the URL — the table is not empty, the
 * window is. Rendering one sentence for all three is how a console tells an operator their code is
 * clean when what actually happened is that they typed a directory that does not exist.
 */
function FindingsEmptyState({
  vendorId,
  repoId,
  page,
  filters,
  offset,
}: {
  vendorId: string
  repoId: string
  page: VendorFindingsPage
  filters: { label: string; value: string }[]
  offset: number
}) {
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
        headline={`No open finding for ${vendorId} in ${repoId} matches this filter.`}
        detail={
          `The API answered with an empty page for ${filters.map((f) => `${f.label} ${f.value}`).join(" and ")}. ` +
          `${vendorId} holds ${page.severity_total.toLocaleString()} open ` +
          `${page.severity_total === 1 ? "finding" : "findings"} in ${repoId}, so this is what the ` +
          "filter excluded and not what the codebase is missing — clear it to see the rest."
        }
      />
    )
  }
  return (
    <EmptyState
      headline={`No open findings for ${vendorId} in ${repoId}.`}
      detail="The API answered with an empty page. Either nothing in this codebase calls that vendor, or nothing that does is currently at risk."
    />
  )
}

export function VendorFindingsRecord({
  vendorId,
  repoId,
}: {
  vendorId: string
  repoId: string
}) {
  const [offset, setOffset] = useOffsetParam(OFFSET_KEY)
  const filters = useVendorFindingFilters()
  const query = useVendorFindings(vendorId, {
    limit: DEFAULT_LIMIT,
    offset,
    repoId,
    severity: filters.severity ?? undefined,
    path: filters.pathPrefix ?? undefined,
    order: (filters.order ?? undefined) as FindingOrder | undefined,
  })

  if (query.isPending) {
    return (
      <div className="min-h-0 flex-1 overflow-auto p-section">
        <LoadingState what={`open findings for ${vendorId}`} />
      </div>
    )
  }
  if (query.isError) {
    return (
      <div className="min-h-0 flex-1 overflow-auto p-section">
        <ErrorState
          error={query.error}
          what={`open findings for ${vendorId}`}
          onRetry={() => void query.refetch()}
        />
      </div>
    )
  }

  const page = query.data
  const activeFilters = filters.activeFilters

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {/* Pinned above the rows it narrows rather than scrolling with them: a control that moves
          away from its table is a control a reader scrolls back up to reach. */}
      <div className="flex shrink-0 flex-wrap items-start gap-section border-b border-line px-section py-row">
        <FacetChips
          legend="Severity"
          options={severityOptions(page)}
          selected={filters.severity}
          onSelect={filters.setSeverity}
          allLabel="Every severity"
          countScope={`Counted over all ${page.severity_total.toLocaleString()} open findings for ${vendorId} in ${repoId}, not over the page below.`}
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
        <ActiveFilters filters={activeFilters} onClear={filters.clearAll} />
      </div>

      {page.items.length === 0 ? (
        <div className="min-h-0 flex-1 overflow-auto p-section">
          <FindingsEmptyState
            vendorId={vendorId}
            repoId={repoId}
            page={page}
            filters={activeFilters}
            offset={offset}
          />
        </div>
      ) : (
        <TableFrame fill className="rounded-none border-0">
          <FindingsTable repoId={repoId} rows={page.items} stickyHeader />
        </TableFrame>
      )}

      <div className="flex shrink-0 flex-col gap-field border-t border-line px-section py-field">
        <ProvenanceStrip
          provenance={page}
          bindingNullLabel={
            // An empty page has no rungs to disagree, so "mixed" would invent a conflict.
            page.items.length === 0
              ? "none: there is no finding here to attribute"
              : "mixed: the findings on this page do not all rest on one rung"
          }
        />
        <FooterBar
          offset={offset}
          limit={DEFAULT_LIMIT}
          shown={page.items.length}
          total={page.total}
          /* `severity_total` is this scope's own count, read without the filter applied --
             `types.ts` states it does not agree with `total` whenever a filter is on and is not
             supposed to. That disagreement is exactly the number decision 60 wants shown. */
          unfilteredTotal={activeFilters.length > 0 ? page.severity_total : undefined}
          nextOffset={page.next_offset}
          busy={query.isFetching}
          onOffsetChange={setOffset}
          left={
            activeFilters.length > 0 ? (
              <p className="text-meta text-ink-muted">
                Filtered range — {vendorId} has {page.severity_total.toLocaleString()} open in{" "}
                {repoId} in total.
              </p>
            ) : undefined
          }
        />
      </div>
    </div>
  )
}
