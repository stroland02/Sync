/**
 * The Pull Request level: the remediation run's evidence bundle, with its own address.
 *
 * Specified at `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:442`
 * as "Pull Request — with its evidence bundle", beneath Solution Workflow. Until this file,
 * the whole of that bundle was `pr_url`, one row inside the workflow's node-by-node view
 * (`features/workflows/evidence.tsx:131`) — a link, not a destination a reviewer could send
 * a colleague. This page is that destination, reading the same run `useWorkflow` already
 * fetches and showing the five nodes that answer "does this deserve a merge", in the graph's
 * own order.
 *
 * It needs no route the console does not already have: `GET /api/workflows/{finding_id}` is
 * the only transport this level reads, because the evidence bundle is a subset of the same
 * eight-node payload the Solution Workflow page renders in full.
 */

import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { isRunTerminal, useWorkflow } from "@/api/queries"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Button } from "@/components/ui/button"
import { EvidenceBundle } from "@/features/pullrequests/evidence-bundle"
import { RunOutcome } from "@/features/workflows/run-outcome"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { UnknownRoute } from "@/layouts/unknown-route"

export function PullRequestPage() {
  // The identifier comes out of the URL, so it is checked before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <PullRequest findingId={findingId} />
}

function PullRequest({ findingId }: { findingId: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  const terminal = isRunTerminal(data)

  const trail = [
    { label: "Fleet", to: "/" },
    { label: findingId, to: `/findings/${encodeURIComponent(findingId)}` },
    { label: "Solution workflow", to: `/findings/${encodeURIComponent(findingId)}/workflow` },
    { label: "Pull request" },
  ]

  return (
    <section className="flex flex-col gap-8">
      <Breadcrumbs trail={trail} />
      <h1 className="font-mono text-page">{findingId} — pull request</h1>

      {query.isPending && <LoadingState what={`the run for finding ${findingId}`} />}

      {data === undefined &&
        query.isError &&
        (query.error instanceof NotFoundError ? (
          <div className="flex flex-col items-start gap-section">
            <NotFoundState
              headline="No remediation run for this finding, so there is no pull request."
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
          <p className="max-w-prose text-meta text-ink-muted">
            Run <span className="font-mono">{data.thread_id}</span>
            {data.generation_count > 1 && (
              <>
                {" — the most recent of "}
                {data.generation_count}
                {" runs the checkpointer holds for this finding. An earlier generation may "}
                {"have reached a pull request even where this one has not; "}
                <Link to="/" className="underline underline-offset-2">
                  the fleet screen
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

          <EvidenceBundle nodes={data.nodes} terminal={terminal} />

          <p className="max-w-prose text-body text-muted-foreground">
            Read from the checkpointer, the same source as{" "}
            <Link
              to={`/findings/${encodeURIComponent(findingId)}/workflow`}
              className="underline underline-offset-2"
            >
              the solution workflow
            </Link>
            , which shows all eight nodes; this page shows the five that carry the evidence a
            pull request rests on.
          </p>
        </>
      )}
    </section>
  )
}
