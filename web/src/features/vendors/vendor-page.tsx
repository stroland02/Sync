/**
 * One API service: what is at risk across the codebase, and what the vendor changed.
 *
 * **Owner decision 29 sets the order, and the mock draws the opposite one.** `03-vendor` leads
 * with what the vendor changed and puts open findings at the bottom. The decision leads with
 * exposure — what this vendor costs this codebase — and puts the vendor's history below it as the
 * reason those findings appeared. The settled authority order puts a decision above the mock, so
 * the conflict is resolved that way and recorded rather than left for the next reader to
 * rediscover.
 *
 * Top to bottom: the operations this codebase calls, then the findings open against them, then
 * what the vendor published beside where it was read from.
 */

import { useParams } from "react-router"

import { FactList } from "@/components/fact-list"
import { VendorChangesCard } from "@/features/vendors/vendor-changes-table"
import { VendorExposureCard } from "@/features/vendors/vendor-exposure-card"
import {
  VendorFindingsCard,
  VendorFindingsControls,
} from "@/features/vendors/vendor-findings-table"
import { VendorSourcesCard } from "@/features/vendors/vendor-sources-card"
import { DetailGrid } from "@/layouts/detail-grid"
import { UnknownRoute } from "@/layouts/unknown-route"


export interface VendorPageProps {
  readonly question?: string
}

export function VendorPage() {
  // **The route is the scope**, and it used to be a query string: this read
  // `searchParams.get("repo_id")` while the route carries `:repoId`, so an address naming a
  // workspace could still render a fleet-wide claim -- the screen contradicting its own URL.
  const { vendorId, repoId } = useParams<{ vendorId: string; repoId: string }>()
  if (vendorId === undefined || repoId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-8">
      {/* Header and Fact List */}
      <DetailGrid
        railSide="end"
        rail={
          <FactList
            facts={[
              { label: "Vendor", value: <span className="font-mono">{vendorId}</span> },
              {
                label: "Repository scope",
                value: <span className="font-mono">{repoId}</span>,
              },
              {
                label: "Findings counted over",
                value: repoId,
              },
              {
                label: "Changes counted over",
                value: "The vendor, never a repository",
              },
            ]}
          />
        }
      >
        <div className="flex min-w-0 flex-col gap-section">
          <p className="max-w-prose text-body text-muted-foreground">
            Open findings for {vendorId} in <span className="font-mono">{repoId}</span> alone. The
            vendor changes below are the exception and say so: what {vendorId} published is a fact
            about the vendor, not about this workspace.
          </p>
        </div>
      </DetailGrid>

      <div className="flex flex-col gap-8" data-testid="vendor-exposure">
        <VendorExposureCard vendorId={vendorId} repoId={repoId} />
        <VendorFindingsControls vendorId={vendorId} repoId={repoId} />
        <VendorFindingsCard vendorId={vendorId} repoId={repoId} />
      </div>

      <div
        className="grid grid-cols-1 lg:grid-cols-2 gap-section items-start"
        data-testid="vendor-history"
      >
        <VendorChangesCard vendorId={vendorId} repoId={repoId} />
        <VendorSourcesCard vendorId={vendorId} repoId={repoId} />
      </div>
    </section>
  )
}
