/**
 * The repair record, aggregated: every `migration_outcome` row the graph holds.
 *
 * `attempts` and `distinct_findings` render as two stat tiles rather than one combined
 * figure, because they are two different facts. `sync.remediate.corpus` writes one row per
 * attempt, so a finding retried three times is three attempts and one finding — a screen
 * that showed a single number for both would be the grain defect `CLAUDE.md` names for
 * this table.
 */

import { lazy, Suspense } from "react"

import { useCorpus } from "@/api/queries"
import type { Tally } from "@/api/types"
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

// Lazy so echarts and echarts-for-react — the corpus chart's only heavy
// dependency — land in their own chunk instead of the console's initial
// bundle.
const CorpusChart = lazy(() =>
  import("@/features/fleet/corpus-chart").then((mod) => ({ default: mod.CorpusChart })),
)

function TallyTable({ heading, tally }: { heading: string; tally: Tally }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex flex-col gap-row">
      <h3 className="furniture text-meta text-muted-foreground">{heading}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-meta">Value</TableHead>
            <TableHead className="text-meta">Attempts</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([value, count]) => (
            <TableRow key={value}>
              <TableCell className="font-mono text-body">{value}</TableCell>
              <TableCell className="font-mono text-body">{count}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function CorpusSummaryCard() {
  const query = useCorpus()

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the repair record" />}
      {query.isError && <ErrorState error={query.error} what="the repair record" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="text-emphasis">Repair record</CardTitle>
            <CardDescription className="text-body">
              Every repair attempt the graph has recorded, one row of{" "}
              <code className="font-mono">migration_outcome</code> per attempt. A finding
              retried three times writes three attempts here and counts once toward
              findings.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-section">
            {query.data.attempts === 0 ? (
              <EmptyState
                headline="The graph holds no repair attempts."
                detail="The API answered, and migration_outcome has no rows. That is an answer, not a failure — nothing has reached a patch attempt on this database yet."
              />
            ) : (
              <>
                <Suspense fallback={null}>
                  <CorpusChart data={query.data} />
                </Suspense>
                <div className="grid gap-section sm:grid-cols-3">
                  <TallyTable heading="By disposition" tally={query.data.by_terminal_status} />
                  <TallyTable heading="By strategy" tally={query.data.by_strategy} />
                  <TallyTable heading="By tier" tally={query.data.by_tier} />
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
