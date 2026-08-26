/**
 * What the vendor published, whether or not this codebase is affected.
 *
 * Rebuilt from `vendor-changes-table.tsx` (deleted) as a pane body: a four-column table that scrolls
 * under its own pinned head, with the rest of each row in a drawer.
 *
 * **Six columns became four, and the two that moved are the ones a reader does not read per row.**
 * `path_ptr` is a JSON pointer sixty characters long — the widest cell in the table by a factor of
 * three — and the version pair is the same `from → to` on every row of one intake. Both are what a
 * reader wants *about a row they have chosen*, which is what the drawer is for (owner ruling
 * 2026-08-25: a detail must never squeeze the table). What is left is the row's position in the
 * feed, what changed, how the vendor graded it, and the one column that reaches this codebase.
 *
 * **No headline figure, and that is the ruling M7-W174 exists to make.** `sync.graph.schema.sql`
 * declares `vendor_change` as the one source in the pipeline that does not converge: the rows are
 * at-least-once, so a count of them is not a measurement. The range under the table says which rows
 * this page holds, which is a fact about the page rather than about the vendor.
 *
 * This route's envelope carries a null `indexed_at` and a null `binding_source`, and both are
 * correct rather than missing: the answer is built from vendor changes alone and holds no binding,
 * so naming a rung would claim a mapping that does not appear in the payload.
 */

import { useMemo } from "react"
import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorChanges } from "@/api/queries"
import type { VendorChangeRow } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { DetailLayout, useSelectionKeys, useSelectionParam } from "@/components/detail-layout"
import { FactList } from "@/components/fact-list"
import { ProvenanceStrip } from "@/components/provenance"
import { RelativeTime } from "@/components/relative-time"
import { Absent, Formatted } from "@/components/status"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { ChangeKindTag, SeverityTag } from "@/components/tag"
import { changeKey } from "@/features/vendors/vendor-record"
import { FooterBar } from "@/layouts/footer-bar"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { bindingSurfaceHref } from "@/lib/hrefs"
import { useOffsetParam } from "@/lib/use-offset-param"

/** Everything about one change that is not worth a column on every row. */
function ChangeDetail({
  change,
  vendorId,
  repoId,
}: {
  change: VendorChangeRow
  vendorId: string
  repoId: string
}) {
  return (
    <div className="flex min-w-0 flex-col gap-section">
      <FactList
        facts={[
          { label: "Kind", value: <ChangeKindTag kind={change.change_kind} /> },
          { label: "Severity", value: <SeverityTag severity={change.severity} /> },
          {
            label: "Published",
            value: (
              <time dateTime={change.published_at} className="font-mono text-meta">
                <Formatted value={formatTimestamp(change.published_at)} />
              </time>
            ),
          },
          {
            label: "Versions compared",
            value: (
              <span className="font-mono text-meta break-all">
                <Formatted value={orAbsent(change.from_version)} /> →{" "}
                <Formatted value={orAbsent(change.to_version)} />
              </span>
            ),
          },
        ]}
      />

      <section className="flex min-w-0 flex-col gap-field">
        <h3 className="furniture text-meta text-ink-muted">Where in the specification</h3>
        {change.path_ptr === null ? (
          <span className="text-meta">
            <Absent>
              <span>
                no pointer recorded — this change names the document rather than a position in it
              </span>
            </Absent>
          </span>
        ) : (
          <code className="min-w-0 rounded-control border border-line bg-surface-subtle p-field font-mono text-meta break-all select-all">
            {change.path_ptr}
          </code>
        )}
      </section>

      <section className="flex min-w-0 flex-col gap-field">
        <h3 className="furniture text-meta text-ink-muted">What it meets here</h3>
        {change.operation === null ? (
          <span className="text-meta">
            <Absent>
              <span>
                no operation recorded — this change names no operation, so nothing joins it to a
                call site in this codebase
              </span>
            </Absent>
          </span>
        ) : (
          <>
            <Link
              className="text-body text-brand-link underline underline-offset-2"
              to={bindingSurfaceHref(repoId, vendorId, change.operation)}
            >
              Open the binding surface for {change.operation} →
            </Link>
            <p className="max-w-prose text-meta text-ink-muted">
              Whether a call site here is affected is a detector&rsquo;s answer, and a
              detector&rsquo;s answer is a finding rather than a row in this table.
            </p>
          </>
        )}
      </section>
    </div>
  )
}

