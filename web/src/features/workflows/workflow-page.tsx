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
 *
 * ## Recomposed as a narrative by M7-W179
 *
 * `docs/superpowers/briefs/2026-08-07-substrate-workflow.md` is the mapping table this port was
 * gated on. Read that before porting a level, not this docstring.
 *
 * **The reading order is the change.** This screen rendered a status list: a banner saying how the
 * run ended, then a card containing eight nodes. It now reads as an investigation — what arrived,
 * what happened in order with each node's evidence attached to it, and how it ended **at the point
 * where it ended**. On an abandoned run that last part is the whole of it: the reason sits under the
 * evidence of the node that failed and over the nodes reading "the run ended before the graph got
 * here", instead of in a banner four screens above them.
 *
 * **Two of the direction's asks are not in this payload and neither is invented.** There is no
 * per-node elapsed time anywhere in a checkpoint this route reads (B123), and a superseded
 * generation is not reachable from it (B124) — `GET /api/workflows/{finding_id}` answers with the
 * newest thread only. The rail says how many generations there are and where the others are listed,
 * which is what the payload supports, and the opening entry says plainly that the sequence carries
 * no times.
 *
 * ## The header spans both columns, and the title is "Run N", by M7-W193
 *
 * The header was inside the 360px rail with the finding's 32-character identifier at the display
 * step. It is now the grid's first row across both columns, and the title is which run this is among
 * the generations the checkpointer holds. **The finding's own name is not in it, and that is a
 * ruling rather than an omission** — it is not on this payload, and fetching it would put this
 * page's only focal point behind a query that 404s for every patched or abandoned finding, which is
 * exactly the run most worth reading. `lib/detail-title.tsx` carries the argument; the breadcrumb
 * and the rail's first row both still reach the finding in one click.
 */

import type { ReactNode } from "react"
import { FetchedAt } from "@/components/fetched-at"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { WORKFLOW_POLL_MS, isRunTerminal, useWorkflow } from "@/api/queries"
import type { WorkflowState } from "@/api/types"
import { type Fact, FactList } from "@/components/fact-list"
import { Skeleton } from "@/components/skeleton"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { NodeSequence } from "@/features/workflows/node-sequence"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { SupersededGenerations } from "@/features/workflows/superseded-generations"
import { Breadcrumbs } from "@/layouts/breadcrumbs"
import { PageHeader } from "@/layouts/page-header"
import { UnknownRoute } from "@/layouts/unknown-route"
import { DetailTitleText, runTitle } from "@/lib/detail-title"
import { formatFindingBadge } from "@/lib/format"
import { formatTimestamp } from "@/lib/format"

const DEFAULT_QUESTION =
  "What did Sync's remediation graph do about this finding, node by node?"

export interface WorkflowPageProps {
  readonly question?: string
}

