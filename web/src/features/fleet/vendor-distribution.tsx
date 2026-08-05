/**
 * The operator's first question, answered here and at `/codebase`: which vendors have open
 * findings right now. Both screens read `GET /api/overview` and render the same row shape
 * through `VendorFindingsTable` — this file is the one place that table's columns and links
 * are declared, so `/codebase`'s full detail and this screen's summary cannot silently
 * disagree about what a vendor row shows.
 *
 * Ordering by open-finding count, descending, is a client-side re-sort of a set `/api/overview`
 * already returns in full — honest under Decision 4 because nothing here is paginated. It is
 * also the closest this screen can get to "which vendor needs attention first" until a route
 * accepts the severity filter the frozen surface already offers; `ScreenLimitsCard` states that
 * gap once for the whole screen rather than repeating it in this card's own prose.
 */

import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import type { VendorSummary } from "@/api/types"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CardinalityStatement, describeCardinality, sliceForDisplay } from "@/features/fleet/cardinality"

/** The vendor rows, unpaginated. Shared so `/codebase` and this screen render one table, not two. */
export function VendorFindingsTable({ vendors }: { vendors: readonly VendorSummary[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-meta">Vendor</TableHead>
          <TableHead className="text-meta">Open findings</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {vendors.map((vendor) => (
          <TableRow key={vendor.vendor_id}>
            <TableCell>
              <Link
                to={`/vendors/${encodeURIComponent(vendor.vendor_id)}`}
                className="font-mono underline underline-offset-2"
              >
                {vendor.vendor_id}
              </Link>
            </TableCell>
            <TableCell className="font-mono">{vendor.open_finding_count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function byOpenFindingCountDescending(a: VendorSummary, b: VendorSummary): number {
  return b.open_finding_count - a.open_finding_count || a.vendor_id.localeCompare(b.vendor_id)
}

export function VendorDistributionCard() {
  const query = useOverview()

  return (
    <div className="flex flex-col gap-4">
      {query.isPending && <LoadingState what="the open findings" />}
      {query.isError && <ErrorState error={query.error} what="the open findings" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="text-emphasis">
              {query.data.total_findings.toLocaleString()} open{" "}
              {query.data.total_findings === 1 ? "finding" : "findings"} across{" "}
              {query.data.vendors.length}{" "}
              {query.data.vendors.length === 1 ? "vendor" : "vendors"}
            </CardTitle>
            <CardDescription className="text-body">
              Every open finding the graph holds, grouped by the vendor whose API the call
              site binds to. The full per-vendor detail lives at{" "}
              <Link to="/codebase" className="underline underline-offset-2">
                Codebase
              </Link>
              ; this panel is that same answer, ordered by which vendor has the most open
              findings.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {query.data.vendors.length === 0 ? (
              <EmptyState
                headline="No vendor is at risk."
                detail="The API answered, and the graph holds no open findings. That is a result, not a failure — nothing indexed is currently broken, drifting, or wasting money."
              />
            ) : (
              <>
                <CardinalityStatement
                  text={describeCardinality(
                    query.data.vendors.length,
                    "vendor",
                    "vendors",
                    "open finding count, descending",
                  )}
                />
                <VendorFindingsTable
                  vendors={sliceForDisplay(
                    [...query.data.vendors].sort(byOpenFindingCountDescending),
                  )}
                />
              </>
            )}
            <ProvenanceStrip
              provenance={query.data}
              bindingNullLabel={
                // Null means two different things and the empty page is the one that would
                // be misreported: with no findings there is nothing to disagree about, so
                // "mixed" would invent a conflict.
                query.data.vendors.length === 0
                  ? "none: there is no finding here to attribute"
                  : "mixed: the open findings do not all rest on one rung"
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
