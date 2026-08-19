/**
 * One API service: what the vendor changed, and what is at risk across the codebase.
 *
 * **The owner re-ruled the order on 2026-08-19, superseding decision 29.** That decision led
 * with exposure — what this vendor costs this codebase — with the vendor's history at the
 * bottom. Looking at the running page reversed it: until telemetry attaches, the exposure
 * table's rung and traffic columns are constants, so the page opened on its emptiest answer
 * while the changes feed — the thing that moves — sat below the fold. The mock (`03-vendor`)
 * drew this order all along; the ruling is recorded here so the next reader sees a decision
 * rather than a drift back to the mock.
 *
 * Top to bottom: what the vendor published beside where it was read from, then the operations
 * this codebase calls, then the findings open against them.
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
                // One scope fact, not two: "Repository scope" and "Findings counted over"
                // carried the same value under different labels, which reads as two facts.
                label: "Findings counted over",
                value: <span className="font-mono">{repoId}</span>,
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
            What {vendorId} published, then what it touches here. The changes are a fact about the
            vendor, never about this workspace; the exposure and findings beneath them are counted
            over <span className="font-mono">{repoId}</span> alone.
          </p>
        </div>
      </DetailGrid>

      {/* No `items-start`: the two cards share this row, and stretching them to one height is
          what keeps the pairing legible as a pairing rather than as two blocks that happen to
          be adjacent. The page gap, because this row sits between panels, not inside one. */}
      <div
        className="grid grid-cols-1 gap-8 lg:grid-cols-2"
        data-testid="vendor-history"
      >
        <VendorChangesCard vendorId={vendorId} repoId={repoId} />
        <VendorSourcesCard vendorId={vendorId} repoId={repoId} />
      </div>

      <div className="flex flex-col gap-8" data-testid="vendor-exposure">
        <VendorExposureCard vendorId={vendorId} repoId={repoId} />
        <VendorFindingsControls vendorId={vendorId} repoId={repoId} />
        <VendorFindingsCard vendorId={vendorId} repoId={repoId} />
      </div>
    </section>
  )
}
