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

import { Link } from "react-router"

import { useDetectors } from "@/api/queries"
import type { BindingSource, DetectorRow, Tally } from "@/api/types"
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
import { describeRung } from "@/lib/format"

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
    <div className="flex flex-col gap-2">
      <h3 className="text-meta uppercase tracking-wide text-muted-foreground">{heading}</h3>
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
              <TableCell className="font-mono text-body" title={tooltipFor?.(value)}>
                {value}
              </TableCell>
              <TableCell className="font-mono text-body">{count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DetectorCard({ row }: { row: DetectorRow }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="font-mono text-emphasis">{row.detector}</CardTitle>
        <CardDescription className="text-body">
          {row.total} open {row.total === 1 ? "finding" : "findings"} currently attributed
          to this detector.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <TallyTable heading="By rung" tally={row.by_rung} tooltipFor={rungTooltip} />
          <TallyTable heading="By claim" tally={row.by_claim} />
          <TallyTable heading="By severity" tally={row.by_severity} />
        </div>
        {/* No route filters an open finding by the detector that raised it -- that
            attribution exists nowhere else in the console before this screen. The link
            below is real and goes to real findings; it is just not scoped to this row,
            and the sentence says so rather than letting the link imply otherwise. */}
        <p className="text-meta text-muted-foreground">
          No route filters findings by detector yet.{" "}
          <Link to="/codebase" className="underline underline-offset-2">
            Browse every open finding
          </Link>{" "}
          instead.
        </p>
      </CardContent>
    </Card>
  )
}

export function DetectorAccountability() {
  const query = useDetectors()

  if (query.isPending) return <LoadingState what="detector accountability" />
  if (query.isError) return <ErrorState error={query.error} what="detector accountability" />

  const { detectors, total_open_findings } = query.data

  return (
    <div className="flex flex-col gap-4">
      {detectors.length === 0 ? (
        <EmptyState
          headline="No open finding is attributed to any detector."
          detail="The API answered, and the graph holds no open findings right now. That is an answer, not a failure -- nothing indexed is currently flagged by any detector."
        />
      ) : (
        <>
          <p className="text-body text-muted-foreground">
            {total_open_findings} open {total_open_findings === 1 ? "finding" : "findings"}{" "}
            across {detectors.length} {detectors.length === 1 ? "detector" : "detectors"}.
          </p>
          {detectors.map((row) => (
            <DetectorCard key={row.detector} row={row} />
          ))}
        </>
      )}
    </div>
  )
}
