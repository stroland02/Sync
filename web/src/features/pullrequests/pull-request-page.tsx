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
 *
 * ## Ported onto the vendored substrate by M7-W180
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-pull-request.md` is the mapping table this port was
 * gated on. Read that before porting a level, not this docstring.
 *
 * **The fact rail is a left column, taken from the standing ruling rather than argued again.** The
 * Finding level placed one there and the controller settled it for every detail level: 360px, the
 * page header inside it, the content column beside it from the top of the page, one column below
 * `lg`.
 *
 * **The rail's number and branch are lifted out of node evidence, so the lift has a test.**
 * `WorkflowState` carries neither; both are keys inside `nodes[].evidence`, which is
 * `Record<string, unknown>` and promises nothing. `bundle-facts.ts` owns that read, the boundary
 * check on the pull request's address, and the short absence phrase each row wears when the run has
 * no number or no branch to show.
 *
 * **Three of the six facts the direction's rail asks for are not on this payload and none is
 * invented.** The run's state is the outcome panel standing level with the rail, so a row for it
 * would be one fact twice. There is no timestamp anywhere on this route, which is B123. And the
 * repository is B125: the checkpoint carries `repo` on every run and `workflow_state` forwards
 * eleven other channel values and not that one — cutting a repository name out of the pull request's
 * URL would be pattern-matching a forge address the payload never labelled.
 *
 * ## The header spans both columns, and the title is the bundle's own name, by M7-W193
 *
 * It was inside the 360px rail with the finding's 32-character identifier at the display step. The
 * title is now `#number · branch`, from the two facts `bundle-facts.ts` already lifts, and it states
 * the absence — in that module's own outcome-keyed words — when a run pushed nothing or opened
 * nothing. The rail keeps both rows: the title names the subject, and the rows say which nothing
 * each part is, which is a longer answer than a title can carry.
 */

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { WORKFLOW_POLL_MS, useWorkflow } from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { type Fact, FactList } from "@/components/fact-list"
import { Skeleton } from "@/components/skeleton"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import {
  type BundleFacts,
  bundleFacts,
  noBranchPhrase,
  noPullRequestPhrase,
} from "@/features/pullrequests/bundle-facts"
import { EvidenceBundle } from "@/features/pullrequests/evidence-bundle"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"
import { DetailTitleText, pullRequestTitle } from "@/lib/detail-title"
import { routeQuestion } from "@/lib/routes"

/** This screen's own entry in the registry, so `PageHeader` renders the registry's sentence. */
const ROUTE_PATH = "/findings/:findingId/workflow/pull-request"

export function PullRequestPage() {
  // The identifier comes out of the URL, so it is checked before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <PullRequest findingId={findingId} />
}

/**
 * What `RunOutcome` may say about this screen, which renders five of the run's eight nodes.
 *
 * `locate`, `prepare` and `patch` are deliberately not here, so nothing below this panel may
 * be described as the attempt in full — and the node the workflow screen calls `open_pr` is
 * labelled "The pull request" here, so naming the channel would send a reader looking for a
 * heading that is not on this page.
 *
 * All four survived the port untouched. The Solution Workflow had to repoint three of its own
 * because its outcome moved into the sequence; nothing moved here, so "below" and "above" are still
 * true of this screen's geometry.
 */
const BELOW: BelowThisPanel = {
  inFlight: `The five nodes below are the last state the checkpointer recorded for them, re-read every ${WORKFLOW_POLL_MS / 1000} seconds until the run finishes.`,
  abandoned:
    "The five nodes below carry however far the evidence got; locate, prepare and patch are not among them, and the solution workflow shows all eight.",
  opened: "The pull request itself is the last of the five panels below.",
  unrecognised: "The five nodes below are still what the run produced.",
}

/**
 * The bundle's own facts, in the rail beside the evidence.
 *
 * Three states per fact and they are three different claims, the same three every ported detail
 * level spells: a `Skeleton` says the query is in flight, `<Absent>` says it failed, and a value is
 * a value. The finding is answered by the URL rather than by the query, so it never wears either.
 *
 * There is no State row on purpose. `RunOutcome` renders the run's disposition as the first thing
 * in the content column, at `h2`, level with this rail — a word for it here as well would be the
 * same fact twice a few inches apart, which is the defect the Fleet port's ruling 2 named.
 */
