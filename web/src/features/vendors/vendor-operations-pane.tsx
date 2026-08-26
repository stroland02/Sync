/**
 * What this codebase calls on one integration — the spine of the record screen.
 *
 * Rebuilt from `vendor-exposure-card.tsx` (deleted) as a pane in a locked composition. Every claim
 * that card made survives; what went is the `MetricPanel` chrome around it and the paragraph under
 * the rows, which is now the pane's own pinned foot.
 *
 * **Every row states its rung.** A call site is what the static index found, and `CLAUDE.md`
 * requires the rung on every binding and everything derived from one: a false positive that cannot
 * be attributed to a rung cannot be fixed. It is monochrome and it is not a hideable column.
 *
 * **Telemetry sits beside the count, never inside it.** A reader sees that the graph found four
 * call sites *and* whether traffic confirmed the operation — two facts. Folding them into one
 * "confidence" would be the composite this console refuses, and it would also be unreadable:
 * static evidence and observed evidence answer different questions.
 *
 * **`observed` is three-valued.** `null` is not "no traffic" — it is nobody looked, because no
 * telemetry is attached or because the question spans repositories that differ. It renders as
 * *never measured*, which is the distinction the whole console exists to keep.
 *
 * No ratio, no percentage, no score. Counts, a rung, and a tri-state.
 */

import { Waypoints } from "lucide-react"
import type { ReactNode } from "react"
import { Link } from "react-router"

import type { VendorOperationsResponse } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { observedLabel } from "@/features/vendors/vendor-record"
import { bindingSurfaceHref } from "@/lib/hrefs"

/** A body branch that is not rows: it takes the pane's scroll rather than the table's. */
function PaneNotice({ children }: { children: ReactNode }) {
  return <div className="min-h-0 flex-1 overflow-auto p-section">{children}</div>
}

export function VendorOperationsPane({
  vendorId,
  repoId,
  data,
  isPending,
  error,
  onRetry,
}: {
  vendorId: string
  repoId: string
  data: VendorOperationsResponse | undefined
  isPending: boolean
  error: Error | null
  onRetry: () => void
}) {
  const attachedAt = data?.telemetry_attached_at ?? null
  const operations = data?.operations ?? []

  return (
    <PanelPane
      scroll={false}
      label="Operations this codebase calls"
      icon={Waypoints}
      hint={
        <InfoHint label={`About the operations ${vendorId} is called on`}>
          <p>
            What the Index stage read from the code: the operations this codebase calls on{" "}
            {vendorId}, and how many places call each. Every row is what the static index found,
            which is why each states its rung rather than leaving it to be assumed.
          </p>
          <p>
            {attachedAt === null
              ? "No telemetry is attached to this scope, so no row can say whether traffic reached the operation. That is nobody having looked, which is a different fact from having looked and seen nothing."
              : "Telemetry is attached, so an operation no span named is a measured absence of traffic rather than an unasked question."}
          </p>
        </InfoHint>
      }
      // In the head rather than a pinned foot, and that is a height decision: measured at
      // 1366×768, a 40px foot here is a third of what this pane has to give its rows. The claims
      // are unchanged — how many rows there are, that there are no more behind them, and which
      // evidence they rest on.
      actions={
        <span className="flex min-w-0 items-center gap-field text-meta text-ink-muted">
          <span className="shrink-0 font-mono tabular-nums text-ink">
            {data === undefined ? "—" : operations.length.toLocaleString()}
          </span>
          <span className="min-w-0 truncate">
            {/* Not a page: the answer is one row per operation, bounded by the vendor's operation
                surface rather than by traffic, so there is nothing behind it. */}
            {attachedAt === null
              ? "all of them · static evidence, telemetry not attached"
              : "all of them · static evidence, with telemetry attached"}
          </span>
        </span>
      }
    >
      {isPending && (
        <PaneNotice>
          <LoadingState what={`the operations ${vendorId} is called on`} />
        </PaneNotice>
      )}
      {error !== null && (
        <PaneNotice>
          <ErrorState
            error={error}
            what={`the operations ${vendorId} is called on`}
            onRetry={onRetry}
          />
        </PaneNotice>
      )}
      {data !== undefined &&
        (operations.length === 0 ? (
          <PaneNotice>
            <EmptyState
              headline={`This codebase does not call ${vendorId}.`}
              detail={`The index found no current call site in ${repoId} naming this vendor. A call the last pass stopped finding is not counted here, so a vendor this codebase used to call reads the same as one it never did.`}
              command={`uv run sync index --repo ${repoId}`}
            />
          </PaneNotice>
        ) : (
          // Borderless: the frame is what moves the scroll onto the table container, which is the
          // element a `sticky` head has to sit inside; the pane already draws the border.
          <TableFrame fill className="rounded-none border-0">
            <Table>
              <TableHeader sticky>
                {/* No Repositories column: this pane always asks with a `repoId`, so the payload's
                    `repository_count` is 1 on every row by construction — a constant is not a
                    column. The unscoped payload keeps the field for callers that ask fleet-wide. */}
                <TableRow>
                  <TableHead>Operation</TableHead>
                  <TableHead>Call sites</TableHead>
                  <TableHead>Rung</TableHead>
                  <TableHead>Traffic</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {operations.map((operation) => (
                  <TableRow key={operation.operation_id}>
                    <TableCell className="font-mono">
                      <Link
                        to={bindingSurfaceHref(repoId, vendorId, operation.operation_id)}
                        className="underline underline-offset-2 break-words"
                      >
                        {operation.operation_id}
                      </Link>
                    </TableCell>
                    <TableCell className="font-mono tabular-nums">
                      {operation.call_site_count.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <RungBadge rung={operation.binding_rung} />
                    </TableCell>
                    <TableCell className="text-meta text-ink-muted">
                      {observedLabel(operation.observed)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableFrame>
        ))}
    </PanelPane>
  )
}