export function VendorChangesRecord({
  vendorId,
  repoId,
}: {
  vendorId: string
  repoId: string
}) {
  const [offset, setOffset] = useOffsetParam("changes_offset")
  const [openChange, setOpenChange] = useSelectionParam("change")
  const query = useVendorChanges(vendorId, { limit: DEFAULT_LIMIT, offset })

  const items = useMemo(() => query.data?.items ?? [], [query.data])
  const keys = useMemo(() => items.map(changeKey), [items])
  useSelectionKeys(keys, openChange, setOpenChange)
  const selected = openChange === null ? null : (items.find((row) => changeKey(row) === openChange) ?? null)

  if (query.isPending) {
    return (
      <div className="min-h-0 flex-1 overflow-auto p-section">
        <LoadingState what={`the changes ${vendorId} published`} />
      </div>
    )
  }
  if (query.isError) {
    return (
      <div className="min-h-0 flex-1 overflow-auto p-section">
        <ErrorState
          error={query.error}
          what={`the changes ${vendorId} published`}
          onRetry={() => void query.refetch()}
        />
      </div>
    )
  }

  const page = query.data

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {page.items.length === 0 ? (
        <div className="min-h-0 flex-1 overflow-auto p-section">
          <EmptyState
            headline={`Nothing recorded for ${vendorId}.`}
            detail="The API answered with an empty page. Either no feed has been ingested for this vendor, or it has published nothing Sync tracks."
            command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
          />
        </div>
      ) : (
        <DetailLayout
          docked
          title={selected === null ? "Change" : selected.change_kind}
          subtitle={selected === null ? undefined : (selected.operation ?? "no operation named")}
          onClose={() => setOpenChange(null)}
          detail={
            selected === null ? null : (
              <ChangeDetail change={selected} vendorId={vendorId} repoId={repoId} />
            )
          }
          list={
            <TableFrame fill className="rounded-none border-0">
              <Table>
                <TableHeader sticky>
                  <TableRow>
                    <TableHead>Published</TableHead>
                    <TableHead>Kind</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Operation</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {page.items.map((change) => {
                    const key = changeKey(change)
                    return (
                      <TableRow
                        key={key}
                        data-state={key === openChange ? "selected" : undefined}
                        className="cursor-pointer"
                        onClick={() => setOpenChange(key === openChange ? null : key)}
                      >
                        <TableCell className="text-meta">
                          <time dateTime={change.published_at}>
                            <RelativeTime iso={change.published_at} />
                          </time>
                        </TableCell>
                        <TableCell>
                          <ChangeKindTag kind={change.change_kind} />
                        </TableCell>
                        <TableCell>
                          <SeverityTag severity={change.severity} />
                        </TableCell>
                        <TableCell className="font-mono">
                          {change.operation === null ? (
                            <Formatted value={null} />
                          ) : (
                            <Link
                              to={bindingSurfaceHref(repoId, vendorId, change.operation)}
                              className="underline underline-offset-2 break-words"
                              onClick={(event) => event.stopPropagation()}
                            >
                              {change.operation}
                            </Link>
                          )}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </TableFrame>
          }
        />
      )}

      {/* Pinned rather than scrolled: provenance a reader has to scroll to reach is provenance
          they will not read. `py-field` and one line of caveat rather than three — measured at
          1366×768, this block was 175px of a 195px body and the rows had none. The claim is
          unchanged; the argument for it is behind the pane's ⓘ. */}
      <div className="flex shrink-0 flex-col gap-field border-t border-line px-section py-field">
        <ProvenanceStrip
          provenance={page}
          bindingNullLabel="none: this answer is built from vendor changes and holds no binding"
          indexedNullLabel="not applicable: nothing here was read out of the codebase"
        />
        <FooterBar
          offset={offset}
          limit={DEFAULT_LIMIT}
          shown={page.items.length}
          total={page.total}
          nextOffset={page.next_offset}
          busy={query.isFetching}
          onOffsetChange={setOffset}
          left={
            <p className="text-meta text-ink-muted">
              Recorded at least once — which rows this page holds, never a count of what{" "}
              {vendorId} changed.
            </p>
          }
        />
      </div>
    </div>
  )
}
