/**
 * The Solution Workflow: what Sync actually did about one finding, node by node.
 *
 * Competing tools show a black box and a verdict, and ask a reviewer to trust the verdict.
 * Sync checkpoints every node of its remediation graph, so this screen can show the run
 * itself — which node ran, which one the graph owes a visit, which never started, and what
 * each one produced. Everything else in this console exists to get a reviewer here.
 *
 * The route carries no provenance envelope, unlike the other four. It reads the LangGraph
 * checkpointer tables and the rest read the graph; they are two databases, so there is no
 * `indexed_at` and no rung to report and nothing is invented to fill the gap.
 */

import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { isRunTerminal, useWorkflow } from "@/api/queries"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { NodeSequence } from "@/features/workflows/node-sequence"
import { RunOutcome } from "@/features/workflows/run-outcome"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"
import { formatTimestamp } from "@/lib/format"

export function WorkflowPage() {
  // The identifier comes out of the URL, so it is checked before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <Workflow findingId={findingId} />
}

/**
 * A background refetch failed, but the last good run is still in hand.
 *
 * React Query keeps `data` across a failed refetch, so the honest move is to keep showing
 * it rather than swap the screen for an alarm the reviewer would read as "the run broke" —
 * it is the console's refresh that broke, not the run. Whether the view heals itself differs
 * by case: a live run is still being polled and the next successful hit clears this on its
 * own, but a terminal run has no background poll left to do that, so it gets the retry.
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
      className="rounded border border-border bg-muted p-section text-body text-muted-foreground"
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

function Workflow({ findingId }: { findingId: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  const terminal = isRunTerminal(data)

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs
        trail={[
          { label: "Fleet", to: "/" },
          { label: findingId, to: `/findings/${encodeURIComponent(findingId)}` },
          { label: "Solution workflow" },
        ]}
      />
      <h1 className="font-mono text-page">{findingId} — solution workflow</h1>

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
          <ErrorState error={query.error} what={`the run for finding ${findingId}`} />
        ))}

      {data !== undefined && (
        <>
          {query.isError && (
            <StaleBanner
              fetchedAt={query.dataUpdatedAt}
              live={!terminal}
              isFetching={query.isFetching}
              onRetry={() => void query.refetch()}
            />
          )}

          <p className="max-w-prose text-meta text-ink-muted">
            Run <span className="font-mono">{data.thread_id}</span>
            {data.generation_count > 1 && (
              <>
                {" — the most recent of "}
                {data.generation_count}
                {" runs the checkpointer holds for this finding. "}
                <Link to="/" className="underline underline-offset-2">
                  The fleet screen
                </Link>
                {" lists every one."}
              </>
            )}
          </p>

          <RunOutcome
            outcome={data.outcome}
            abandonReason={data.abandon_reason}
            reportReason={data.report_reason}
          />

          <p className="max-w-prose text-body text-muted-foreground">
            <Link
              to={`/findings/${encodeURIComponent(findingId)}/workflow/pull-request`}
              className="underline underline-offset-2"
            >
              See the pull request's evidence bundle
            </Link>{" "}
            — the five nodes below that answer whether this run earned a merge, at their own
            address a reviewer can send on.
          </p>

          <Card>
            <CardHeader>
              <CardTitle>The run, node by node</CardTitle>
              <CardDescription>
                The remediation graph's own order, with the evidence each node produced. A
                node marked due after it has already run is a retry the graph owes another
                visit, not a finished step — the loop is real and this view does not hide
                it.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <NodeSequence nodes={data.nodes} />
            </CardContent>
          </Card>

          <p className="max-w-prose text-body text-muted-foreground">
            Read from the checkpointer, which is a different database from the API
            Dependency Graph — this screen carries no indexing timestamp and no binding rung
            for that reason.{" "}
            <Link
              to={`/findings/${encodeURIComponent(findingId)}`}
              className="underline underline-offset-2"
            >
              The finding itself
            </Link>{" "}
            carries both.
          </p>
        </>
      )}
    </section>
  )
}
