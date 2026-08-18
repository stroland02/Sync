/**
 * Dashboard 7, as a propless card the Signals route mounts.
 *
 * Propless but scoped: it reads `repoId` from the router the way `signals-page.tsx` does, so
 * mounting is one import and one tag while the answer stays repository-scoped. Telemetry attaches
 * per repository, so a fleet-wide version of this question has no single answer.
 *
 * `observed-volume-option.ts` carries what is counted. What this file owns is the four sentences
 * that stop the numbers being read as something they are not:
 *
 * - Telemetry never attached renders as an absence, not as a volume of nought.
 * - The figures are summed over the rows this page holds, and the frame says so when that is not
 *   all of them, because a ranking built from a page can change when the rest arrives.
 * - Errors sit beside calls as a count. There is no failure rate, however tempting the division.
 * - A one-day series prints its figure instead of drawing a line, because a slope needs two
 *   points and a flat line invented from one reads as stability.
 */

import { useCallback } from "react"
import { useParams } from "react-router"

import { useRepositoryObserved } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import {
  buildOperationSparklineOption,
  observedVolumeByOperation,
  type VolumePoint,
} from "@/features/dashboards/observed-volume-option"
import { formatTimestamp } from "@/lib/format"
import { Badge } from "@/vendor/supabase/ui/badge"

/** The ceiling the transport enforces. Asked for deliberately: a wider page is a truer ranking. */
const CALLS_LIMIT = 500

function Sparkline({ series }: { series: readonly VolumePoint[] }) {
  const build = useCallback(
    (tokens: ChartTokens) => buildOperationSparklineOption(series, tokens),
    [series],
  )
  return (
    <div className="h-6 w-28">
      <EChart
        buildOption={build}
        ariaLabel={`Call volume across ${series.length} days`}
        style={{ height: "100%", width: "100%" }}
      />
    </div>
  )
}

export function ObservedVolumeCard() {
  const { repoId } = useParams<{ repoId: string }>()
  const query = useRepositoryObserved(repoId ?? "", { callsLimit: CALLS_LIMIT })

  if (repoId === undefined) return null
  if (query.isPending) return <LoadingState what={`observed call volume for ${repoId}`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`observed call volume for ${repoId}`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  const volume = observedVolumeByOperation(query.data)

  return (
    <MetricPanel
      label="What traffic actually called"
      caption={
        <p className="max-w-prose">
          Observed calls per operation for{" "}
          <span className="font-mono">{repoId}</span>, from correlated traces rather than from the
          code. This is the one question the static index cannot answer: not whether this codebase
          calls an operation, but whether anything did.
        </p>
      }
    >
      {!volume.telemetryAttached ? (
        <EmptyState
          headline="Never measured."
          detail="No telemetry has been attached to this repository, so nothing has looked at its traffic. This is the absence of a measurement rather than a measurement of nothing — an operation with no calls here would look identical, and the two are not the same fact."
        />
      ) : volume.operations.length === 0 ? (
        <EmptyState
          headline="Telemetry is attached and has seen no calls."
          detail={`Attached ${formatTimestamp(volume.attachedAt) ?? "at an unrecorded time"}. This is a measured nought: something looked and found no traffic, which is a different answer from never having looked.`}
        />
      ) : (
        <div className="flex flex-col gap-field">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Operation</TableHead>
                <TableHead>Vendor</TableHead>
                <TableHead>Calls</TableHead>
                <TableHead>Errors</TableHead>
                <TableHead>Rung</TableHead>
                <TableHead>Over time</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {volume.operations.map((operation) => (
                <TableRow key={`${operation.vendorId}-${operation.operationId}`}>
                  <TableCell className="font-mono">{operation.operationId}</TableCell>
                  <TableCell className="font-mono">{operation.vendorId}</TableCell>
                  <TableCell className="font-mono">{operation.calls.toLocaleString()}</TableCell>
                  <TableCell className="font-mono">{operation.errors.toLocaleString()}</TableCell>
                  <TableCell>
                    <span className="flex flex-wrap gap-field">
                      {operation.rungs.map((rung) => (
                        <Badge key={rung}>{rung}</Badge>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell>
                    {operation.drawable ? (
                      <Sparkline series={operation.series} />
                    ) : (
                      <span className="text-meta text-ink-muted">
                        one day only — <Absent />
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <p className="text-meta text-ink-muted leading-relaxed">
            {volume.complete ? (
              <>Counted over all {volume.totalRows.toLocaleString()} observed-call rows.</>
            ) : (
              <>
                <span className="text-ink">
                  Counted over {volume.countedRows.toLocaleString()} of{" "}
                  {volume.totalRows.toLocaleString()} observed-call rows.
                </span>{" "}
                These figures are sums over that page, not the operations&apos; totals, and the
                ranking can change when the rest arrives.
              </>
            )}{" "}
            Errors are a count of failed calls beside the calls themselves, never divided into
            them — a failure rate would average two facts. An operation listed at more than one
            rung arrived at both: a span that correlated to it and a span that did not are two
            observations, not one stronger one.
          </p>
        </div>
      )}
    </MetricPanel>
  )
}
