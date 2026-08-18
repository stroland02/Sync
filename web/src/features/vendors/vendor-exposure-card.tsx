/**
 * What this vendor costs this codebase — the vendor page's opening answer, per decision 29.
 *
 * Operations first, because the reader's question on arriving is *where am I exposed*, and the
 * vendor's publishing history below it is the reason findings appeared rather than the headline.
 *
 * **Every row states its rung.** A call site is what the static index found, and `CLAUDE.md`
 * requires the rung on every binding and everything derived from one: a false positive that
 * cannot be attributed to a rung cannot be fixed.
 *
 * **Telemetry sits beside the count, never inside it.** A reader sees that the graph found four
 * call sites *and* that traffic confirmed the operation — two facts. Folding them into one
 * "confidence" would be the composite this console refuses, and it would also be unreadable:
 * static evidence and observed evidence answer different questions.
 *
 * **`observed` is three-valued.** `null` is not "no traffic" — it is nobody looked, because no
 * telemetry is attached, or because the question spans repositories that differ. It renders as
 * *never measured*, which is the distinction the whole console exists to keep.
 *
 * No ratio, no percentage, no score. Counts, a rung, and a tri-state.
 */

import { Link } from "react-router"

import { useVendorOperations } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { ErrorState, LoadingState } from "@/components/states"
import { TableEmptyState } from "@/components/table-empty"
import { Badge } from "@/vendor/supabase/ui/badge"

/** What `observed` says on screen, including the case where nothing looked. */
export function observedLabel(observed: boolean | null): string {
  if (observed === null) return "never measured"
  return observed ? "traffic confirmed" : "no traffic seen"
}

function bindingSurfaceHref(vendorId: string, operation: string, repoId: string): string {
  const path = `/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operation)}`
  return `${path}?repo_id=${encodeURIComponent(repoId)}`
}

export function VendorExposureCard({
  vendorId,
  repoId,
}: {
  vendorId: string
  repoId: string
}) {
  const query = useVendorOperations(vendorId, repoId)

  if (query.isPending) return <LoadingState what={`what ${vendorId} costs this codebase`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`what ${vendorId} costs this codebase`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const { operations, telemetry_attached_at: attachedAt } = query.data

  return (
    <MetricPanel
      label="What this costs you"
      caption={
        <>
          <p className="max-w-prose">
            The operations this codebase calls on {vendorId}, and how many places call each. Every
            row is what the static index found, which is why each states its rung rather than
            leaving it to be assumed.
          </p>
          <p className="max-w-prose">
            {attachedAt === null
              ? "No telemetry is attached to this scope, so no row can say whether traffic reached the operation. That is nobody having looked, which is a different fact from having looked and seen nothing."
              : "Telemetry is attached, so an operation no span named is a measured absence of traffic rather than an unasked question."}
          </p>
        </>
      }
    >
      <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Operation</TableHead>
              <TableHead>Call sites</TableHead>
              <TableHead>Repositories</TableHead>
              <TableHead>Rung</TableHead>
              <TableHead>Traffic</TableHead>
            </TableRow>
          </TableHeader>
          {operations.length === 0 ? (
            <TableEmptyState
              columns={5}
              headline={`This codebase does not call ${vendorId}.`}
              detail="The index found no current call site naming this vendor. A call the last pass stopped finding is not counted here, so a vendor this codebase used to call reads the same as one it never did."
            />
          ) : (
          <TableBody>
            {operations.map((operation) => (
              <TableRow key={operation.operation_id}>
                <TableCell className="font-mono">
                  <Link
                    to={bindingSurfaceHref(vendorId, operation.operation_id, repoId)}
                    className="underline underline-offset-2"
                  >
                    {operation.operation_id}
                  </Link>
                </TableCell>
                <TableCell className="font-mono">{operation.call_site_count}</TableCell>
                <TableCell className="font-mono">{operation.repository_count}</TableCell>
                <TableCell>
                  <Badge>{operation.binding_rung}</Badge>
                </TableCell>
                <TableCell className="text-meta text-ink-muted">
                  {observedLabel(operation.observed)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
          )}
        </Table>

      {operations.length > 0 && (
        <p className="text-meta text-ink-muted leading-relaxed">
          Showing all {operations.length.toLocaleString()}{" "}
          {operations.length === 1 ? "operation" : "operations"} this codebase calls on {vendorId}.
          This list is not a page: the answer is one row per operation, bounded by the vendor's
          operation surface rather than by traffic, so there is nothing behind it.
        </p>
      )}
    </MetricPanel>
  )
}
