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
import type { RunDisposition } from "@/api/types"
import { PageControls } from "@/components/page-controls"
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
import { formatElapsed, orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

/** "in flight" for a run with no disposition yet — never "running", which never arrives here. */
function describeOutcome(outcome: RunDisposition | null): string {
  return outcome === null ? "in flight" : outcome
}

export function RunsCard() {
  const [offset, setOffset] = useOffsetParam("runs_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset })

  return (
    <div className="flex flex-col gap-4">
      {query.isPending && <LoadingState what="the fleet's runs" />}
      {query.isError && <ErrorState error={query.error} what="the fleet's runs" />}

      {query.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle>
              {query.data.total} {query.data.total === 1 ? "run" : "runs"}
            </CardTitle>
            <CardDescription>
              One row per checkpoint thread, not one per finding — a finding retried across
              generations writes a new thread each generation, and each generation is its
              own row here.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {query.data.items.length === 0 ? (
              <EmptyState
                headline="No run has ever checkpointed."
                detail="The API answered, and the checkpointer holds no thread. That is an answer, not a failure — nothing has attempted a repair on this database yet."
              />
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Finding</TableHead>
                      <TableHead>Node the graph owes</TableHead>
                      <TableHead>Outcome</TableHead>
                      <TableHead>Last checkpoint</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {query.data.items.map((run) => (
                      <TableRow key={run.thread_id}>
                        <TableCell className="font-mono text-xs">
                          <Link
                            to={`/findings/${encodeURIComponent(run.finding_id)}/workflow`}
                            className="underline underline-offset-2"
                          >
                            {run.finding_id}
                          </Link>
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {orAbsent(run.current_node)}
                        </TableCell>
                        <TableCell>
                          {describeOutcome(run.outcome)}
                          {run.outcome === "abandoned" && (
                            <div className="mt-1 font-mono text-xs text-muted-foreground">
                              {orAbsent(run.abandon_reason)}
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {formatElapsed(run.last_checkpoint_at)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
                <PageControls
                  offset={offset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.items.length}
                  total={query.data.total}
                  nextOffset={query.data.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setOffset}
                />
              </>
            )}

            <p className="border-t border-border pt-3 text-sm text-muted-foreground">
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
