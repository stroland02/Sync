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
 *
 * ## On `ScreenFrame`
 *
 * "Open the pull request" left the rail for the controls band: it is the one destination this
 * screen offers and the band is where a screen's destinations live, so a reader no longer has to
 * reach the bottom of a fact list to find the forge. Its qualifying sentence travels with it.
 */

import type { ReactNode } from "react"
import { Link, useParams } from "react-router"

import { NotFoundError } from "@/api/errors"
import { workspacePath } from "@/features/findings/workspace-path"
import { WORKFLOW_POLL_MS, usePatch, useWorkflow } from "@/api/queries"
import type { WorkflowNode, WorkflowState } from "@/api/types"
import { type Fact, FactList } from "@/components/fact-list"
import { Pending } from "@/features/findings/pending"
import { ErrorState, LoadingState, NotFoundState } from "@/components/states"
import { Absent } from "@/components/status"
import { Button } from "@/components/ui/button"
import {
  type BundleFacts,
  bundleFacts,
  noBranchPhrase,
  noPullRequestPhrase,
} from "@/features/pullrequests/bundle-facts"
import { BUNDLE_STAGES, EvidenceBundle } from "@/features/pullrequests/evidence-bundle"
import { PatchPanel, VISIBLE_DIFF_LINES } from "@/features/pullrequests/patch-panel"
import { RunOutcome, type BelowThisPanel } from "@/features/workflows/run-outcome"
import { DetailGrid } from "@/layouts/detail-grid"
import { ScreenFrame } from "@/layouts/screen-frame"
import type { StatusSegment } from "@/layouts/status-band"
import { UnknownRoute } from "@/layouts/unknown-route"


export interface PullRequestPageProps {
  readonly question?: string
}

export function PullRequestPage() {
  // Both identifiers come out of the URL, so both are checked before a request is made for them.
  // `repoId` was carried through unchecked and `workspacePath(undefined)` is `/repositories/`, so
  // this screen's three workspace links resolved to an address that renders "No screen at this
  // address" — the exact failure `workspace-path.ts` was written for, on a route whose registry
  // entry declares `params: ["repoId", "findingId"]`.
  const { repoId, findingId } = useParams<{ repoId: string; findingId: string }>()
  if (repoId === undefined || findingId === undefined) return <UnknownRoute />
  return <PullRequest repoId={repoId} findingId={findingId} />
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
 * level spells: `<Pending>` writes the word where the value goes while the query is in flight,
 * `<Absent>` says it failed, and a value is
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
  repoId: string,
  findingId: string,
): Fact[] {
  function fact(render: (state: WorkflowState) => ReactNode): ReactNode {
    if (data !== undefined) return render(data)
    if (failure !== null) return failure
    return <Pending />
  }

  return [
    {
      label: "Finding",
      value: (
        <Link
          to={`${workspacePath(repoId)}/findings/${encodeURIComponent(findingId)}`}
          className="underline underline-offset-2"
        >
          <code className="font-mono text-meta break-all select-all">{findingId}</code>
        </Link>
      ),
    },
    {
      label: "Repository",
      value: fact((state) =>
        state.repo_id === null ? (
          <Absent>unknown</Absent>
        ) : (
          <Link
            to={`/repositories/${encodeURIComponent(state.repo_id)}`}
            className="underline underline-offset-2"
          >
            <code className="font-mono text-meta break-all">{state.repo_id}</code>
          </Link>
        ),
      ),
    },
    {
      label: "Pull request",
      value: fact((state) =>
        facts.prNumber === null ? (
          <Absent>{noPullRequestPhrase(state.outcome)}</Absent>
        ) : (
          <span className="font-mono">#{facts.prNumber}</span>
        ),
      ),
    },
    {
      label: "Branch",
      value: fact((state) =>
        facts.branch === null ? (
          <Absent>{noBranchPhrase(state.outcome)}</Absent>
        ) : (
          <span className="font-mono break-words">{facts.branch}</span>
        ),
      ),
    },
    {
      label: "Run",
      value: fact((state) => (
        <code className="font-mono text-meta break-all select-all">{state.thread_id}</code>
      )),
    },
    {
      label: "Generations",
      value: fact((state) => (
        <div className="flex flex-col gap-field">
          <span className="font-mono">{state.generation_count}</span>
          {state.generation_count > 1 && (
            <span className="text-meta text-ink-muted">
              This is the most recent of {state.generation_count} runs the checkpointer holds for
              this finding. An earlier generation may have reached a pull request even where this one
              has not;{" "}
              <Link to={workspacePath(repoId)} className="underline underline-offset-2">
                the codebase overview
              </Link>{" "}
              lists every one.
            </span>
          )}
        </div>
      )),
    },
  ]
}

