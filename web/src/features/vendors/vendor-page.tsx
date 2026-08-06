/**
 * One API service: what is at risk across the codebase, and what the vendor changed.
 *
 * The two tables query independently so a failure on one does not blank the other — the
 * vendor's changes are still an answer when the findings query fails, and vice versa.
 *
 * This screen is fleet-wide and stays that way regardless of how it was reached:
 * `GET /api/vendors/{vendor_id}` takes no `repo_id`, so a vendor's findings and changes are
 * never narrowed to one repository, even when the URL carries a `repo_id` the breadcrumb used
 * to get here. The query string is passed through purely so a link built from this page —
 * into a binding surface, which *can* be scoped — keeps the repository the operator started
 * from, rather than losing it at the one screen that cannot use it.
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
    <section className="flex flex-col gap-4">
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
      <p className="text-body text-muted-foreground">
        Every open finding and every published change for {vendorId}, across every repository
        the index has seen — <code className="font-mono">GET /api/vendors/{vendorId}</code>{" "}
        takes no repository id, so nothing below can be narrowed to one codebase yet.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Errors and incidents</CardTitle>
          <CardDescription>
            Call sites in this codebase that an open finding touches. The rung on each row
            says how the system knows the site is bound to the operation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VendorFindingsTable vendorId={vendorId} repoId={repoId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Vendor changes</CardTitle>
          <CardDescription>
            What {vendorId} published, whether or not this codebase is affected.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VendorChangesTable vendorId={vendorId} repoId={repoId} />
        </CardContent>
      </Card>
    </section>
  )
}
