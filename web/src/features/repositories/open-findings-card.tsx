/**
 * What is currently wrong in one repository, and which vendors it is wrong with.
 *
 * The design document's reason for starting the hierarchy at a repository is that the question
 * an operator actually has is "what is wrong with my code"
 * (`specs/2026-07-25-sync-self-maintaining-apis-design.md:407`). Nothing on the Codebase screen
 * answered it: index coverage says what Sync has read, observed telemetry says what traffic
 * arrived, and neither is a finding. This card is that answer, and it is also the way down to
 * API Services — a vendor row here opens that vendor's findings still scoped to this
 * repository.
 *
 * Every figure is scoped. `GET /api/overview?repo_id=` counts open findings in this repository
 * alone, and the payload echoes `repo_id` back so the scope is a fact in the response rather
 * than a promise the screen makes about a request it sent. An unscoped answer under a
 * repository's heading is a false claim about that repository, which is the defect B92 closes.
 *
 * **Two absences that are not the same, and this card renders both.** No open finding is a
 * measured zero: the API answered and the graph holds none for this repository. That is not a
 * verdict that nothing is wrong — a detector reports what it can see, and `IndexCoverageCard`
 * beside this one carries what the index does not see. The card says so rather than letting an
 * empty table read as a clean bill of health, which is the one thing a screen with no health
 * figure must still not imply.
 */

import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import type { Tally } from "@/api/types"
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
import {
  boundedTotalCaveat,
  CardinalityStatement,
  describeBoundedTotal,
  describeCardinality,
  sliceForDisplay,
} from "@/features/fleet/cardinality"
import { VendorFindingsTable } from "@/features/fleet/vendor-distribution"

/** Severity counts, in the vocabulary's own order rather than by size. */
function SeverityBreakdown({ counts }: { counts: Tally }) {
  const entries = Object.entries(counts).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex flex-col gap-row">
      <h3 className="furniture text-meta text-muted-foreground">By severity</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-meta">Severity</TableHead>
            <TableHead className="text-meta">Open findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([severity, count]) => (
            <TableRow key={severity}>
              <TableCell className="font-mono text-body">{severity}</TableCell>
              <TableCell className="font-mono text-body">{count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function OpenFindingsCard({ repoId }: { repoId: string }) {
  const query = useOverview(repoId)

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what={`open findings in ${repoId}`} />}
      {query.isError && <ErrorState error={query.error} what={`open findings in ${repoId}`} />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="flex flex-wrap items-baseline gap-field">
              <span className="text-figure">
                {describeBoundedTotal(
                  query.data.total_findings,
                  query.data.total_findings_bound_reached,
                )}
              </span>
              <span>
                open {query.data.total_findings === 1 ? "finding" : "findings"} in this
                repository
              </span>
            </CardTitle>
            <CardDescription className="max-w-prose text-body">
              Counted in <span className="font-mono">{repoId}</span> and in no other
              repository — every figure on this card moves when a different repository is
              selected. A vendor below opens its findings still scoped here; detector
              attribution for this repository alone is on{" "}
              <Link
                to={`/detectors?repo_id=${encodeURIComponent(repoId)}`}
                className="underline underline-offset-2"
              >
                the detectors screen
              </Link>
              .
            </CardDescription>
            {query.data.total_findings_bound_reached && (
              <p className="max-w-prose text-body text-muted-foreground">
                {boundedTotalCaveat(query.data.total_findings_bound)}
              </p>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-section">
            {query.data.vendors.length === 0 ? (
              <EmptyState
                headline={`No open finding against any vendor in ${repoId}.`}
                detail="The API answered, and the graph holds no open finding for this repository. That is a measured zero rather than silence — but it is not a verdict that nothing is wrong: a detector reports what it can see, and the index coverage card beside this one is where what Sync has not read is stated."
              />
            ) : (
              <>
                <CardinalityStatement
                  text={describeCardinality(
                    query.data.vendors.length,
                    "vendor",
                    "vendors",
                    "vendor id, alphabetically",
                  )}
                />
                <VendorFindingsTable
                  vendors={sliceForDisplay(query.data.vendors)}
                  repoId={repoId}
                />
                <SeverityBreakdown counts={query.data.severity_counts} />
              </>
            )}
            <ProvenanceStrip
              provenance={query.data}
              bindingNullLabel={
                query.data.vendors.length === 0
                  ? "none: there is no finding here to attribute"
                  : "mixed: this repository's open findings do not all rest on one rung"
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
