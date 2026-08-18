/**
 * The vendors attached to one repository.
 *
 * The owner's instruction was a vendors page listing *"all the vendors part of that codebase"*, at
 * an equal stage with API services. This is the list; `vendor-page.tsx` is the detail a row opens.
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

import { useParams } from "react-router"
import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import { Badge } from "@/vendor/supabase/ui/badge"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"

const DEFAULT_QUESTION =
  "Which API vendors does this repository call, and how much is open against each?"

export interface RepositoryVendorsPageProps {
  readonly question?: string
}

export function RepositoryVendorsPage({ question = DEFAULT_QUESTION }: RepositoryVendorsPageProps) {
  const { repoId } = useParams<{ repoId: string }>()
  const overview = useOverview(repoId)

  const trail = (
    <Breadcrumbs
      trail={[
        { label: "Overview", to: "/" },
        { label: repoId ?? "", to: `/repositories/${encodeURIComponent(repoId ?? "")}` },
        { label: "Vendors" },
      ]}
    />
  )

  const header = <PageHeader title="Vendors" question={question} trail={trail} />

  if (overview.isPending) {
    return (
      <section className="flex flex-col gap-section">
        {header}
        <LoadingState what="the vendors attached to this repository" />
      </section>
    )
  }

  if (overview.isError) {
    return (
      <section className="flex flex-col gap-section">
        {header}
        <ErrorState
          error={overview.error}
          what="the vendors attached to this repository"
          onRetry={() => void overview.refetch()}
        />
      </section>
    )
  }

  // The answer names the scope it was computed for. Rendering rows from a fleet-wide answer under
  // this repository's heading would be a false claim about this repository, so it is refused rather
  // than shown with a caveat.
  const scopeMatches = overview.data?.repo_id === repoId
  const vendors = scopeMatches ? (overview.data?.vendors ?? []) : []

  return (
    <section className="flex flex-col gap-section">
      {header}

      {!scopeMatches ? (
        <EmptyState
          headline="This answer was computed for a different scope."
          detail={
            `The overview that arrived names its scope as ` +
            `${overview.data?.repo_id ?? "the whole fleet"}, not ${repoId}. Its vendors are not ` +
            `shown here, because a fleet-wide list under one repository's name is a claim about ` +
            `that repository which nothing computed.`
          }
        />
      ) : vendors.length === 0 ? (
        <EmptyState
          headline="No vendor is attached to this repository."
          detail="A vendor appears here once INDEX finds a call site binding this repository to it."
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
            {vendors.map((vendor) => (
              <TableRow key={vendor.vendor_id}>
                <TableCell>
                  <Link
                    to={`/vendors/${encodeURIComponent(vendor.vendor_id)}?repo_id=${encodeURIComponent(repoId ?? "")}`}
                    className="font-mono underline underline-offset-2"
                  >
                    {vendor.vendor_id}
                  </Link>
                </TableCell>
                <TableCell>
                  {/* A confirmed zero is an answer about this vendor and renders as words, never as
                      the absence marker. The two mean different things and the console's whole
                      position rests on not collapsing them. */}
                  <Badge>
                    {vendor.open_finding_count === 0
                      ? "No open findings"
                      : `${vendor.open_finding_count} open findings`}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      <p className="text-meta text-muted-foreground max-w-5xl leading-relaxed">
        This list is what INDEX bound in this repository. A vendor's published rate limits, auth
        rules and call structures are not shown, because no stage captures them yet — that is work
        not done rather than a vendor with none.
      </p>
    </section>
  )
}
