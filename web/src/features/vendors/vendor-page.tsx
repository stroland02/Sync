/**
 * One API service: what is at risk in this codebase, and what the vendor changed.
 *
 * The two tables query independently so a failure on one does not blank the other — the
 * vendor's changes are still an answer when the findings query fails, and vice versa.
 */

import { useParams } from "react-router"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { VendorChangesTable } from "@/features/vendors/vendor-changes-table"
import { VendorFindingsTable } from "@/features/vendors/vendor-findings-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function VendorPage() {
  const { vendorId } = useParams<{ vendorId: string }>()
  if (vendorId === undefined) return <UnknownRoute />

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs
        trail={[
          { label: "Fleet", to: "/" },
          { label: "Codebase", to: "/codebase" },
          { label: vendorId },
        ]}
      />
      <h1 className="font-mono text-page">{vendorId}</h1>

      <Card>
        <CardHeader>
          <CardTitle>Errors and incidents</CardTitle>
          <CardDescription>
            Call sites in this codebase that an open finding touches. The rung on each row
            says how the system knows the site is bound to the operation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VendorFindingsTable vendorId={vendorId} />
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
          <VendorChangesTable vendorId={vendorId} />
        </CardContent>
      </Card>
    </section>
  )
}
