/**
 * The repair record, aggregated: every `migration_outcome` row the graph holds.
 *
 * `attempts` and `distinct_findings` are shown as two different numbers, because they are
 * two different facts. `sync.remediate.corpus` writes one row per attempt, so a finding
 * retried three times is three attempts and one finding — a screen that showed a single
 * number for both would be the grain defect `CLAUDE.md` names for this table.
 */

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

function TallyTable({ heading, tally }: { heading: string; tally: Tally }) {
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs tracking-wide text-muted-foreground uppercase">{heading}</h3>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Value</TableHead>
            <TableHead>Attempts</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([value, count]) => (
            <TableRow key={value}>
              <TableCell className="font-mono text-xs">{value}</TableCell>
              <TableCell className="font-mono text-xs">{count}</TableCell>
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
    <div className="flex flex-col gap-4">
      {query.isPending && <LoadingState what="the repair record" />}
      {query.isError && <ErrorState error={query.error} what="the repair record" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle>
              {query.data.attempts} {query.data.attempts === 1 ? "attempt" : "attempts"}{" "}
              across {query.data.distinct_findings}{" "}
              {query.data.distinct_findings === 1 ? "finding" : "findings"}
            </CardTitle>
            <CardDescription>
              Every repair attempt the graph has recorded, one row of{" "}
              <code className="font-mono">migration_outcome</code> per attempt. A finding
              retried three times writes three attempts here and counts once toward
              findings.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {query.data.attempts === 0 ? (
              <EmptyState
                headline="The graph holds no repair attempts."
                detail="The API answered, and migration_outcome has no rows. That is an answer, not a failure — nothing has reached a patch attempt on this database yet."
              />
            ) : (
              <div className="grid gap-4 sm:grid-cols-3">
                <TallyTable heading="By disposition" tally={query.data.by_terminal_status} />
                <TallyTable heading="By strategy" tally={query.data.by_strategy} />
                <TallyTable heading="By tier" tally={query.data.by_tier} />
              </div>
            )}

            <p className="border-t border-border pt-3 text-sm text-muted-foreground">
              This table holds nothing for a run abandoned before any attempt (at{" "}
              <code className="font-mono">locate</code> or{" "}
              <code className="font-mono">prepare</code>), for a run where no tier applied,
              or for a run whose state was missing its finding, site, or change — those runs
              are real, and the runs table above still names them through an abandon
              reason, but they leave no attempt for this table to count. A{" "}
              <code className="font-mono">null</code> row below is an attempt whose column
              was never written, not a count of zero.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
