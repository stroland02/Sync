/**
 * One card per detector: how many open findings, at which rungs, with what claims and
 * severities.
 *
 * The rung table on each card is the point, not an incidental column. `CLAUDE.md` requires
 * a false positive be attributable to the rung that produced it, and this is where that
 * attribution has to land: a detector whose findings rest entirely on `static` is making a
 * claim of one kind, and one mixing `static` and `observed` is making two different kinds
 * of claim under one name.
 *
 * Order is whatever `GET /api/detectors` returns -- alphabetical by detector name, which is
 * how `sync.dashboard.graph_views.detector_accountability` already sorts it -- and nothing
 * here re-sorts by total. Sorting by count is what turns a roll-up into a leaderboard, and
 * detectors are not competing: more findings is neither better nor worse than fewer.
 */

import { Suspense, lazy, useMemo } from "react"
import { Link } from "react-router"

import { useDetectors } from "@/api/queries"
import type { BindingSource, DetectorRow, Tally } from "@/api/types"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { rungComposition } from "@/features/detectors/rung-series"
import { describeRung, orAbsent } from "@/lib/format"

/**
 * `echarts` is ~1.1 MB minified and this screen is one of nine. Lazy, so it lands in its own
 * chunk and never in the initial bundle — the same arrangement `corpus-summary.tsx` makes, and
 * `vite.config.ts`'s `chunkSizeWarningLimit` comment carries why the warning it raises is
 * expected. `fallback={null}` rather than a placeholder: the cards below are the same numbers,
 * already on screen, so nothing is waiting on this.
 */
const RungCompositionChart = lazy(() =>
  import("@/features/detectors/rung-composition-chart").then((mod) => ({
    default: mod.RungCompositionChart,
  })),
)

function isBindingSource(value: string): value is BindingSource {
  return (
    value === "static" ||
    value === "resolved" ||
    value === "observed" ||
    value === "unresolved" ||
    value === "unattributed"
  )
}

/** A tooltip naming what the rung claims, for the one tally whose keys are the rung vocabulary. */
function rungTooltip(key: string): string | undefined {
  return isBindingSource(key) ? describeRung(key) : undefined
}