export function WorkflowPage({ question = DEFAULT_QUESTION }: WorkflowPageProps) {
  // The identifier comes out of the URL, so it is checked before a request is made for it.
  const { findingId } = useParams<{ findingId: string }>()
  if (findingId === undefined) return <UnknownRoute />
  return <Workflow findingId={findingId} question={question} />
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

/**
 * What `RunOutcome` may say about this screen, which renders all eight nodes as a narrative.
 * The panel does not know that; this page does.
 *
 * Three of these named a position that has moved. The outcome is no longer above the sequence, so
 * nothing is "below" it in the sense these were written for — and the `abandoned` sentence gains
 * what the old arrangement could not carry, because there was no *where* for the outcome to be
 * relative to. The `opened` sentence is untouched: "under `open_pr`" names a heading.
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
 *
 * Every sentence but the third was already on this screen — the checkpointer-is-a-different-database
 * paragraph from the foot of the page, and the two sentences from the description of the card the
 * sequence used to sit inside. They are here because this is where a reader meets them before
 * reading anything they qualify, rather than after.
 */
function Arrival({ findingId }: { findingId: string }) {
  return (
    <>
      <h3 className="text-emphasis">What arrived</h3>
      <div className="mt-row flex max-w-prose flex-col gap-row text-body text-muted-foreground">
        <p>A finding arrived from the API Dependency Graph, and this run is what Sync did about it.</p>
        <p>
          Read from the checkpointer, which is a different database from the API Dependency
          Graph — this screen carries no indexing timestamp and no binding rung for that reason.{" "}
          <Link
            to={`/findings/${encodeURIComponent(findingId)}`}
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
 * The run's own facts, in the rail beside the narrative.
 *
 * Three states per fact and they are three different claims, the same three every ported detail
 * level spells: a `Skeleton` says the query is in flight, `<Absent>` says it failed, and a value is
 * a value. The finding is answered by the URL rather than by the query, so it never wears either.
 *
 * There is no Outcome row here on purpose. The outcome is the narrative's closing entry, where it
 * carries its reason and its position; a word for it in the rail as well would be the same fact at
 * two weights, which is the defect the Fleet port's ruling 2 named.
 *
 * Both identifiers are `<code>` at the meta step. They are values a reader copies rather than reads,
 * which is the register they belong in and the reason M7-W193 took the finding id out of the title.
 */
function runFacts(data: WorkflowState | undefined, failure: ReactNode | null, findingId: string): Fact[] {
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
              this finding.{" "}
              <Link to="/" className="underline underline-offset-2">
                The fleet screen
              </Link>{" "}
              lists every one.
            </span>
          )}
        </div>
      )),
    },
  ]
}

function Workflow({ findingId, question }: { findingId: string; question: string }) {
  const query = useWorkflow(findingId)
  const data = query.data
  const terminal = isRunTerminal(data)

  // Short, because the content column carries the same answer in full: two rows spelling out that
  // state's whole sentence would be one fact written three times. Each still says which nothing it is.
  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>no run for this finding</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  const title =
    data !== undefined ? (
      <DetailTitleText title={runTitle(data.generation_count)} />
    ) : failure !== null ? (
      failure
    ) : (
      <Skeleton width="w-40" />
    )

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,22.5rem)_minmax(0,1fr)]">
      <div className="min-w-0 lg:col-span-2">
        <PageHeader
          trail={
            <Breadcrumbs
              trail={[
                { label: "Repositories", to: "/" },
                { label: formatFindingBadge(findingId), to: `/findings/${encodeURIComponent(findingId)}` },
                { label: "Solution workflow" },
              ]}
            />
          }
          title={title}
          question={question}
        />
      </div>

      <div className="flex min-w-0 flex-col gap-section">
        <FactList facts={runFacts(data, failure, findingId)} />

        {data !== undefined && (
          <p className="text-body text-muted-foreground">
            <Link
              to={`/findings/${encodeURIComponent(findingId)}/workflow/pull-request`}
              className="underline underline-offset-2"
            >
              {/* The possessive asserted a pull request on every run, including the ones that
                  never opened one. The link goes to the same place either way; what it says
                  follows the outcome the payload already carries. */}
              {data.outcome === "opened"
                ? "See the pull request's evidence bundle"
                : "See the evidence bundle for this run"}
            </Link>{" "}
            — the five nodes that answer whether this run earned a merge, at their own address a
            reviewer can send on.
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
            {query.isError ? (
              <StaleBanner
                fetchedAt={query.dataUpdatedAt}
                live={!terminal}
                isFetching={query.isFetching}
                onRetry={() => void query.refetch()}
              />
            ) : (
              /* The healthy counterpart to `StaleBanner`. That banner only appears once a refetch
                 has failed, so until now a run being watched and a run whose screen had gone quiet
                 for a terminal outcome looked identical — both just sat there. This says which. */
              <FetchedAt
                at={query.dataUpdatedAt}
                polling={!terminal}
                idleReason="This run has reached a terminal outcome, so nothing is being polled."
              />
            )}

            <SupersededGenerations
              generations={data.generations}
              currentThreadId={data.thread_id}
            />

            <NodeSequence
              nodes={data.nodes}
              opening={<Arrival findingId={findingId} />}
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
          </>
        )}
      </div>
    </div>
  )
}
