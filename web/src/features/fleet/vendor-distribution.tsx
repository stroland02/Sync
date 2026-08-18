/**
 * The operator's first question: which vendors have open findings right now, across every
 * repository the index has seen. `/codebase` used to answer the same question from the same
 * `GET /api/overview` payload, unpaginated; that route was retired in the 2026-08-05
 * hierarchy reconciliation because it wore the Codebase level's name over data no repository
 * scopes it to, and this panel — capped, and honest about the cap — is what a fleet-wide
 * answer to that question looks like once the borrowed name is gone. The per-repository
 * answer lives one level down, at a repository's own Codebase screen.
 *
 * Ordering by open-finding count, descending, is a client-side re-sort of a set `/api/overview`
 * already returns in full — honest under Decision 4 because nothing here is paginated. It is
 * also the closest this screen can get to "which vendor needs attention first" until a route
 * accepts the severity filter the frozen surface already offers; `ScreenLimitsCard` states that
 * gap once for the whole screen rather than repeating it in this card's own prose.
 *
 * **The vendor count is this panel's metric, and the open-findings total is not.** M7-W163 moved
 * that total to the fact rail and the rule it set holds here: a panel renders the count that is
 * its own grain and never one an operator has already read at the top of the screen. The figure
 * ships with the word it counts, because a bare number under a panel name is a number claiming to
 * be whatever the reader guesses.
 */

import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import type { VendorSummary } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  boundedTotalCaveat,
  CardinalityStatement,
  describeCardinality,
  sliceForDisplay,
} from "@/features/fleet/cardinality"
import { FooterBar } from "@/layouts/footer-bar"

import { vendorHref } from "@/lib/hrefs"
/**
 * The vendor rows, unpaginated.
 *
 * `repoId` is the scope the rows were counted in, and it travels into each link rather than
 * being dropped at the boundary: a vendor opened from a repository's own screen must land on
 * that repository's findings, not on the fleet's. Null is the fleet, which is what the lead
 * screen passes.
 */
export function VendorFindingsTable({
  vendors,
  repoId,
}: {
  vendors: readonly VendorSummary[]
  repoId: string
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Vendor</TableHead>
          <TableHead>Open findings</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {vendors.map((vendor) => (
          <TableRow key={vendor.vendor_id}>
            <TableCell>
              <Link
                to={vendorHref(vendor.vendor_id, repoId)}
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

export function VendorDistributionCard({ repoId }: { repoId: string }) {
  // Scoped, because every page is a workspace's page. This asked `useOverview()` with no argument
  // and counted every repository the index has seen, which is the show-all the owner ruled out.
  const query = useOverview(repoId)

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the open findings" />}
      {query.isError && <ErrorState error={query.error} what="the open findings" onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <MetricPanel
          label="Open findings by vendor"
          metric={{
            value: query.data.vendors.length.toLocaleString(),
            unit: query.data.vendors.length === 1 ? "vendor with open findings" : "vendors with open findings",
          }}
          caption={
            <>
              <p className="max-w-prose">
                Every open finding the graph holds, grouped by the vendor whose API the call
                site binds to, ordered by which vendor has the most open findings. This is the
                fleet's roll-up across every repository the index has seen, which is the
                question this level asks; the same figures for one codebase are on that
                repository's own Codebase screen, and the two are different numbers rather than
                different renderings of one.
              </p>
              {query.data.total_findings_bound_reached && (
                <p className="max-w-prose">{boundedTotalCaveat(query.data.total_findings_bound)}</p>
              )}
            </>
          }
        >
          {query.data.vendors.length === 0 ? (
            <EmptyState
              headline="No vendor is at risk."
              detail="The API answered, and the graph holds no open findings. That is a result, not a failure — nothing indexed is currently broken, drifting, or wasting money."
            />
          ) : (
            <>
              <VendorFindingsTable
                repoId={repoId}
                vendors={sliceForDisplay(
                  [...query.data.vendors].sort(byOpenFindingCountDescending),
                )}
              />
              {/* No pager: `/api/overview` returns the vendor roll-up whole, so the slice above is
                  a display decision rather than a page, and the sentence says which. */}
              <FooterBar
                left={
                  <CardinalityStatement
                    text={describeCardinality(
                      query.data.vendors.length,
                      "vendor",
                      "vendors",
                      "open finding count, descending",
                    )}
                  />
                }
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
        </MetricPanel>
      )}
    </div>
  )
}
