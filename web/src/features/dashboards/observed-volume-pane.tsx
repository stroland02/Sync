/**
 * Dashboard 7 as a pane of the locked Metrics grid: the operations traffic actually called,
 * ranked, in a table that fills its share of the viewport and scrolls its own rows under a pinned
 * header.
 *
 * Rebuilt from `observed-volume-card.tsx` on 2026-08-26. What changed is the frame — a
 * `MetricPanel` that grew to whatever height five hundred rows wanted, on a page that was one
 * scrolling column, became a bounded pane on a locked screen — and two *arguments* moved behind
 * the ⓘ, where `console-surface.md` puts them. What did not move is a single distinction:
 *
 * - Telemetry never attached renders as an absence, not as a volume of nought.
 * - The figures are summed over the rows this page holds, and the frame says so when that is not
 *   all of them, because a ranking built from a page can change when the rest arrives.
 * - Errors sit beside calls as a count. There is no failure rate, however tempting the division.
 * - A one-day series prints its figure instead of drawing a line, because a slope needs two
 *   points and a flat line invented from one reads as stability.
 *
 * `observed-volume-option.ts` still carries what is counted.
 *
 * **The pane will not print a count when nothing is recorded as having watched.** Measured on the
 * running console: this deployment returns eight observed-call rows against a null
 * `telemetry_attached_at`, and the card printed "Counted over all 8 observed-call rows" directly
 * beneath "Never measured." Two sentences on one panel contradicting each other, and the count is
 * the one that has to go.
 *
 * **The scroll belongs to the table, not to the pane** (`scroll={false}`): the vendored table
 * container is the `overflow-auto` element, so it is the containing block a sticky header sticks
 * to. A second scroller around it leaves the head fixed to a box that never moves.
 */

import { useCallback } from "react"
import { Activity } from "lucide-react"
import { useParams } from "react-router"

import { useRepositoryObserved } from "@/api/queries"
import {
  Table,
  TableBody,
  TableCell,
  TableFrame,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { ErrorState, LoadingState } from "@/components/states"
import { TableEmptyState } from "@/components/table-empty"
import { Absent } from "@/components/status"
import {
  buildOperationSparklineOption,
  observedVolumeByOperation,
  type VolumePoint,
} from "@/features/dashboards/observed-volume-option"
import { formatTimestamp } from "@/lib/format"
import { Badge } from "@/vendor/supabase/ui/badge"

/** The ceiling the transport enforces. Asked for deliberately: a wider page is a truer ranking. */
export const CALLS_LIMIT = 500

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

const HINT = (
  <InfoHint label="About observed call volume">
    Observed calls per operation, from correlated traces rather than from the code. This is the one
    question the static index cannot answer: not whether this codebase calls an operation, but
    whether anything did. Telemetry attaches per repository, so there is no fleet-wide version of
    this question to fall back on — a repository nobody has attached telemetry to has never been
    looked at, which is a different fact from one whose traffic was measured at nought. Errors are
    never divided into calls because a failure rate would average two facts. And an operation
    listed at more than one rung arrived at both: a span that correlated to it and a span that did
    not are two observations, not one stronger one.
  </InfoHint>
)

export function ObservedVolumePane({ className }: { className?: string } = {}) {
  const { repoId } = useParams<{ repoId: string }>()
  const query = useRepositoryObserved(repoId ?? "", { callsLimit: CALLS_LIMIT })

  if (repoId === undefined) return null

  if (query.isPending || query.isError) {
    return (
      <PanelPane
        className={className}
        label="What traffic actually called"
        icon={Activity}
        hint={HINT}
        bodyClassName="p-section"
      >
        {query.isPending ? (
          <LoadingState what={`observed call volume for ${repoId}`} />
        ) : (
          <ErrorState
            error={query.error}
            what={`observed call volume for ${repoId}`}
            onRetry={() => void query.refetch()}
          />
        )}
      </PanelPane>
    )
  }

  const volume = observedVolumeByOperation(query.data)

  return (
    <PanelPane
      className={className}
      label="What traffic actually called"
      icon={Activity}
      hint={HINT}
      // The scope on the band, where the reference puts a pane's own figures. A repository name is
      // not decoration here: telemetry attaches per repository and this table is one repository's.
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono text-ink">{repoId}</span>
          {volume.telemetryAttached && (
            <>
              {" · "}
              <span className="font-mono tabular-nums text-ink">
                {volume.operations.length.toLocaleString()}
              </span>{" "}
              {volume.operations.length === 1 ? "operation" : "operations"}
            </>
          )}
        </span>
      }
      scroll={false}
      footer={
        !volume.telemetryAttached ? (
          // Measured on the running console 2026-08-26: `synthetic/every-state` returns eight
          // observed-call rows and a null `telemetry_attached_at`, so the old card printed
          // "Counted over all 8 rows" directly under "Never measured." — two sentences on one
          // panel contradicting each other. The count is what has to go: `telemetry_attached_at`
          // is what says anything ever looked (B157), and a sum over rows nothing is recorded as
          // having watched is a figure with no watcher behind it.
          <span>
            No telemetry attachment is recorded here, so the{" "}
            {volume.totalRows.toLocaleString()} observed-call{" "}
            {volume.totalRows === 1 ? "row" : "rows"} the transport returned are left uncounted
            rather than presented as a measurement.
          </span>
        ) : (
          <span>
            {volume.complete ? (
              <>Counted over all {volume.totalRows.toLocaleString()} observed-call rows.</>
            ) : (
              <>
                <span className="text-ink">
                  Counted over {volume.countedRows.toLocaleString()} of{" "}
                  {volume.totalRows.toLocaleString()} observed-call rows
                </span>{" "}
                — sums over that page, not the operations&apos; totals, and the ranking can change
                when the rest arrives.
              </>
            )}{" "}
            Errors are a count beside the calls themselves, never divided into them.
          </span>
        )
      }
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      <TableFrame fill className="rounded-none border-0">
        <Table>
          <TableHeader sticky>
            <TableRow>
              <TableHead>Operation</TableHead>
              <TableHead>Vendor</TableHead>
              <TableHead>Calls</TableHead>
              <TableHead>Errors</TableHead>
              <TableHead>Rung</TableHead>
              <TableHead>Over time</TableHead>
            </TableRow>
          </TableHeader>
          {!volume.telemetryAttached ? (
            <TableEmptyState
              columns={6}
              headline="Never measured."
              detail="No telemetry has been attached to this repository, so nothing has looked at its traffic. This is the absence of a measurement rather than a measurement of nothing — an operation with no calls here would look identical, and the two are not the same fact."
            />
          ) : volume.operations.length === 0 ? (
            <TableEmptyState
              columns={6}
              headline="Telemetry is attached and has seen no calls."
              detail={`Attached ${formatTimestamp(volume.attachedAt) ?? "at an unrecorded time"}. This is a measured nought: something looked and found no traffic, which is a different answer from never having looked.`}
            />
          ) : (
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
          )}
        </Table>
      </TableFrame>
    </PanelPane>
  )
}
