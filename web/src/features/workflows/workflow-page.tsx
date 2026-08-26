/**
 * The Solution Workflow: what Sync did about one finding, and what checked it — both at once.
 *
 * **A locked, two-pane screen with no tabs.** It was a narrow fact rail beside a tabbed single
 * column, which meant a reviewer could read the transcript or the output but never both, and the
 * one question this screen exists to answer — *does the evidence support the change?* — needed the
 * two halves side by side. Evidence left, remediation right, each pane scrolling its own body under
 * a header that holds still. The tabs are gone entirely: nothing here narrows anything, so the
 * controls band is omitted rather than reserved empty.
 *
 * Read from the LangGraph checkpointer, a different database from the API Dependency Graph, so this
 * route carries no provenance envelope — no `indexed_at`, no binding rung, no vendor, and nothing
 * invented to fill the gap. No per-node elapsed time exists in any checkpoint it reads (B123) and a
 * superseded generation is not reachable from it (B124): `GET /api/workflows/{finding_id}` answers
 * with the newest thread only.
 *
 * The heading is the registry's "Solution workflow" rather than the finding's own name — a ruling
 * recorded in `lib/detail-title.tsx`: the name is not on this payload, and fetching it would put
 * the page's focal point behind a query that 404s for every patched or abandoned finding.
 */

import { useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { WORKFLOW_POLL_MS, isRunTerminal, useWorkflow } from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { FetchedAt } from "@/components/fetched-at"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { activityEntries, omittedCount } from "@/features/workflows/activity"
import { EvidencePane } from "@/features/workflows/evidence-pane"
import { RemediationPane } from "@/features/workflows/remediation-pane"
import { RunIdentityHeader } from "@/features/workflows/run-identity-header"
import { WorkflowKpis } from "@/features/workflows/workflow-kpis"
import { ScreenFrame } from "@/layouts/screen-frame"
import { SplitPanes } from "@/layouts/split-panes"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"

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
 * A failed refetch does not stop the poll on a live run and does not start one on a finished run,
 * so the band states both axes rather than collapsing them into "stale".
 */
function pollNote(terminal: boolean, refreshFailed: boolean): string | null {
  if (refreshFailed) {
    return terminal
      ? "Could not refresh, and the run reached a terminal outcome, so nothing is polling in the background — these are the last figures the console read."
      : `Could not refresh — these are the last figures the console read, and polling continues every ${WORKFLOW_POLL_MS / 1000} seconds.`
  }
  // `FetchedAt`'s `idleReason` already states the terminal case in the header row, so the band
  // carries only what that does not — one of the two, never both.
  return terminal ? null : `Re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`
}

/**
 * What this route can count, plus the run's own last word.
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
    {
      // The reference puts a "Breaking Change Detected" severity chip beside the incident id. The
      // finding's change kind is not on this payload and fetching it would put the header's focal
      // point behind a route that 404s for every patched or abandoned finding. The run's own
      // recorded disposition is the honest figure in that position: a value from a closed
      // vocabulary, legible without colour, permanently visible under a locked viewport.
      kind: "figure",
      label: "Outcome",
      value: state.outcome ?? null,
      scope: "the checkpointer's last word; the reason sits in the sequence where the run stopped",
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
    <ScreenFrame
      status={status}
      layout="locked"
      subtitle="What Sync's remediation graph did about this finding, and what checked the patch it wrote."
    >
      <WorkflowKpis data={data} />

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
          <ErrorState
            error={query.error}
            what={`the run for finding ${findingId}`}
            onRetry={() => void query.refetch()}
          />
        ))}

      {data !== undefined && (
        <SplitPanes
          header={
            <RunIdentityHeader
              repoId={repoId}
              findingId={findingId}
              data={data}
              trailing={
                query.isError ? (
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
                )
              }
            />
          }
          left={<EvidencePane repoId={repoId} findingId={findingId} data={data} />}
          right={<RemediationPane repoId={repoId} findingId={findingId} data={data} />}
        />
      )}
    </ScreenFrame>
  )
}
