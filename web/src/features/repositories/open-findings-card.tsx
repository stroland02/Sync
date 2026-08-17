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
 *
 * **The bounded total is this panel's metric, and the vendor count is not.** M7-W173's mapping
 * (`docs/superpowers/briefs/2026-08-07-substrate-codebase.md`) keeps the figure and the words that
 * say what it counts exactly as this card already had them in one title, split across
 * `MetricPanel`'s value and unit. The `+` glyph `describeBoundedTotal` writes still ships with the
 * caveat paragraph that says in words what it means, because a glyph is never the only channel.
 */

import { Link } from "react-router"

import { useOverview } from "@/api/queries"
import type { Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { ProvenanceStrip } from "@/components/provenance"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
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
      <h3 className="furniture text-meta text-ink-muted">By severity</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Severity</TableHead>
            <TableHead>Open findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([severity, count]) => (
            <TableRow key={severity}>
              <TableCell className="font-mono">{severity}</TableCell>
              <TableCell className="font-mono">{count}</TableCell>
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
    <div className="flex min-w-0 flex-col gap-section">
      {query.isPending && <LoadingState what={`open findings in ${repoId}`} />}
      {query.isError && <ErrorState error={query.error} what={`open findings in ${repoId}`} onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <MetricPanel
          label="Open findings"
          metric={{
            value: describeBoundedTotal(
              query.data.total_findings,
              query.data.total_findings_bound_reached,
            ),
            unit: `open ${
              query.data.total_findings === 1 ? "finding" : "findings"
            } in this repository`,
          }}
          caption={
            <>
              <p className="max-w-prose">
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
              </p>
              {query.data.total_findings_bound_reached && (
                <p className="max-w-prose">
                  {boundedTotalCaveat(query.data.total_findings_bound)}
                </p>
              )}
            </>
          }
        >
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
        </MetricPanel>
      )}
    </div>
  )
}
