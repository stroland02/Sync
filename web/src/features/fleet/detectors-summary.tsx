/**
 * "Which detector is producing my false positives?" — answerable from `GET /api/detectors`
 * without a transport change, so it belongs on the lead screen alongside the other four.
 *
 * The rung column is the point, not an incidental one: CLAUDE.md requires a false positive
 * be attributable to the rung that produced it, and a detector whose findings mix rungs is
 * making more than one kind of claim under a single name. It is never hidden and never coloured.
 *
 * No metric figure: the fact rail's fourth tile already names how many detectors have open findings.
 *
 * **The panel's name used to carry that count a third time**, reading `4 detectors with open
 * findings` over a cardinality sentence that read `This is all 4 detectors.` — the `h2` the gap
 * report measured on a screen with no footer under any of its rows. The heading is the section's
 * name now and the count sits under the rows it counts;
 * `2026-08-07-substrate-fidelity-task-4.md` carries why that footer takes no pager.
 */

import { useDetectors } from "@/api/queries"
import type { DetectorRow, Tally } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { CardinalityStatement, describeCardinality, sliceForDisplay } from "@/features/fleet/cardinality"
import { FooterBar } from "@/layouts/footer-bar"

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
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the detector attribution" />}
      {query.isError && <ErrorState error={query.error} what="the detector attribution" onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <MetricPanel
          label="Detectors with open findings"
          caption={
            <p className="max-w-prose">
              {/* The link to the Detectors level was here, mid-sentence. M7-W163 moved it to the
                  screen's control bar, which is where a control plane keeps a primary action —
                  a destination reached by reading to the end of a paragraph is a destination
                  most readers do not reach. */}
              Every open finding, aggregated by the detector that raised it — scoped to open
              findings, the only findings read the graph offers today. A closed finding is
              invisible here exactly as it is invisible everywhere else in the console.
            </p>
          }
        >
          {query.data.detectors.length === 0 ? (
            <EmptyState
              headline="No detector has an open finding."
              detail="The API answered, and no open finding names a detector — there are no open findings to attribute. That is an answer, not a failure."
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Detector</TableHead>
                    <TableHead>Open findings</TableHead>
                    <TableHead>By rung</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sliceForDisplay(
                    [...query.data.detectors].sort(byTotalDescending),
                  ).map((detector) => (
                    <TableRow key={detector.detector}>
                      <TableCell className="font-mono">{detector.detector}</TableCell>
                      <TableCell className="font-mono">{detector.total}</TableCell>
                      <TableCell className="font-mono text-meta text-muted-foreground">
                        {summariseTally(detector.by_rung)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <FooterBar
                left={
                  <CardinalityStatement
                    text={describeCardinality(
                      query.data.detectors.length,
                      "detector",
                      "detectors",
                      "open finding count, descending",
                    )}
                  />
                }
              />
            </>
          )}
        </MetricPanel>
      )}
    </div>
  )
}
