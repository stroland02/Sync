/**
 * One API service: what is at risk across the codebase, and what the vendor changed.
 *
 * The two tables query independently so a failure on one does not blank the other — the
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
 * The cards are gone for the reason `binding-surface-page.tsx` records: a card costs 32px of
 * horizontal room, the findings table is the widest thing on this screen, and the two regions are
 * told apart by their headings and by the rule each footer bar draws under itself.
 */

import { useParams, useSearchParams } from "react-router"

import { FactList } from "@/components/fact-list"
import { VendorChangesTable } from "@/features/vendors/vendor-changes-table"
import { VendorFindingsTable } from "@/features/vendors/vendor-findings-table"
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
    <>
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
              Open findings for {vendorId} in{" "}
              <span className="font-mono">{repoId}</span> alone. The vendor changes below are the
              exception and say so: what {vendorId} published is a fact about the vendor, not
              about this repository.
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

      <section className="flex flex-col gap-section">
        <div className="flex flex-col gap-field">
          <h2 className="text-section">Errors and incidents</h2>
          <p className="max-w-prose text-body text-ink-muted">
            Call sites that an open finding touches
            {repoId === null ? (
              <>
                , in every repository the index has seen — this table is not scoped to one
                codebase, because nothing selected one on the way here
              </>
            ) : (
              <>
                {" "}
                in <span className="font-mono">{repoId}</span>, and in no other repository
              </>
            )}
            . The rung on each row says how the system knows the site is bound to the
            operation.
          </p>
        </div>
        <VendorFindingsTable vendorId={vendorId} repoId={repoId} />
      </section>

      <section className="flex flex-col gap-section">
        <div className="flex flex-col gap-field">
          <h2 className="text-section">Vendor changes</h2>
          <p className="max-w-prose text-body text-ink-muted">
            What {vendorId} published, whether or not this codebase is affected. Every change
            the feed has recorded, and{" "}
            {repoId === null ? "not narrowed to any repository" : (
              <>
                <span className="font-mono">not</span> narrowed to{" "}
                <span className="font-mono">{repoId}</span>
              </>
            )}
            : a vendor publishes a change once, to everyone, so this list is the same whichever
            repository you reached it from. To see what it hits here, open an operation's
            binding surface from the table above.
          </p>
        </div>
        <VendorChangesTable vendorId={vendorId} repoId={repoId} />
      </section>
    </>
  )
}
