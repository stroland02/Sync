/**
 * The vendors attached to one repository — integration grid and table view.
 *
 * The owner's instruction was a vendors page listing *"all the vendors part of that codebase"*, at
 * an equal stage with API services, modeled after the Supabase integrations screen with cards,
 * badges, tier filters, and detailed metrics.
 *
 * **What this screen deliberately does not show.** The owner also asked for each vendor's *"api
 * formats rules calls limits structures and data traces"*. Rate limits, auth rules and call
 * structures are not captured by any stage — they are in no table and no payload — so this renders
 * what the graph holds and names the rest as absent work rather than drawing empty panels carrying
 * the never-measured marker. The owner ruled for that explicitly (`M14-W365`, ruling 2 of the first
 * round): build the page from what exists.
 *
 * **The scope check is the load-bearing part.** `/api/overview` echoes the `repo_id` it was computed
 * for. A caller that ignores it can render the fleet's vendors under one repository's name, and this
 * console has shipped that defect before — `codebases-panel.tsx` printed the fleet-wide
 * `total_findings` under every card until `M14-W265`. So the rows render only when the answer's own
 * scope matches the address, and say so plainly when it does not.
 */

import { useState } from "react"
import { useParams, Link } from "react-router"

import { useAdapters, useOverview } from "@/api/queries"
import type { AdapterRow } from "@/api/types"
import { Badge } from "@/vendor/supabase/ui/badge"
import { Button } from "@/vendor/supabase/ui/button"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { VendorCard, ADAPTER_TIERS } from "@/features/vendors/vendor-card"


export interface RepositoryVendorsPageProps {
  readonly question?: string
}

type ViewMode = "table" | "cards"
type TierFilter = "all" | AdapterRow["kind"]

export function RepositoryVendorsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const overview = useOverview(repoId)
  const adaptersQuery = useAdapters()

  const [viewMode, setViewMode] = useState<ViewMode>("table")
  const [tierFilter, setTierFilter] = useState<TierFilter>("all")



  if (overview.isPending) {
    return (
      <section className="flex flex-col gap-section">
        <LoadingState what="the vendors attached to this repository" />
      </section>
    )
  }

  if (overview.isError) {
    return (
      <section className="flex flex-col gap-section">
        <ErrorState
          error={overview.error}
          what="the vendors attached to this repository"
          onRetry={() => void overview.refetch()}
        />
      </section>
    )
  }

  // The answer names the scope it was computed for. Rendering rows from a fleet-wide answer under
  // this repository's heading would be a false claim about this repository, so it is refused rather
  // than shown with a caveat.
  const scopeMatches = overview.data?.repo_id === repoId
  const vendors = scopeMatches ? (overview.data?.vendors ?? []) : []
  const adaptersMap = new Map(
    (adaptersQuery.data?.adapters ?? []).map((adapter) => [adapter.vendor_id, adapter])
  )

  const filteredVendors = vendors.filter((v) => {
    if (tierFilter === "all") return true
    const adapter = adaptersMap.get(v.vendor_id)
    return adapter?.kind === tierFilter
  })

  return (
    <section className="flex flex-col gap-section min-w-0">

      {!scopeMatches ? (
        <EmptyState
          headline="This answer was computed for a different scope."
          detail={
            `The overview that arrived names its scope as ` +
            `${overview.data?.repo_id ?? "the whole fleet"}, not ${repoId}. Its vendors are not ` +
            `shown here, because a fleet-wide list under one repository's name is a claim about ` +
            `that repository which nothing computed.`
          }
        />
      ) : vendors.length === 0 ? (
        <EmptyState
          headline="No vendor is attached to this repository."
          detail="A vendor appears here once INDEX finds a call site binding this repository to it."
        />
      ) : (
        <div className="flex flex-col gap-section">
          {/* Controls Bar: Filter tabs & View toggle */}
          <div className="flex flex-wrap items-center justify-between gap-field pb-field border-b border-line">
            <div className="flex items-center gap-1 overflow-x-auto">
              <Button
                size="sm"
                variant={tierFilter === "all" ? "secondary" : "ghost"}
                onClick={() => setTierFilter("all")}
                className="text-meta"
              >
                All ({vendors.length})
              </Button>
              {ADAPTER_TIERS.map((tier) => {
                const count = vendors.filter((v) => adaptersMap.get(v.vendor_id)?.kind === tier).length
                if (count === 0 && tierFilter !== tier) return null
                return (
                  <Button
                    key={tier}
                    size="sm"
                    variant={tierFilter === tier ? "secondary" : "ghost"}
                    onClick={() => setTierFilter(tier)}
                    className="text-meta capitalize"
                  >
                    {tier} ({count})
                  </Button>
                )
              })}
            </div>

            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant={viewMode === "table" ? "secondary" : "ghost"}
                onClick={() => setViewMode("table")}
                className="text-meta"
              >
                Table
              </Button>
              <Button
                size="sm"
                variant={viewMode === "cards" ? "secondary" : "ghost"}
                onClick={() => setViewMode("cards")}
                className="text-meta"
              >
                Cards
              </Button>
            </div>
          </div>

          {filteredVendors.length === 0 ? (
            <EmptyState
              headline="No vendors match the selected filter."
              detail={`No attached vendor has an adapter matching tier "${tierFilter}".`}
            />
          ) : viewMode === "cards" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-section">
              {filteredVendors.map((vendor) => {
                const adapter = adaptersMap.get(vendor.vendor_id) ?? null
                return (
                  <Link
                    key={vendor.vendor_id}
                    to={`/vendors/${encodeURIComponent(vendor.vendor_id)}?repo_id=${encodeURIComponent(repoId ?? "")}`}
                    className="block group transition-transform hover:-translate-y-0.5 focus:outline-none"
                  >
                    <VendorCard
                      vendorId={vendor.vendor_id}
                      adapter={adapter}
                      openFindingCount={vendor.open_finding_count}
                    />
                  </Link>
                )
              })}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Vendor</TableHead>
                  <TableHead>Adapter Tier</TableHead>
                  <TableHead>Open findings</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredVendors.map((vendor) => {
                  const adapter = adaptersMap.get(vendor.vendor_id)
                  return (
                    <TableRow key={vendor.vendor_id}>
                      <TableCell>
                        <Link
                          to={`/vendors/${encodeURIComponent(vendor.vendor_id)}?repo_id=${encodeURIComponent(repoId ?? "")}`}
                          className="font-mono underline underline-offset-2"
                        >
                          {vendor.vendor_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Badge>{adapter ? adapter.kind : "none"}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge>
                          {vendor.open_finding_count === 0
                            ? "No open findings"
                            : `${vendor.open_finding_count} open findings`}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </div>
      )}

      <p className="text-meta text-muted-foreground max-w-5xl leading-relaxed">
        This list is what INDEX bound in this repository. A vendor&apos;s published rate limits, auth
        rules and call structures are not shown, because no stage captures them yet — that is work
        not done rather than a vendor with none.
      </p>
    </section>
  )
}
