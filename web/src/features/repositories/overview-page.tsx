/**
 * The root of the hierarchy: the codebase, as the API can describe it.
 *
 * The plan calls this level "repositories", and the directory keeps that name so it
 * mirrors the graph. The screen does not: `/api/overview` answers with vendors and open
 * finding counts and no repository identity, and no route exposes one. A repository
 * selector here would be a control over data that does not exist.
 */

import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"

export function OverviewPage() {
  const query = useOverview()

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs trail={[{ label: "Codebase" }]} />
      <h1 className="text-lg font-medium">Codebase overview</h1>

      {query.isPending && <LoadingState what="the codebase overview" />}
      {query.isError && <ErrorState error={query.error} what="the codebase overview" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle>
              {query.data.total_findings} open{" "}
              {query.data.total_findings === 1 ? "finding" : "findings"} across{" "}
              {query.data.vendors.length}{" "}
              {query.data.vendors.length === 1 ? "vendor" : "vendors"}
            </CardTitle>
            <CardDescription>
              Every open finding the graph holds, grouped by the vendor whose API the call
              site binds to.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {query.data.vendors.length === 0 ? (
              <EmptyState
                headline="No vendor is at risk."
                detail="The API answered, and the graph holds no open findings. That is a result, not a failure — nothing indexed is currently broken, drifting, or wasting money."
              />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Vendor</TableHead>
                    <TableHead>Open findings</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.vendors.map((vendor) => (
                    <TableRow key={vendor.vendor_id}>
                      <TableCell>
                        <Link
                          to={`/vendors/${encodeURIComponent(vendor.vendor_id)}`}
                          className="font-mono underline underline-offset-2"
                        >
                          {vendor.vendor_id}
                        </Link>
                      </TableCell>
                      <TableCell className="font-mono">
                        {vendor.open_finding_count}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <ProvenanceStrip
              provenance={query.data}
              bindingNullLabel={
                // Null means two different things and the empty page is the one that would
                // be misreported: with no findings there is nothing to disagree about, so
                // "mixed" would invent a conflict.
                query.data.vendors.length === 0
                  ? "none: there is no finding here to attribute"
                  : "mixed: the open findings do not all rest on one rung"
              }
            />
          </CardContent>
        </Card>
      )}
    </section>
  )
}
