/**
 * Every run the checkpointer holds, one row per thread.
 *
 * "One row per run" is the sentence this table exists to keep honest: a finding retried
 * across generations writes one checkpoint thread per generation, and this table does not
 * collapse them the way the single-finding workflow view does. Two generations of one
 * finding are two rows here, not one.
 *
 * No metric figure: the run total is the fact rail's second tile, and the only other number this
 * panel could lead with is a per-page tally, which is not a fleet-wide fact at all.
 */

import { Link } from "react-router"

import { DEFAULT_LIMIT } from "@/api/client"
import { hasLiveRun, useRuns } from "@/api/queries"
import type { RunDisposition, RunRow, RunsPage } from "@/api/types"
import {
  Table,
  TableBody,
  TableCell,
  TableEmptyRow,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/data-table"
import { FetchedAt } from "@/components/fetched-at"
import { MetricPanel } from "@/components/metric-panel"
import { RelativeTime } from "@/components/relative-time"
import { ErrorState, LoadingState } from "@/components/states"
import { Formatted } from "@/components/status"
import { FooterBar } from "@/layouts/footer-bar"
import {
  CardinalityStatement,
  describeCardinality,
  isCompleteListing,
} from "@/features/fleet/cardinality"
import { orAbsent } from "@/lib/format"
import { useOffsetParam } from "@/lib/use-offset-param"

/** "in flight" for a run with no disposition yet — never "running", which never arrives here. */
function describeOutcome(outcome: RunDisposition | null, isRehearsal = false): string {
  if (outcome === null) return "in flight"
  if (outcome === "reported" && isRehearsal) return "halted before the remote"
  return outcome
}

function isRehearsal(run: RunRow): boolean {
  return (
    run.run_id?.startsWith("rehearsal-") ??
    run.thread_id.split(":")[1]?.startsWith("rehearsal-") ??
    false
  )
}

/**
 * How many runs on the fetched page ended each way, or are still in flight. Counted over the
 * page this request returned, never over the fleet — `GET /api/runs` paginates and carries no
 * total-by-disposition figure, so a total here would have to be invented.
 */
function tallyDispositionsOnThisPage(items: readonly RunRow[]): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const run of items) {
    const key = describeOutcome(run.outcome, isRehearsal(run))
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

/**
 * The record count, written once so the paged and the complete branch cannot word it differently.
 * `shown` is the page's real size rather than the threshold, so the sentence never claims a slice
 * the table beneath it does not have.
 */
function RunsCount({ data }: { data: RunsPage }) {
  return (
    <CardinalityStatement
      text={describeCardinality(
        data.total,
        "run",
        "runs",
        "newest checkpoint first",
        data.items.length,
      )}
    />
  )
}

export function RunsCard() {
  const [offset, setOffset] = useOffsetParam("runs_offset")
  const query = useRuns({ limit: DEFAULT_LIMIT, offset })

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the fleet's runs" />}
      {query.error && <ErrorState error={query.error} what="the fleet's runs" onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <MetricPanel
          label="Runs"
          caption={
            <p className="max-w-prose">
              One row per checkpoint thread, not one per finding — a finding retried across
              generations writes a new thread each generation, and each generation is its
              own row here.
            </p>
          }
        >
          {/* Decision 61: the headers stay when there is nothing to list, so the shape of the
              data is legible before there is data and a reader learns what a run IS from a
              screen that has none. Only the disposition tally is row-dependent — it counts the
              rows, so with none it would be counting nothing. */}
          <>
            {query.data.items.length > 0 && (
              <div className="flex flex-col gap-field">
                <span className="furniture text-meta text-ink-muted">
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
            )}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Finding</TableHead>
                    <TableHead>Kind</TableHead>
                    <TableHead>Node the graph owes</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Last checkpoint</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.length === 0 && (
                    <TableEmptyRow colSpan={5}>
                      <span className="text-ink">No run has ever checkpointed.</span>{" "}
                      The API answered, and the checkpointer holds no thread. That is an answer,
                      not a failure — nothing has attempted a repair on this database yet.
                    </TableEmptyRow>
                  )}
                  {query.data.items.map((run) => (
                    <TableRow key={run.thread_id}>
                      <TableCell className="font-mono">
                        {/* Workspace-scoped, because `/findings/:id/workflow` is not a route the
                            router serves. Without a repository there is no scoped address to
                            build, and guessing one would send a reader to another workspace's
                            finding — so the id is stated and not linked. */}
                        {run.repo_id === null ? (
                          run.finding_id
                        ) : (
                          <Link
                            to={`/repositories/${encodeURIComponent(run.repo_id)}/findings/${encodeURIComponent(run.finding_id)}/workflow`}
                            className="underline underline-offset-2"
                          >
                            {run.finding_id}
                          </Link>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-meta">
                        {isRehearsal(run) ? "rehearsal" : "live"}
                      </TableCell>
                      <TableCell className="font-mono">
                        <Formatted value={orAbsent(run.current_node)} />
                      </TableCell>
                      <TableCell>
                        {describeOutcome(run.outcome, isRehearsal(run))}
                        {run.outcome === "abandoned" && (
                          <div className="mt-field font-mono text-meta text-muted-foreground">
                            <Formatted value={orAbsent(run.abandon_reason)} />
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="font-mono text-meta">
                        <RelativeTime iso={run.last_checkpoint_at} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {/* One footer on both branches. The pager is what the branch decides, not the
                  footer: a set that fits on one page has no page to move to, and page controls
                  over it are a choice nobody has. The cardinality sentence is the record count
                  either way, and it now has somewhere to sit when the set is complete. */}
              {isCompleteListing(query.data.total) ? (
                <FooterBar left={<RunsCount data={query.data} />} />
              ) : (
                <FooterBar
                  offset={offset}
                  limit={DEFAULT_LIMIT}
                  shown={query.data.items.length}
                  total={query.data.total}
                  nextOffset={query.data.next_offset}
                  busy={query.isFetching}
                  onOffsetChange={setOffset}
                  left={<RunsCount data={query.data} />}
                />
              )}
          </>

          {/* The console's own fetch time, which is a different claim from the run liveness the
              paragraph below refuses to make: this says when we last asked, not whether anything
              is alive. Without it the table cannot answer "when was this true?", and a reviewer
              who cannot answer that will either distrust fresh rows or act on stale ones. */}
          <FetchedAt
            at={query.dataUpdatedAt}
            polling={hasLiveRun(query.data)}
            idleReason="Every run here has reached an outcome, so nothing is being polled."
            className="mt-section"
          />

          <p className="max-w-prose border-t border-line pt-section text-body text-muted-foreground">
            There is no heartbeat and no process registry — the only evidence a run exists
            is a checkpoint row, and "last checkpoint" is staleness, not liveness. A run
            parked at <code className="font-mono">await_ci</code> blocks inside that node
            while it waits on the customer's CI, and writes no checkpoint for as long as
            that takes, by design. A run parked at any other node with the same silence
            has probably died. Nothing in this data tells the two apart, so this screen
            does not guess: there is no dot and no colour here, because a wrong guess
            would be a confident wrong verdict.
          </p>
        </MetricPanel>
      )}
    </div>
  )
}