function TallyTable({
  heading,
  tally,
  tooltipFor,
}: {
  heading: string
  tally: Tally
  tooltipFor?: (key: string) => string | undefined
}) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex flex-col gap-row">
      <h3 className="furniture text-meta text-muted-foreground">{heading}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-meta">Value</TableHead>
            <TableHead className="text-meta">Findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([value, count]) => (
            <TableRow key={value}>
              {/* `value` is a tally key straight from the payload -- an empty string is a
                  real, distinct key (a claim or a severity nothing named), not a missing
                  cell, so it takes the same absence mark as every other unnamed value
                  rather than rendering as blank space with no mark at all. */}
              <TableCell className="font-mono text-body" title={tooltipFor?.(value)}>
                <Formatted value={orAbsent(value)} />
              </TableCell>
              <TableCell className="font-mono text-body">{count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DetectorCard({ row, repoId }: { row: DetectorRow; repoId: string | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-mono text-emphasis">{row.detector}</CardTitle>
        <CardDescription className="text-body">
          {/* Weight carries the count, not a size step: this card repeats once per
              detector, so a stat-tile figure here would cost a row on every one of them. */}
          <span className="font-semibold text-foreground tabular-nums">{row.total}</span> open{" "}
          {row.total === 1 ? "finding" : "findings"} currently attributed to this detector.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-section">
        <div className="grid gap-section sm:grid-cols-3">
          <TallyTable heading="By rung" tally={row.by_rung} tooltipFor={rungTooltip} />
          <TallyTable heading="By claim" tally={row.by_claim} />
          <TallyTable heading="By severity" tally={row.by_severity} />
        </div>
        {/* No route filters an open finding by the detector that raised it -- that
            attribution exists nowhere else in the console before this screen. The link
            below is real and goes to real findings; it is just not scoped to this row,
            and the sentence says so rather than letting the link imply otherwise. */}
        <p className="max-w-prose text-meta text-muted-foreground">
          No route filters findings by detector yet. Every open finding, by vendor, is on{" "}
          {repoId === null ? (
            <Link to="/" className="underline underline-offset-2">
              the fleet screen
            </Link>
          ) : (
            <Link
              to={`/repositories/${encodeURIComponent(repoId)}`}
              className="underline underline-offset-2"
            >
              this repository's own screen
            </Link>
          )}{" "}
          instead.
        </p>
      </CardContent>
    </Card>
  )
}

/**
 * The one chart on this screen, and the sentences that keep it honest.
 *
 * Every bar is full width and carries one detector's composition; the count it is a share of is
 * printed beside the detector's name rather than encoded as length. Both facts are said below
 * rather than left to be inferred, because a stacked bar is exactly where a reader starts
 * reading length as quantity and then as quality.
 */
function RungComposition({ rows }: { rows: DetectorRow[] }) {
  const composition = useMemo(() => rungComposition(rows), [rows])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-emphasis">What these claims rest on</CardTitle>
        <CardDescription className="max-w-prose text-body">
          Every open finding in this scope, split by the rung of evidence behind it, one bar per
          detector. The same counts are in each detector's own <code className="font-mono">By
          rung</code> table below; this is the one view where they can be compared across
          detectors without arithmetic.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-section">
        <Suspense fallback={null}>
          <RungCompositionChart composition={composition} />
        </Suspense>
        <p className="max-w-prose text-body text-muted-foreground">
          Every bar is the same length because it is a composition, not a quantity: the segments
          are that detector's own findings split by rung, and the number of findings they are a
          share of is printed beside the detector's name. Volume is not encoded here at all —
          one detector on this screen can hold four figures' worth of findings and another
          three, and drawing that as length would render the smaller ones as a sliver
          indistinguishable from nothing.
        </p>
        <p className="max-w-prose text-body text-muted-foreground">
          The rung is a class of evidence, not a position on a good-to-bad scale, so no colour
          here grades anything: each is an identity, and each is named in the legend, in the
          segment where it fits, and in the table beneath. A detector resting entirely on{" "}
          <code className="font-mono">static</code> is not doing worse than one correlating
          watched traffic — it is making a different kind of claim, which is the thing an
          operator weighing a false positive needs first.
        </p>
        {composition.absentRungs.length > 0 && (
          <p className="max-w-prose text-body text-muted-foreground">
            Nothing in this scope rests on{" "}
            {composition.absentRungs.map((rung, index) => (
              <span key={rung}>
                {index > 0 && (index === composition.absentRungs.length - 1 ? " or " : ", ")}
                <code className="font-mono">{rung}</code>
              </span>
            ))}
            . Those rungs keep their place in the legend and draw no segment — an absence, which
            is not the same fact as a rung this console does not have.
          </p>
        )}
        {composition.unrecognisedRungs.length > 0 && (
          <p className="max-w-prose text-body text-muted-foreground">
            One series counts findings whose rung this console does not recognise:{" "}
            {composition.unrecognisedRungs.map((rung, index) => (
              <span key={rung}>
                {index > 0 && ", "}
                <code className="font-mono">{rung}</code>
              </span>
            ))}
            . They are counted rather than dropped, so the bars still sum to each detector's own
            total — the provenance vocabulary has grown since this view was written.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function DetectorAccountability({ repoId = null }: { repoId?: string | null }) {
  const query = useDetectors(repoId ?? undefined)

  if (query.isPending) return <LoadingState what="detector accountability" />
  if (query.isError) return <ErrorState error={query.error} what="detector accountability" />

  const { detectors, total_open_findings } = query.data

  return (
    <div className="flex flex-col gap-8">
      {detectors.length === 0 ? (
        <EmptyState
          headline={
            repoId === null
              ? "No open finding is attributed to any detector."
              : `No open finding in ${repoId} is attributed to any detector.`
          }
          detail="The API answered, and the graph holds no open findings in this scope right now. That is an answer, not a failure -- nothing indexed here is currently flagged by any detector."
        />
      ) : (
        <>
          <p className="flex flex-wrap items-baseline gap-field text-body text-muted-foreground">
            <span className="text-figure text-foreground">{total_open_findings}</span>
            <span>
              open {total_open_findings === 1 ? "finding" : "findings"} across{" "}
              {detectors.length} {detectors.length === 1 ? "detector" : "detectors"}.
            </span>
          </p>
          <RungComposition rows={detectors} />
          <div className="flex flex-col gap-section">
            {detectors.map((row) => (
              <DetectorCard key={row.detector} row={row} repoId={repoId} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
