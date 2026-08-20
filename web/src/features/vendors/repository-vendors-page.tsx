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

import { useAdapters, useRepositoryCoverage } from "@/api/queries"
import type { AdapterRow } from "@/api/types"
import { Badge } from "@/vendor/supabase/ui/badge"
import { Button } from "@/vendor/supabase/ui/button"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Skeleton } from "@/components/skeleton"
import { Absent } from "@/components/status"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { PageTabs, vendorsTabs } from "@/components/page-tabs"
import { IntegrationsKpis } from "@/features/vendors/integrations-kpis"
import { VendorCard, ADAPTER_TIERS } from "@/features/vendors/vendor-card"


import { vendorHref } from "@/lib/hrefs"
export interface RepositoryVendorsPageProps {
  readonly question?: string
}

type ViewMode = "table" | "cards"
type TierFilter = "all" | AdapterRow["kind"]

/**
 * How many of one vendor's API products this codebase calls.
 *
 * Three answers, and they are three different facts: the coverage route did not answer, it
 * answered about another repository, or it answered and this vendor has *n* products grouped. A
 * vendor whose operations no adapter has mapped answers nought grouped, which is work not done
 * rather than a vendor selling one API -- so it takes the absence marker and not a zero.
 */
function ServicesCalled({
  vendorId,
  coverage,
  repoId,
}: {
  vendorId: string
  coverage: ReturnType<typeof useRepositoryCoverage>
  repoId: string
}) {
  if (coverage.isPending) return <Skeleton width="2rem" />
  if (coverage.isError) return <Absent>the index did not answer</Absent>
  if (coverage.data.repo_id !== repoId) return <Absent>answered for another repository</Absent>
  // Hotfix from the UI session (2026-08-19 evening): the running API does not serve
  // `by_service` yet, and the unguarded read crashed the whole Vendors page. Missing-from-API
  // is its own nothing — not "no products", which the empty-set branch below claims.
  if (coverage.data.by_service === undefined) {
    return <Absent>product grouping not served yet</Absent>
  }
  const named = new Set(
    coverage.data.by_service
      .filter((row) => row.vendor_id === vendorId && row.service_id !== null)
      .map((row) => row.service_id),
  )
  if (named.size === 0) return <Absent>not grouped into products yet</Absent>
  return <>{named.size.toLocaleString()}</>
}


export function RepositoryVendorsPage() {
  const { repoId } = useParams<{ repoId: string }>()
  const adaptersQuery = useAdapters()
  // How many of its API products this codebase actually calls, from the route the Services screen
  // reads. A vendor is a provider and a service is one of the APIs it sells; the count is the
  // relation between the two screens, and it is a count rather than a list because naming the
  // products here would be the Services screen rendered twice.
  const coverage = useRepositoryCoverage(repoId ?? "")

  const [viewMode, setViewMode] = useState<ViewMode>("table")
  const [tierFilter, setTierFilter] = useState<TierFilter>("all")



  if (coverage.isPending) {
    return (
      <section className="flex flex-col gap-8">
        <LoadingState what="the vendors attached to this repository" />
      </section>
    )
  }

  if (coverage.isError) {
    return (
      <section className="flex flex-col gap-8">
        <ErrorState
          error={coverage.error}
          what="the vendors attached to this repository"
          onRetry={() => void coverage.refetch()}
        />
      </section>
    )
  }

  // The answer names the scope it was computed for. Rendering rows from a fleet-wide answer under
  // this repository's heading would be a false claim about this repository, so it is refused rather
  // than shown with a caveat.
  //
  // **The list is what the index bound, not what has an open finding**, from 2026-08-19. It was
  // built on `overview.vendors` -- a `GROUP BY` over open findings -- so a vendor this codebase
  // calls cleanly was absent from a page asking which vendors it uses, and the page could not
  // answer its own question without the Errors & Incidents payload the owner has now ruled off it.
  const scopeMatches = coverage.data?.repo_id === repoId
  const vendors = scopeMatches
    ? Object.entries(coverage.data?.by_vendor ?? {})
        .map(([vendor_id, call_sites]) => ({ vendor_id, call_sites: Number(call_sites) }))
        .sort((a, b) => b.call_sites - a.call_sites || a.vendor_id.localeCompare(b.vendor_id))
    : []
  const adaptersMap = new Map(
    (adaptersQuery.data?.adapters ?? []).map((adapter) => [adapter.vendor_id, adapter])
  )

  const filteredVendors = vendors.filter((v) => {
    if (tierFilter === "all") return true
    const adapter = adaptersMap.get(v.vendor_id)
    return adapter?.kind === tierFilter
  })

  return (
    <section className="flex min-w-0 flex-col gap-8">
      <PageTabs label="Vendors" tabs={vendorsTabs(repoId ?? "")} />

      {/* Dashboard I1. Above the scope check on purpose: the catalogue is its own read with its
          own scope, so it stays true when the overview beneath arrives computed for a different
          one — and a page whose only content is a mismatch notice tells a reader nothing about
          what this deployment can watch. */}
      {repoId !== undefined && <IntegrationsKpis repoId={repoId} />}

      {!scopeMatches ? (
        <EmptyState
          headline="This answer was computed for a different scope."
          detail={
            `The index coverage that arrived names its scope as ` +
            `${coverage.data?.repo_id ?? "another repository"}, not ${repoId}. Its vendors are not ` +
            `shown here, because a fleet-wide list under one repository's name is a claim about ` +
            `that repository which nothing computed.`
          }
        />
      ) : vendors.length === 0 ? (
        <EmptyState
          headline="No vendor is attached to this repository."
          detail="A vendor appears here once INDEX finds a call site binding this repository to it."
          command={`uv run sync index --repo ${repoId}`}
        />
      ) : (
        <div className="flex flex-col gap-section">
          {/* Controls Bar: Filter tabs & View toggle */}
          <div className="flex flex-wrap items-center justify-between gap-field pb-field border-b border-line">
            <div className="flex items-center gap-field overflow-x-auto">
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

            <div className="flex items-center gap-field">
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
                    to={vendorHref(repoId ?? "", vendor.vendor_id)}
                    className="block group focus:outline-none"
                  >
                    <VendorCard
                      vendorId={vendor.vendor_id}
                      adapter={adapter}
                      callSites={vendor.call_sites}
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
                  <TableHead>Services called</TableHead>
                  <TableHead>Call sites</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredVendors.map((vendor) => {
                  const adapter = adaptersMap.get(vendor.vendor_id)
                  return (
                    <TableRow key={vendor.vendor_id}>
                      <TableCell>
                        <Link
                          to={vendorHref(repoId ?? "", vendor.vendor_id)}
                          className="font-mono underline underline-offset-2"
                        >
                          {vendor.vendor_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <Badge>{adapter ? adapter.kind : "none"}</Badge>
                      </TableCell>
                      <TableCell className="font-mono">
                        <ServicesCalled
                          vendorId={vendor.vendor_id}
                          coverage={coverage}
                          repoId={repoId ?? ""}
                        />
                      </TableCell>
                      <TableCell className="font-mono">
                        {vendor.call_sites.toLocaleString()}
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
