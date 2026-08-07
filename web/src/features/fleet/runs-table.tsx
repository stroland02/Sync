/**
 * Every run the checkpointer holds, one row per thread.
 *
 * "One row per run" is the sentence this table exists to keep honest: a finding retried
 * across generations writes one checkpoint thread per generation, and this table does not
 * collapse them the way the single-finding workflow view does. Two generations of one
 * finding are two rows here, not one.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { useRuns } from "@/api/queries"
import type { RunDisposition, RunRow } from "@/api/types"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { FooterBar } from "@/layouts/footer-bar"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  CardinalityStatement,
  describeCardinality,
  isCompleteListing,
} from "@/features/fleet/cardinality"
import { formatElapsed, orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

/** "in flight" for a run with no disposition yet — never "running", which never arrives here. */
function describeOutcome(outcome: RunDisposition | null): string {
  return outcome === null ? "in flight" : outcome
}

/**
 * How many runs on the fetched page ended each way, or are still in flight. Counted over the
 * page this request returned, never over the fleet — `GET /api/runs` paginates and carries no
 * total-by-disposition figure, so a total here would have to be invented.
 */
function tallyDispositionsOnThisPage(items: readonly RunRow[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const run of items) {
    const key = describeOutcome(run.outcome)
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

export function RunsCard() {
  const [offset, setOffset] = useOffsetParam("runs_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset })

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the fleet's runs" />}
      {query.isError && <ErrorState error={query.error} what="the fleet's runs" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            {/* Same as the vendor panel: the total is in the fact rail now, and the cardinality
                sentence in the footer states it again with the ordering and the slice. Three
                copies of one number was two too many. */}
            <CardTitle className="text-emphasis">Runs</CardTitle>
            <CardDescription className="max-w-prose text-body">
              One row per checkpoint thread, not one per finding — a finding retried across
              generations writes a new thread each generation, and each generation is its
              own row here.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-section">
            {query.data.items.length === 0 ? (
              <EmptyState
                headline="No run has ever checkpointed."
                detail="The API answered, and the checkpointer holds no thread. That is an answer, not a failure — nothing has attempted a repair on this database yet."
              />
            ) : (
              <>
                <div className="flex flex-col gap-field">
                  <span className="furniture text-meta text-muted-foreground">
                    By disposition, this page only
                  </span>
                  <p className="font-mono text-body">
                    {Object.entries(tallyDispositionsOnThisPage(query.data.items))
                      .sort(([a], [b]) => a.localeCompare(b))
                      .map(([outcome, count]) => `${outcome}: ${count}`)
                      .join(", ")}
                  </p>
                  <p className="max-w-prose text-meta text-muted-foreground">
                    Counted across the {query.data.items.length} runs shown below, not the
                    fleet — the fleet's true disposition mix is not in this payload.
                  </p>
                </div>
                {/* Below the threshold the cardinality sentence stands alone: `FooterBar` would
                    render page controls for a set that fits on one page, which is a choice nobody
                    has. Above it, the sentence moves into the footer's `left` slot, which is what
                    that slot is for — what the count is counted over. */}
                {isCompleteListing(query.data.total) && (
                  <CardinalityStatement
                    text={describeCardinality(
                      query.data.total,
                      "run",
                      "runs",
                      "newest checkpoint first",
                      query.data.items.length,
                    )}
                  />
                )}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-meta">Finding</TableHead>
                      <TableHead className="text-meta">Node the graph owes</TableHead>
                      <TableHead className="text-meta">Outcome</TableHead>
                      <TableHead className="text-meta">Last checkpoint</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {query.data.items.map((run) => (
                      <TableRow key={run.thread_id}>
                        <TableCell className="font-mono text-body">
                          <Link
                            to={`/findings/${encodeURIComponent(run.finding_id)}/workflow`}
                            className="underline underline-offset-2"
                          >
                            {run.finding_id}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-body">
                          <Formatted value={orAbsent(run.current_node)} />
                        </TableCell>
                        <TableCell className="text-body">
                          {describeOutcome(run.outcome)}
                          {run.outcome === "abandoned" && (
                            <div className="mt-field font-mono text-meta text-muted-foreground">
                              <Formatted value={orAbsent(run.abandon_reason)} />
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-meta">
                          <Formatted value={formatElapsed(run.last_checkpoint_at)} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                {!isCompleteListing(query.data.total) && (
                  <FooterBar
                    offset={offset}
                    limit={DEFAULT_LIMIT}
                    shown={query.data.items.length}
                    total={query.data.total}
                    nextOffset={query.data.next_offset}
                    busy={query.isFetching}
                    onOffsetChange={setOffset}
                    left={
                      <CardinalityStatement
                        text={describeCardinality(
                          query.data.total,
                          "run",
                          "runs",
                          "newest checkpoint first",
                          query.data.items.length,
                        )}
                      />
                    }
                  />
                )}
              </>
            )}

            <p className="max-w-prose border-t border-border pt-section text-body text-muted-foreground">
              There is no heartbeat and no process registry — the only evidence a run exists
              is a checkpoint row, and "last checkpoint" is staleness, not liveness. A run
              parked at <code className="font-mono">await_ci</code> blocks inside that node
              while it waits on the customer's CI, and writes no checkpoint for as long as
              that takes, by design. A run parked at any other node with the same silence
              has probably died. Nothing in this data tells the two apart, so this screen
              does not guess: there is no dot and no colour here, because a wrong guess
              would be a confident wrong verdict.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
