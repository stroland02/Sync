/**
 * The Solution Workflow: what Sync actually did about one finding, node by node.
 *
 * Read from the LangGraph checkpointer, a different database from the API Dependency Graph, so this
 * route carries no provenance envelope — no `indexed_at`, no binding rung, and nothing invented to
 * fill the gap. No per-node elapsed time exists in any checkpoint it reads (B123) and a superseded
 * generation is not reachable from it (B124): `GET /api/workflows/{finding_id}` answers with the
 * newest thread only.
 *
 * The title is "Run N" and not the finding's own name — a ruling, recorded in `lib/detail-title.tsx`:
 * the name is not on this payload, and fetching it would put the page's only focal point behind a
 * query that 404s for every patched or abandoned finding. Mapping table for the port:
 * `docs/superpowers/briefs/2026-08-07-substrate-workflow.md`.
 */

import { FetchedAt } from "@/components/fetched-at"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { WORKFLOW_POLL_MS, isRunTerminal, useWorkflow } from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { activityEntries, omittedCount } from "@/features/workflows/activity"
import { ActivityTimeline } from "@/features/workflows/activity-timeline"
import { AgentActivityPanel } from "@/features/workflows/agent-activity-panel"
import { NodeSequence } from "@/features/workflows/node-sequence"
import { ReplyBox } from "@/features/workflows/reply-box"
import { RunFactRail } from "@/features/workflows/run-fact-rail"
import { runIdentity } from "@/features/workflows/run-identity"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { SettledOutput } from "@/features/workflows/settled-output"
import { SupersededGenerations } from "@/features/workflows/superseded-generations"
import { DetailGrid } from "@/layouts/detail-grid"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/vendor/supabase/ui/tabs"


import { findingHref } from "@/lib/hrefs"
const NODE_BY_NODE_INTRO =
  "Eight nodes, in the order the graph wires them. A standing is the checkpoint's own answer — nothing here says a node is executing."

export interface WorkflowPageProps {
  readonly question?: string
}

export function WorkflowPage() {
  const { repoId, findingId } = useParams<{ repoId: string; findingId: string }>()
  if (repoId === undefined || findingId === undefined) return <UnknownRoute />
  return <Workflow repoId={repoId} findingId={findingId} />
}

/**
 * A background refetch failed, but the last good run is still in hand — React Query keeps `data`
 * across a failed refetch.
 *
 * Only a terminal run gets the retry button: a live run is still being polled, so the next
 * successful hit clears this on its own.
 */
function StaleBanner({
  fetchedAt,
  live,
  isFetching,
  onRetry,
}: {
  fetchedAt: number
  live: boolean
  isFetching: boolean
  onRetry: () => void
}) {
  return (
    <div
      role="status"
      className="rounded-surface border border-border bg-muted p-section text-body text-muted-foreground"
    >
      <p className="max-w-prose">
        Could not refresh. Showing the run as of{" "}
        <Formatted value={formatTimestamp(new Date(fetchedAt).toISOString())} /> —{" "}
        {live
          ? "the run is still live, so polling continues in the background and this will clear on its own once a request succeeds."
          : "the run has reached a terminal outcome, so nothing is polling in the background."}
      </p>
      {!live && (
        <Button
          variant="outline"
          size="sm"
          className="mt-row"
          disabled={isFetching}
          onClick={onRetry}
        >
          {isFetching ? "Asking…" : "Check again"}
        </Button>
      )}
    </div>
  )
}

/**
 * What `RunOutcome` may say about this screen, which renders all eight nodes as a narrative and
 * places the outcome inside the sequence rather than above it. The panel does not know that; this
 * page does, so the sentences that depend on position live here.
 */
const BELOW: BelowThisPanel = {
  inFlight: `Every entry here is the last state the checkpointer recorded, re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`,
  abandoned:
    "The attempt is still here in full: the entries above this one are what ran, with everything each node produced, and any entry after it is a node the run never reached.",
  opened: (
    <>
      The pull request is under <code>open_pr</code>.
    </>
  ),
  unrecognised: "The entries here are still what the run produced.",
}

/**
 * The narrative's opening entry: what arrived, and what this screen can and cannot see about it.
 */
function Arrival({ repoId, findingId }: { repoId: string; findingId: string }) {
  return (
    <>
      <h3 className="text-emphasis">What arrived</h3>
      <div className="mt-row flex max-w-prose flex-col gap-row text-body text-muted-foreground">
        <p>A finding arrived from the API Dependency Graph, and this run is what Sync did about it.</p>
        <p>
          Read from the checkpointer, which is a different database from the API Dependency
          Graph — this screen carries no indexing timestamp and no binding rung for that reason.{" "}
          <Link
            to={findingHref(repoId, findingId)}
            className="underline underline-offset-2"
          >
            The finding itself
          </Link>{" "}
          carries both.
        </p>
        <p>
          The entries below are the remediation graph's own order, with the evidence each node
          produced. A node marked due after it has already run is a retry the graph owes another
          visit, not a finished step — the loop is real and this view does not hide it.
        </p>
      </div>
    </>
  )
}

/**
 * A failed refetch does not stop the poll on a live run and does not start one on a finished run,
 * so the band states both axes rather than collapsing them into "stale".
 */
function pollNote(terminal: boolean, refreshFailed: boolean): string | null {
  if (refreshFailed) {
    return terminal
      ? "Could not refresh, and the run reached a terminal outcome, so nothing is polling in the background — these are the last figures the console read."
      : `Could not refresh — these are the last figures the console read, and polling continues every ${WORKFLOW_POLL_MS / 1000} seconds.`
  }
  // `FetchedAt`'s `idleReason` already states the terminal case in the content column, so the band
  // carries only what that does not — one of the two, never both.
  return terminal ? null : `Re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`
}

