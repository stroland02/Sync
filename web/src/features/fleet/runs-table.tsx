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
import { FilterRail, type FilterGroup } from "@/components/filter-rail"
import { useFilterParam } from "@/lib/use-filter-param"
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
 * The disposition vocabulary as the rail offers it, in a fixed order the payload cannot vary.
 *
 * Built from the closed set rather than from `by_disposition`'s keys: the payload omits a
 * disposition no run has reached, and an option missing from the rail claims the value does
 * not exist in the vocabulary — where a zero count is a real answer worth selecting. The
 * `"in-flight"` value is the transport's word for the payload's `"null"` bucket.
 */
const OUTCOME_OPTIONS = [
  { value: "in-flight", label: "in flight", bucket: "null" },
  { value: "opened", label: "opened", bucket: "opened" },
  { value: "reported", label: "reported", bucket: "reported" },
  { value: "abandoned", label: "abandoned", bucket: "abandoned" },
] as const

/**
 * The rail's one facet, counted over every run the deployment holds — the payload computes
 * `by_disposition` before the outcome filter is applied, precisely so these figures say what
 * each selection would return rather than describing the page in view.
 */
function outcomeGroup(
  data: RunsPage,
  selected: string | null,
  onSelect: (value: string | null) => void,
): FilterGroup {
  const toOption = (option: (typeof OUTCOME_OPTIONS)[number]) => ({
    value: option.value,
    label: option.label,
    count: { kind: "counted" as const, value: data.by_disposition[option.bucket] ?? 0 },
  })
  return {
    id: "outcome",
    legend: "Disposition",
    selected,
    onSelect,
    unfiltered: {
      label: "Every run",
      count: { kind: "counted", value: data.unfiltered_total },
    },
    options: [toOption(OUTCOME_OPTIONS[0]), ...OUTCOME_OPTIONS.slice(1).map(toOption)],
  }
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
  // `useFilterParam` rather than `useFacetParam` plus a separate `setOffset`, and the difference
  // is a real defect rather than tidiness: both hooks call `setSearchParams`, and React Router
  // hands the functional form the *current* params rather than a queued value -- so two writes in
  // one handler give the second a `prev` that predates the first, and the offset reset discarded
  // the facet it was meant to accompany. The rail looked pressed and nothing was refetched, which
  // is the owner's report of 2026-08-19. One write does both.
  const [outcome, setSelectedOutcome] = useFilterParam("runs_outcome", ["runs_offset"])
  const query = useRuns({ limit: DEFAULT_LIMIT, offset, outcome })

  // A new narrowing starts at the first page: an offset kept from the previous selection can
  // sit past the narrowed set's end, which renders an empty page over a non-empty answer.
  // One write: the setter clears the offset itself.
  const setOutcome = setSelectedOutcome

  return (
    <div className="flex flex-col gap-section">
      {query.isPending && <LoadingState what="the fleet's runs" />}
      {query.error && <ErrorState error={query.error} what="the fleet's runs" onRetry={() => void query.refetch()} />}

      {query.isSuccess && (
        <div className="grid gap-section lg:grid-cols-[17rem_minmax(0,1fr)] lg:items-stretch">
        {/* The rail's counts and the table's record count answer two different questions — the
            rail is counted over every run the deployment holds (the payload computes it before
            the filter applies), the footer over the narrowed set — and each states its scope. */}
        <FilterRail
          label="Narrow the runs"
          countScope="Counted across every run this deployment holds, whichever option is pressed. The record count under the table describes the narrowed set."
          groups={[outcomeGroup(query.data, outcome, setOutcome)]}
        />
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
              screen that has none. */}
          <>
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
                  {query.data.items.length === 0 &&
                    (outcome !== null && query.data.unfiltered_total > 0 ? (
                      <TableEmptyRow colSpan={5}>
                        <span className="text-ink">No run matches this narrowing.</span> The
                        checkpointer holds {query.data.unfiltered_total} runs and none of them
                        carries this disposition — clear the rail's selection to see them.
                      </TableEmptyRow>
                    ) : (
                      <TableEmptyRow colSpan={5}>
                        <span className="text-ink">No run has ever checkpointed.</span> The API
                        answered, and the checkpointer holds no thread. That is an answer, not a
                        failure — nothing has attempted a repair on this database yet.
                      </TableEmptyRow>
                    ))}
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
                        {/* Liveness as a recorded word, in-flight rows only (B194). A chip
                            from a closed vocabulary, legible without colour — `expired` is a
                            stored transition the sweep wrote, never a per-render guess, and
                            `unmonitored` is the honest word for a run that predates the
                            heartbeat table. */}
                        {run.liveness !== null && (
                          <div className="mt-field">
                            <span className="furniture rounded-control border border-line px-field py-field text-meta text-ink-muted">
                              {run.liveness === "alive" && "process alive"}
                              {run.liveness === "expired" && "heartbeats stopped"}
                              {run.liveness === "unmonitored" && "not monitored"}
                            </span>
                            {run.liveness === "alive" && run.last_heartbeat_at !== null && (
                              <span className="ml-row font-mono text-meta text-muted-foreground">
                                <RelativeTime iso={run.last_heartbeat_at} />
                              </span>
                            )}
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

          {/* Amended 2026-08-18 with B194 rather than deleted: the checkpoint half is still
              true and still the reason "last checkpoint" is never read as liveness. What
              changed is that monitored runs now carry a second, separate signal, and the
              paragraph says exactly how far it reaches. */}
          <p className="max-w-prose border-t border-line pt-section text-body text-muted-foreground">
            A checkpoint records progress, not existence — "last checkpoint" is staleness, not
            liveness. A run parked at <code className="font-mono">await_ci</code> blocks inside
            that node while it waits on the customer's CI, and writes no checkpoint for as long
            as that takes, by design. What tells that run apart from one that died is the
            heartbeat: the runner's process says "still here" on a timer, straight through a CI
            wait, and a run whose heartbeats stop with no clean exit is recorded{" "}
            <span className="font-mono">expired</span> by a sweep — a stored transition, not a
            guess made at render time. A run marked <span className="font-mono">not monitored</span>{" "}
            predates that mechanism, and for it this screen still does not guess.
          </p>
        </MetricPanel>
        </div>
      )}
    </div>
  )
}
