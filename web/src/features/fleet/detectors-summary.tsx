/**
 * "Which detector is producing my false positives?" — answerable from `GET /api/detectors`
 * without a transport change, so it belongs on the lead screen alongside the other four.
 *
 * The rung column is the point, not an incidental one: CLAUDE.md requires a false positive
 * be attributable to the rung that produced it, and a detector whose findings mix rungs is
 * making more than one kind of claim under a single name.
 */

import { Link } from "react-router"

import { useDetectors } from "@/api/queries"
import type { DetectorRow, Tally } from "@/api/types"
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
import { CardinalityStatement, describeCardinality, sliceForDisplay } from "@/features/fleet/cardinality"

function summariseTally(tally: Tally): string {
  return Object.entries(tally)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, count]) => `${key}: ${count}`)
    .join(", ")
}

function byTotalDescending(a: DetectorRow, b: DetectorRow): number {
  return b.total - a.total || a.detector.localeCompare(b.detector)
}

export function DetectorsSummaryCard() {
  const query = useDetectors()

  return (
    <div className="flex flex-col gap-4">
      {query.isPending && <LoadingState what="the detector attribution" />}
      {query.isError && <ErrorState error={query.error} what="the detector attribution" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="text-emphasis">
              {query.data.detectors.length}{" "}
              {query.data.detectors.length === 1 ? "detector" : "detectors"} with open findings
            </CardTitle>
            <CardDescription className="text-body">
              Every open finding, aggregated by the detector that raised it — scoped to open
              findings, the only findings read the graph offers today. A closed finding is
              invisible here exactly as it is invisible everywhere else in the console.{" "}
              <Link to="/detectors" className="underline underline-offset-2">
                Full detail
              </Link>
              .
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {query.data.detectors.length === 0 ? (
              <EmptyState
                headline="No detector has an open finding."
                detail="The API answered, and no open finding names a detector — there are no open findings to attribute. That is an answer, not a failure."
              />
            ) : (
              <>
                <CardinalityStatement
                  text={describeCardinality(
                    query.data.detectors.length,
                    "detector",
                    "detectors",
                    "open finding count, descending",
                  )}
                />
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-meta">Detector</TableHead>
                      <TableHead className="text-meta">Open findings</TableHead>
                      <TableHead className="text-meta">By rung</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sliceForDisplay(
                      [...query.data.detectors].sort(byTotalDescending),
                    ).map((detector) => (
                      <TableRow key={detector.detector}>
                        <TableCell className="font-mono text-body">
                          {detector.detector}
                        </TableCell>
                        <TableCell className="font-mono text-body">{detector.total}</TableCell>
                        <TableCell className="font-mono text-meta text-muted-foreground">
                          {summariseTally(detector.by_rung)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
