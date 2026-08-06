/**
 * Errors and incidents for one vendor: every call site an open finding touches.
 *
 * The rung column is per row and is the one to weigh a finding by. The envelope's rung
 * below the table is a property of the page and goes null the moment the page mixes rungs,
 * which is exactly when the per-row column stops being redundant.
 *
 * The operation column links into the Binding surface level. `repoId`, when the caller has
 * one, rides along so the surface that opens is scoped to it.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useVendorFindings } from "@/api/queries"
import { PageControls } from "@/components/page-controls"
import { ProvenanceStrip, RungBadge } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

function bindingSurfaceHref(vendorId: string, operation: string, repoId: string | null): string {
  const path = `/bindings/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operation)}`
  return repoId === null ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`
}

export function VendorFindingsTable({
  vendorId,
  repoId = null,
}: {
  vendorId: string
  repoId?: string | null
}) {
  const [offset, setOffset] = useOffsetParam("findings_offset")
  const query = useVendorFindings(vendorId, { limit: DEFAULT_LIMIT, offset })

  if (query.isPending) return <LoadingState what={`open findings for ${vendorId}`} />
  if (query.isError) {
    return <ErrorState error={query.error} what={`open findings for ${vendorId}`} />
  }

  const page = query.data

  return (
    <div className="flex flex-col gap-section">
      {page.items.length === 0 ? (
        <EmptyState
          headline={`No open findings for ${vendorId}.`}
          detail="The API answered with an empty page. Either nothing in this codebase calls that vendor, or nothing that does is currently at risk."
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
                <TableHead>Finding</TableHead>
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
                    {row.file}:{row.line}
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
                  <TableCell>
                    <Link
                      to={`/findings/${encodeURIComponent(row.finding_id)}`}
                      className="font-mono underline underline-offset-2"
                    >
                      {row.finding_id}
                    </Link>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <PageControls
            offset={offset}
            limit={DEFAULT_LIMIT}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            busy={query.isFetching}
            onOffsetChange={setOffset}
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
    </div>
  )
}
