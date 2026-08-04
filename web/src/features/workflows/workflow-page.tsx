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
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { NodeSequence } from "@/features/workflows/node-sequence"
import { RunOutcome } from "@/features/workflows/run-outcome"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function WorkflowPage() {
  // The identifier comes out of the URL, so it is checked before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <Workflow findingId={findingId} />
}

function Workflow({ findingId }: { findingId: string }) {
  const query = useWorkflow(findingId)
  const terminal = isRunTerminal(query.data)

  return (
    <section className="flex flex-col gap-4">
      <Breadcrumbs
        trail={[
          { label: "Codebase", to: "/" },
          { label: findingId, to: `/findings/${encodeURIComponent(findingId)}` },
          { label: "Solution workflow" },
        ]}
      />
      <h1 className="font-mono text-lg font-medium">{findingId} — solution workflow</h1>

      {query.isPending && <LoadingState what={`the run for finding ${findingId}`} />}

      {query.isError &&
        (query.error instanceof NotFoundError ? (
          <div className="flex flex-col items-start gap-3">
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

      {query.isSuccess && (
        <>
          <RunOutcome
            outcome={query.data.outcome}
            abandonReason={query.data.abandon_reason}
          />

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
              <NodeSequence nodes={query.data.nodes} terminal={terminal} />
            </CardContent>
          </Card>

          <p className="text-sm text-muted-foreground">
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
