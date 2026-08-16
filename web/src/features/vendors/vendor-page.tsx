/**
 * One API service: what is at risk across the codebase, and what the vendor changed.
 *
 * The two panels query independently so a failure on one does not blank the other — the
 * vendor's changes are still an answer when the findings query fails, and vice versa.
 *
 * The screen carries two scopes on purpose, and says which is which beside each.
 *
 * **Findings are scoped to the repository** when the URL names one. `GET /api/vendors/{id}`
 * takes `repo_id` and the answer echoes the scope back, so what a reader sees under a
 * repository's name is that repository's findings — API Services is the first level under
 * Codebase, and repository scope is what every level below it inherits.
 *
 * **Changes are not, and cannot be.** What a vendor published is a fact about the vendor, true
 * whether or not any repository calls it, so there is no repository scope for it to be in.
 * `whats_changed` takes no `repo_id` and gains nothing from one. That is stated beside the table
 * rather than left for a reader to infer from a number that did not move.
 *
 * ---
 *
 * **M7-W164 moved this screen onto the chassis.** The two scopes were the screen's whole argument
 * and were carried only inside two paragraphs of prose; they are now also four facts in a list
 * beside the header, which is what a reader scans before deciding whether a number means what they
 * assumed. The paragraphs stay where they are — the list says *which* scope, the sentence beside
 * each table says *why it cannot be otherwise*, and those are different claims.
 *
 * ## Ported onto the vendored substrate by M7-W174
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-api-services.md` is the mapping table this port was
 * gated on. Read that before porting a level, not this docstring.
 *
 * Both sections are now panels: the `h2` that named each is the panel's own name at
 * `--text-section`, the paragraph under it is the panel's caption, and both tables take the Studio anatomy
 * through `components/data-table.tsx`. The findings panel gains the figure this level never
 * rendered — open findings for this vendor in this scope, before any filter — and the changes panel
 * deliberately gains none, because `vendor_change` rows are at-least-once and a count of them is
 * not a measurement.
 *
 * **No page-level `ControlBar`, and the chassis is complete without one.** The bar is already on
 * this screen: the findings panel has held severity, path and ordering since the filters landed.
 * A second bar could only carry the scope, and the scope is already stated by the fact list and by
 * the paragraph beside it — a third copy is a fact that will disagree with itself. The action slot
 * stays empty because the one candidate, detector attribution, is scoped by repository and not by
 * vendor, so offering it here would silently widen the scope this page is about.
 */

import { useParams, useSearchParams } from "react-router"

import { FactList } from "@/components/fact-list"
import { VendorChangesCard } from "@/features/vendors/vendor-changes-table"
import { VendorFindingsCard } from "@/features/vendors/vendor-findings-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"
import { routeQuestion } from "@/lib/routes"

/** This screen's own entry in the registry, so `PageHeader` renders the registry's sentence. */
const ROUTE_PATH = "/vendors/:vendorId"

export function VendorPage() {
  const { vendorId } = useParams<{ vendorId: string }>()
  const [searchParams] = useSearchParams()
  if (vendorId === undefined) return <UnknownRoute />
  const repoId = searchParams.get("repo_id")

  return (
    <section className="flex flex-col gap-8">
      {/* The header and the fact list share one band, which is where M7-W164 put them and why:
          the four facts are what a reader checks before deciding whether a number below means
          what they assumed, so they belong beside the question rather than under it. Measured at
          1280x800, stacking the header full width instead cost 105px above the first table row and
          bought nothing this arrangement does not already give. */}
      <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="flex min-w-0 flex-col gap-section">
          <PageHeader
            trail={
              <Breadcrumbs
                trail={
                  repoId === null
                    ? [{ label: "Fleet", to: "/" }, { label: vendorId }]
                    : [
                        { label: "Fleet", to: "/" },
                        { label: repoId, to: `/repositories/${encodeURIComponent(repoId)}` },
                        { label: vendorId },
                      ]
                }
              />
            }
            title={<span className="font-mono">{vendorId}</span>}
            question={routeQuestion(ROUTE_PATH)}
          />
          {repoId === null ? (
            <p className="max-w-prose text-body text-muted-foreground">
              Every open finding and every published change for {vendorId}, across every
              repository the index has seen. Nothing selected a repository on the way here, so
              this page is in the fleet's scope rather than one codebase's — open it from a
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
      </div>

      {/* Both panels take the full width. Six columns each, and the widest cell on the screen is a
          call-site path from a customer repository — halving either wraps every row, which is the
          constraint the findings table's own rung-column comment already records at full width. */}
      <VendorFindingsCard vendorId={vendorId} repoId={repoId} />
      <VendorChangesCard vendorId={vendorId} repoId={repoId} />
    </section>
  )
}