/**
 * How many of the five this bundle names the run has actually been through.
 *
 * `ran` and `due_again` are the two standings that mean the graph executed the node at least once;
 * `due` does not — `node-standing.ts` words it as a visit the graph still owes. A node the payload
 * carries no entry for is not reached either, which is why this counts the stages rather than the
 * nodes.
 */
function nodesReached(nodes: WorkflowNode[]): number {
  return BUNDLE_STAGES.filter((stage) => {
    const standing = nodes.find((node) => node.name === stage.name)?.standing
    return standing === "ran" || standing === "due_again"
  }).length
}

/** The window `PatchPanel` draws, counted for the band rather than restated by it. */
function diffWindow(diff: string): string {
  const total = diff.split("\n").length
  return `${Math.min(total, VISIBLE_DIFF_LINES).toLocaleString()} of ${total.toLocaleString()}`
}

function PullRequest({
  repoId,
  findingId,
}: {
  repoId: string
  findingId: string
}) {
  const query = useWorkflow(findingId)
  const data = query.data
  const facts = bundleFacts(data?.nodes ?? [])
  // The patch panel's own key, so the diff figure reads the answer already on screen rather than
  // opening a second request for it — and so the figure is gated on the query it counts rather
  // than on the run's.
  const patch = usePatch(findingId)

  const failure = query.isError ? (
    query.error instanceof NotFoundError ? (
      <Absent>no run for this finding</Absent>
    ) : (
      <Absent>the API did not answer</Absent>
    )
  ) : null

  // Three absences and they are three claims: nothing has answered, the answer failed, and the run
  // produced no patch at all. The last one is a measurement that happened and found nothing to
  // window, so it never wears a scope that says a count was taken.
  const diffScope =
    patch.data === undefined
      ? patch.isError
        ? "did not answer"
        : "still asking"
      : patch.data.diff === null
        ? "no diff on this run — the patch panel says which nothing that is"
        : "of the patch this run produced; the rest are on the branch named above"

  const status: StatusSegment[] =
    data === undefined
      ? [
          {
            kind: "none",
            why: query.isError
              ? query.error instanceof NotFoundError
                ? "no run for this finding, so there is nothing here to count"
                : "the run did not answer"
              : "asking the checkpointer for this run",
          },
        ]
      : [
          {
            kind: "figure",
            label: "Nodes reached",
            value: `${nodesReached(data.nodes)} of ${BUNDLE_STAGES.length}`,
            scope:
              "the five this bundle names — reached means the graph ran the node, not that it " +
              "produced evidence",
          },
          {
            kind: "figure",
            label: "Diff lines shown",
            value:
              patch.data === undefined || patch.data.diff === null
                ? null
                : diffWindow(patch.data.diff),
            scope: diffScope,
          },
          {
            kind: "figure",
            label: "Generation",
            value: `${data.generation_count.toLocaleString()} of ${data.generation_count.toLocaleString()}`,
            // The pointer is gated the way the rail's own caveat is: at one generation there is
            // no earlier one, and naming a list of them sends a reader after something absent.
            scope:
              data.generation_count > 1
                ? "this page is the newest generation the checkpointer holds for this finding; " +
                  "any earlier one is listed on the codebase overview"
                : "the only generation the checkpointer holds for this finding",
          },
          {
            kind: "note",
            text:
              "Read from the LangGraph checkpointer rather than the graph — two databases — so " +
              "this route carries no indexed_at and no binding rung: nothing on this screen is " +
              "dated by an index run or attributed to an evidence rung.",
          },
        ]

  // Omitted rather than emptied when the run opened nothing: the frame reserves no height for a
  // band it is not given.
  const controls =
    facts.prUrl !== null ? (
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
    ) : undefined

  return (
    <ScreenFrame controls={controls} status={status}>
    <DetailGrid
      rail={
        <div className="flex min-w-0 flex-col gap-section">
          <FactList facts={railFacts(data, facts, failure, repoId, findingId)} />

          <p className="text-body text-muted-foreground">
            Read from the checkpointer, the same source as{" "}
            <Link
              to={`${workspacePath(repoId)}/findings/${encodeURIComponent(findingId)}/workflow`}
              className="underline underline-offset-2"
            >
              the solution workflow
            </Link>
            , which shows all eight nodes; this page shows the five that carry the evidence a pull
            request rests on.
          </p>
        </div>
      }
    >
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
            <ErrorState error={query.error} what={`the run for finding ${findingId}`} onRetry={() => void query.refetch()} />
          ))}

        {data !== undefined && (
          <>
            {/* Decision 47: the diff leads. Before this a reviewer could read every verdict
                about a patch on this screen without ever seeing the patch, and the
                verification chain that follows it is what makes the verdicts worth reading. */}
            <PatchPanel findingId={findingId} nodes={data.nodes} />

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
    </DetailGrid>
    </ScreenFrame>
  )
}