/**
 * The two things this route can count, both read off the one payload that answers for either.
 *
 * A run whose node list is genuinely empty counts `0`; a run nothing has answered for is absent and
 * the caller renders `none` instead.
 */
function runStatus(
  state: WorkflowState,
  terminal: boolean,
  refreshFailed: boolean,
): StatusSegment[] {
  const omitted = omittedCount(state)

  return [
    {
      kind: "figure",
      label: "Nodes",
      value: state.nodes.length.toLocaleString(),
      scope: "the remediation graph's own list, whether or not the run reached each one",
    },
    {
      kind: "figure",
      label: "Timeline entries",
      value: activityEntries(state).length.toLocaleString(),
      // `activityEntries` is the stamped nodes PLUS one closing entry once the run has an outcome,
      // so nodes minus omitted does not reconcile on any terminal run -- which is most of them.
      scope: [
        omitted === 0
          ? "every node wrote a checkpoint timestamp"
          : omitted === 1
            ? "one node wrote no checkpoint timestamp and has no entry — absence, not zero"
            : `${omitted} nodes wrote no checkpoint timestamp and have no entry — absence, not zero`,
        terminal ? "and the run's outcome adds one entry of its own" : null,
      ]
        .filter(Boolean)
        .join(", "),
    },
    ...(pollNote(terminal, refreshFailed) === null
      ? []
      : [{ kind: "note" as const, text: pollNote(terminal, refreshFailed)! }]),
  ]
}

function Workflow({ repoId, findingId }: { repoId: string; findingId: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  const terminal = isRunTerminal(data)

  // Short: the content column states the same case in full. Each still says which nothing it is.
  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>no run for this finding</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  // Built for every state the query can be in: a band that appears on success alone renders
  // "nothing has been asked yet" and "asked, and this run holds nothing" as the same blank strip.
  const status: StatusSegment[] =
    data === undefined
      ? [
          {
            kind: "none",
            why: query.isError
              ? query.error instanceof NotFoundError
                ? "the checkpointer holds no run for this finding"
                : "the run did not answer"
              : "asking the checkpointer for this run",
          },
        ]
      : runStatus(data, terminal, query.isError)

  return (
    /* The tab list publishes into the controls band, outside the pane it switches: Radix carries
       selection through context rather than nesting, so the root may wrap the whole frame. */
    <Tabs defaultValue="activity" className="flex min-w-0 flex-col gap-8">
      <ScreenFrame
        status={status}
        controls={
          data === undefined ? undefined : (
            <TabsList className="gap-section">
              <TabsTrigger value="activity">Activity</TabsTrigger>
              <TabsTrigger value="findings">Findings</TabsTrigger>
            </TabsList>
          )
        }
      >
        <DetailGrid
          railSide="narrow"
          rail={<RunFactRail repoId={repoId} findingId={findingId} data={data} failure={failure} />}
        >
          <div className="flex min-w-0 flex-col gap-8">
            {query.isPending && <LoadingState what={`the run for finding ${findingId}`} />}

            {data === undefined &&
              query.isError &&
              (query.error instanceof NotFoundError ? (
                <div className="flex flex-col items-start gap-section">
                  <NotFoundState
                    headline="No remediation run for this finding."
                    detail="The API answered, and the checkpointer holds no run under this identifier. Either remediation has not been started for this finding, or it has never been started for any finding on this database. This is an answer about the run, not a failure of the console — a finding can be perfectly real and have no attempt against it yet."
                    identifier={query.error.identifier}
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={query.isFetching}
                    onClick={() => void query.refetch()}
                  >
                    {query.isFetching ? "Asking…" : "Check again"}
                  </Button>
                </div>
              ) : (
                <ErrorState error={query.error} what={`the run for finding ${findingId}`} onRetry={() => void query.refetch()} />
              ))}

            {data !== undefined && (
              <>
                {query.isError ? (
                  <StaleBanner
                    fetchedAt={query.dataUpdatedAt}
                    live={!terminal}
                    isFetching={query.isFetching}
                    onRetry={() => void query.refetch()}
                  />
                ) : (
                  <FetchedAt
                    at={query.dataUpdatedAt}
                    polling={!terminal}
                    idleReason="This run has reached a terminal outcome, so nothing is being polled."
                  />
                )}

                <AgentActivityPanel repoId={repoId} findingId={findingId} run={data} />

                <TabsContent value="activity" className="flex min-w-0 flex-col gap-8">
                  <MetricPanel label="Node by node" caption={NODE_BY_NODE_INTRO}>
                    <NodeSequence
                      nodes={data.nodes}
                      outcome={data.outcome}
                      opening={<Arrival repoId={repoId} findingId={findingId} />}
                      closing={
                        <RunOutcome
                          outcome={data.outcome}
                          abandonReason={data.abandon_reason}
                          reportReason={data.report_reason}
                          below={BELOW}
                          frame="entry"
                        />
                      }
                    />
                  </MetricPanel>

                  <ActivityTimeline state={data} />

                  <ReplyBox waitingOn={data === undefined ? null : runIdentity(data).waitingOn} />
                </TabsContent>

                <TabsContent value="findings" className="flex min-w-0 flex-col gap-8">
                  <SettledOutput repoId={repoId} findingId={findingId} state={data} />

                  <SupersededGenerations
                    generations={data.generations}
                    currentThreadId={data.thread_id}
                  />
                </TabsContent>
              </>
            )}
          </div>
        </DetailGrid>
      </ScreenFrame>
    </Tabs>
  )
}