function railFacts(
  data: WorkflowState | undefined,
  facts: BundleFacts,
  failure: ReactNode | null,
  findingId: string,
): Fact[] {
  function fact(width: string, render: (state: WorkflowState) => ReactNode): ReactNode {
    if (data !== undefined) return render(data)
    if (failure !== null) return failure
    return <Skeleton width={width} />
  }

  return [
    {
      label: "Finding",
      value: (
        <Link
          to={`/findings/${encodeURIComponent(findingId)}`}
          className="underline underline-offset-2"
        >
          <code className="font-mono text-meta break-all select-all">{findingId}</code>
        </Link>
      ),
    },
    {
      label: "Pull request",
      value: fact("w-16", (state) =>
        facts.prNumber === null ? (
          <Absent>{noPullRequestPhrase(state.outcome)}</Absent>
        ) : (
          <span className="font-mono">#{facts.prNumber}</span>
        ),
      ),
    },
    {
      label: "Branch",
      value: fact("w-40", (state) =>
        facts.branch === null ? (
          <Absent>{noBranchPhrase(state.outcome)}</Absent>
        ) : (
          <span className="font-mono break-words">{facts.branch}</span>
        ),
      ),
    },
    {
      label: "Run",
      value: fact("w-40", (state) => (
        <code className="font-mono text-meta break-all select-all">{state.thread_id}</code>
      )),
    },
    {
      label: "Generations",
      value: fact("w-12", (state) => (
        <div className="flex flex-col gap-field">
          <span className="font-mono">{state.generation_count}</span>
          {state.generation_count > 1 && (
            <span className="text-meta text-ink-muted">
              This is the most recent of {state.generation_count} runs the checkpointer holds for
              this finding. An earlier generation may have reached a pull request even where this one
              has not;{" "}
              <Link to="/" className="underline underline-offset-2">
                the fleet screen
              </Link>{" "}
              lists every one.
            </span>
          )}
        </div>
      )),
    },
  ]
}

function PullRequest({ findingId }: { findingId: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  // One read of the evidence per render, shared by the rail and by the link out. `bundleFacts`
  // scans the node list, and three rows asking it the same question three times is the same work
  // three times.
  const facts = bundleFacts(data?.nodes ?? [])

  // Short, because the content column carries the same answer in full: four rows spelling out that
  // state's whole sentence would be one fact written five times. Each still says which nothing it is.
  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>no run for this finding</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  const trail = [
    { label: "Fleet", to: "/" },
    { label: findingId, to: `/findings/${encodeURIComponent(findingId)}` },
    { label: "Solution workflow", to: `/findings/${encodeURIComponent(findingId)}/workflow` },
    { label: "Pull request" },
  ]

  const title =
    data !== undefined ? (
      <DetailTitleText
        title={pullRequestTitle(
          facts.prNumber,
          facts.branch,
          noPullRequestPhrase(data.outcome),
          noBranchPhrase(data.outcome),
        )}
      />
    ) : failure !== null ? (
      failure
    ) : (
      <Skeleton width="w-72" />
    )

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]">
      <div className="min-w-0 lg:col-span-2">
        <PageHeader
          trail={<Breadcrumbs trail={trail} />}
          title={title}
          question={routeQuestion(ROUTE_PATH)}
        />
      </div>

      <div className="flex min-w-0 flex-col gap-section">
        <FactList facts={railFacts(data, facts, failure, findingId)} />

        <p className="text-body text-muted-foreground">
          Read from the checkpointer, the same source as{" "}
          <Link
            to={`/findings/${encodeURIComponent(findingId)}/workflow`}
            className="underline underline-offset-2"
          >
            the solution workflow
          </Link>
          , which shows all eight nodes; this page shows the five that carry the evidence a pull
          request rests on.
        </p>

        {facts.prUrl !== null && (
          <p className="text-body">
            <a
              href={facts.prUrl}
              target="_blank"
              rel="noreferrer noopener"
              className="underline underline-offset-2"
            >
              Open the pull request
            </a>{" "}
            <span className="text-muted-foreground">
              — leaves the console for the forge it was opened on.
            </span>
          </p>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-8">
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
            <RunOutcome
              outcome={data.outcome}
              abandonReason={data.abandon_reason}
              reportReason={data.report_reason}
              below={BELOW}
            />

            <EvidenceBundle nodes={data.nodes} outcome={data.outcome} />
          </>
        )}
      </div>
    </div>
  )
}
