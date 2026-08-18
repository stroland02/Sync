/**
 * One API service: what is at risk across the codebase, and what the vendor changed.
 *
 * Screen layout extracted from `docs/console-mock/index.html` Section 3 (`03-vendor`):
 * - Top 2-column grid: "What the vendor changed" (left) and "Where it was read from" (right)
 * - Control bar: Severity, prefix path filter, and ordering choices
 * - Full-width bottom card: "Errors and incidents" (open findings table, pagination, provenance)
 */

import { useParams, useSearchParams } from "react-router"

import { FactList } from "@/components/fact-list"
import { VendorChangesCard } from "@/features/vendors/vendor-changes-table"
import {
  VendorFindingsCard,
  VendorFindingsControls,
} from "@/features/vendors/vendor-findings-table"
import { VendorSourcesCard } from "@/features/vendors/vendor-sources-card"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { DetailGrid } from "@/layouts/detail-grid"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"

const DEFAULT_QUESTION = "What is at risk from this vendor, and what did it change?"

export interface VendorPageProps {
  readonly question?: string
}

export function VendorPage({ question = DEFAULT_QUESTION }: VendorPageProps) {
  const { vendorId } = useParams<{ vendorId: string }>()
  const [searchParams] = useSearchParams()
  if (vendorId === undefined) return <UnknownRoute />
  const repoId = searchParams.get("repo_id")

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
                value:
                  repoId === null ? (
                    "Nothing selected one on the way here"
                  ) : (
                    <span className="font-mono">{repoId}</span>
                  ),
              },
              {
                label: "Findings counted over",
                value: repoId === null ? "Every repository the index has seen" : repoId,
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
          <PageHeader
            trail={
              <Breadcrumbs
                trail={[
                  { label: "Repositories", to: "/" },
                  ...(repoId === null
                    ? []
                    : [{ label: repoId, to: `/repositories/${encodeURIComponent(repoId)}` }]),
                  { label: vendorId },
                ]}
              />
            }
            title={<span className="font-mono">{vendorId}</span>}
            question={question}
          />
          {repoId === null ? (
            <p className="max-w-prose text-body text-muted-foreground">
              Every open finding and every published change for {vendorId}, across every
              repository the index has seen. Nothing selected a repository on the way here, so
              this page is in the fleet&apos;s scope rather than one codebase&apos;s — open it from a
              repository to narrow the findings below.
            </p>
          ) : (
            <p className="max-w-prose text-body text-muted-foreground">
              Open findings for {vendorId} in <span className="font-mono">{repoId}</span> alone.
              The vendor changes below are the exception and say so: what {vendorId} published is
              a fact about the vendor, not about this repository.
            </p>
          )}
        </div>
      </DetailGrid>

      {/* Top 2-column layout from console-mock 03-vendor */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
        <VendorChangesCard vendorId={vendorId} repoId={repoId} />
        <VendorSourcesCard vendorId={vendorId} repoId={repoId} />
      </div>

      {/* Findings Controls Bar */}
      <VendorFindingsControls vendorId={vendorId} repoId={repoId} />

      {/* Findings / Errors & Incidents Table */}
      <VendorFindingsCard vendorId={vendorId} repoId={repoId} />
    </section>
  )
}
