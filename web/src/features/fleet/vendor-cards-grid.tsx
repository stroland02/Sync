/**
 * One card per vendor this codebase calls: how many places call it, and how many findings are open.
 *
 * Adopted from Lane F, which is retired. Its composition is kept — a dense grid of per-vendor
 * cards below the totals line — and three of its claims are not.
 *
 * **No composite figure per vendor.** The adopted card drew a filled track whose width was
 * `openFindings / callSites`. That is a scalar over two counts, which is refused on the record
 * three times over, and it is a *rate* besides: findings per call site is not a quantity either
 * number measures, and the track invited reading a long bar as a worse vendor. The two counts are
 * on the card and they are not averaged into a third thing.
 *
 * **No verdict.** `Clean` and `Active` were a green dot and a liveness pulse written as words. A
 * vendor with no open findings has no open findings, which is a count, and it is already stated.
 *
 * **An unanswered count is `null`, never nought.** The adopted card wrote
 * `findingCountsByVendor[vendorId] ?? 0`, so a vendor the overview had not answered for showed a
 * confident "0 open findings". `/api/overview` names the vendors it counted; a vendor absent from
 * that list was not counted rather than counted at zero, and the two render differently here.
 */

import { Link } from "react-router"

import { useOverview, useRepositoryCoverage } from "@/api/queries"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"

export interface VendorCardsGridProps {
  readonly repoId: string
}

export function VendorCardsGrid({ repoId }: VendorCardsGridProps) {
  const coverage = useRepositoryCoverage(repoId)
  const overview = useOverview(repoId)

  if (coverage.isPending) {
    return (
      <div className="grid grid-cols-1 gap-section sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex flex-col gap-row rounded-surface border border-border bg-card p-section"
          >
            <Skeleton width="w-24" />
            <Skeleton width="w-16" />
          </div>
        ))}
      </div>
    )
  }

  if (coverage.isError || coverage.data === undefined) {
    return null
  }

  const vendors = Object.entries(coverage.data.by_vendor).sort(([a], [b]) => a.localeCompare(b))

  if (vendors.length === 0) {
    return (
      <div className="rounded-surface border border-border bg-card p-section text-meta text-muted-foreground">
        <Absent>no vendor attached to this repository</Absent>
      </div>
    )
  }

  // Absent from the overview's list means not counted, which is not the same as counted at nought.
  const openFindingsByVendor = new Map<string, number>(
    overview.data?.vendors?.map((v) => [v.vendor_id, v.open_finding_count]) ?? []
  )

  return (
    <div className="flex flex-col gap-row">
      <div className="flex items-center justify-between">
        <h3 className="font-mono text-meta font-medium uppercase tracking-wider text-muted-foreground">
          Attached API services
        </h3>
        <span className="font-mono text-meta text-muted-foreground">
          {vendors.length} {vendors.length === 1 ? "vendor" : "vendors"}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-section sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {vendors.map(([vendorId, callSites]) => {
          const openFindings = openFindingsByVendor.get(vendorId)

          return (
            <Link
              key={vendorId}
              to={`/repositories/${encodeURIComponent(repoId)}/vendors/${encodeURIComponent(vendorId)}`}
              className="group flex flex-col gap-row rounded-surface border border-border bg-card p-section transition-colors hover:border-foreground/20 hover:bg-surface-subtle"
            >
              <div className="flex items-center justify-between gap-row">
                <span className="font-mono text-meta font-semibold uppercase tracking-wide text-foreground group-hover:text-primary">
                  {vendorId}
                </span>
                <span className="font-mono text-meta text-muted-foreground">
                  {callSites} {callSites === 1 ? "call site" : "call sites"}
                </span>
              </div>

              <div className="flex items-baseline gap-row">
                <span className="font-mono text-emphasis font-semibold tracking-tight text-foreground">
                  {openFindings === undefined ? <Absent /> : openFindings}
                </span>
                <span className="text-meta text-muted-foreground">
                  {openFindings === undefined
                    ? "open findings not yet answered"
                    : openFindings === 1
                      ? "open finding"
                      : "open findings"}
                </span>
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
