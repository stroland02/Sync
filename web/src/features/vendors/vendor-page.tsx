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
 * `whats_changed` takes no `repo_id` and gains nothing from one. That is stated on the card
 * rather than left for a reader to infer from a number that did not move.
 */

import { useParams, useSearchParams } from "react-router"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { VendorChangesTable } from "@/features/vendors/vendor-changes-table"
import { VendorFindingsTable } from "@/features/vendors/vendor-findings-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function VendorPage() {
  const { vendorId } = useParams<{ vendorId: string }>()
  const [searchParams] = useSearchParams()
  if (vendorId === undefined) return <UnknownRoute />
  const repoId = searchParams.get("repo_id")

  return (
    <section className="flex flex-col gap-8">
      <div className="flex flex-col gap-section">
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
        <h1 className="font-mono text-page">{vendorId}</h1>
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
            <span className="font-mono">{repoId}</span> alone. The changes card below is the
            exception and says so: what {vendorId} published is a fact about the vendor, not
            about this repository.
          </p>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Errors and incidents</CardTitle>
          <CardDescription className="max-w-prose">
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
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VendorFindingsTable vendorId={vendorId} repoId={repoId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Vendor changes</CardTitle>
          <CardDescription className="max-w-prose">
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
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VendorChangesTable vendorId={vendorId} repoId={repoId} />
        </CardContent>
      </Card>
    </section>
  )
}
