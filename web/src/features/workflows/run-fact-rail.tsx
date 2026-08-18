/**
 * The run's identity, held still while the transcript scrolls.
 *
 * The Solution Workflow is where a human intervenes in work that is still in progress, so the two
 * panes answer different questions and only one of them moves. This one answers *what is this run*:
 * the finding it came from, the repository it cloned, the tier the cascade routed to, the strategy
 * that produced the edit, when its first checkpoint landed, how far apart its checkpoints are, and
 * what the graph still owes a visit. `run-identity.ts` derives every one of those and returns null
 * for the ones this payload cannot answer.
 *
 * **Three refusals are visible in what is not here.**
 *
 * A reference incident view puts a confidence figure in exactly this rail — `Root cause confidence:
 * 9`. There is none here and there will not be one: what stands behind a claim is the class of
 * evidence it rests on, and this run's evidence is named node by node in the transcript. The
 * provenance rung, which is the console's own answer to that question, belongs to the API
 * Dependency Graph and not to the checkpointer, so the rail links to the finding rather than
 * inventing a rung this database cannot see.
 *
 * There is no outcome row. The outcome is the narrative's closing entry, placed where the run
 * stopped; a word for it here as well would be one fact at two weights.
 *
 * **`Checkpoint span` is not a run duration.** It is the distance between the first and the last
 * checkpoint this run wrote, which is a measurement. A run parked on the customer's CI writes
 * nothing for as long as that takes, and a run that has died writes the same nothing, so "how long
 * it has been running" is a figure nothing computed and it is not on this screen.
 *
 * **The three actions render disabled rather than vanishing**, per the owner's rule that an action
 * missing from a screen teaches a reader the product is unpredictable. Each names what it needs.
 */

import type { ReactNode } from "react"
import { Link } from "react-router"

import type { WorkflowState } from "@/api/types"
import { type Fact, FactList } from "@/components/fact-list"
import { Skeleton } from "@/components/skeleton"
import { Absent, Formatted } from "@/components/status"
import { Button } from "@/components/ui/button"
import { formatSpan, runIdentity } from "@/features/workflows/run-identity"
import { formatTimestamp } from "@/lib/format"

/** What each rail action would need before it could act. Named, so the gap is a work item. */
const ACTIONS: { label: string; needs: string }[] = [
  {
    label: "Copy the agent prompt",
    needs: "the prompt the remediation agent was given, which no checkpoint channel records",
  },
  {
    label: "Give feedback",
    needs: "a write route that accepts a reviewer's judgement of a run",
  },
  {
    label: "Restart the run",
    needs: "a route that starts remediation, which would mutate the graph",
  },
]

function code(value: string): ReactNode {
  return <code className="font-mono text-meta break-all select-all">{value}</code>
}

function railFacts(
  data: WorkflowState | undefined,
  failure: ReactNode | null,
  findingId: string,
): Fact[] {
  function fact(width: string, render: (state: WorkflowState) => ReactNode): ReactNode {
    if (data !== undefined) return render(data)
    if (failure !== null) return failure
    return <Skeleton width={width} />
  }

  const identity = data === undefined ? null : runIdentity(data)

  return [
    {
      label: "Finding",
      value: (
        <Link
          to={`/findings/${encodeURIComponent(findingId)}`}
          className="underline underline-offset-2"
        >
          {code(findingId)}
        </Link>
      ),
    },
    {
      // The checkpointer holds the run, not the finding, so the vendor is genuinely unavailable
      // here. Named rather than dropped: a rail that silently omits a row a reader expects reads
      // as a screen that forgot, and this is a route boundary rather than an oversight.
      label: "Vendor",
      value: (
        <span className="text-body">
          <Absent>not on this payload — the checkpointer holds the run, not the finding</Absent>
        </span>
      ),
    },
    {
      label: "Repository",
      value: fact("w-32", () =>
        identity?.repoId ? code(identity.repoId) : <Absent>the run recorded no repository</Absent>,
      ),
    },
    {
      label: "Tier",
      value: fact("w-24", () =>
        identity?.tier === null || identity === null ? (
          <Absent>locate recorded no tier</Absent>
        ) : (
          <span className="font-mono text-body">{identity.tier}</span>
        ),
      ),
    },
    {
      label: "Strategy",
      value: fact("w-24", () =>
        identity?.strategy === null || identity === null ? (
          <Absent>patch has produced no attempt</Absent>
        ) : (
          <span className="font-mono text-body">{identity.strategy}</span>
        ),
      ),
    },
    {
      label: "Started",
      value: fact("w-32", () =>
        identity?.startedAt == null ? (
          <Absent>no node has stamped a checkpoint yet</Absent>
        ) : (
          <time dateTime={identity.startedAt} className="font-mono text-meta">
            <Formatted value={formatTimestamp(identity.startedAt)} />
          </time>
        ),
      ),
    },
    {
      label: "Checkpoint span",
      value: fact("w-20", () => (
        <div className="flex flex-col gap-field">
          {identity?.checkpointSpanSeconds == null ? (
            <Absent>nothing stamped, so there is no span to measure</Absent>
          ) : (
            <span className="font-mono text-body">{formatSpan(identity.checkpointSpanSeconds)}</span>
          )}
          <span className="text-meta text-ink-muted">
            First checkpoint to last. Not how long the run took — a run waiting on the customer's CI
            writes no checkpoint for as long as that takes.
          </span>
        </div>
      )),
    },
    {
      label: "Waiting on",
      value: fact("w-24", (state) => {
        if (identity === null) return <Absent />
        if (identity.waitingOn !== null) {
          return (
            <div className="flex flex-col gap-field">
              <span className="font-mono text-body">{identity.waitingOn}</span>
              <span className="text-meta text-ink-muted">
                The graph owes this node a visit. That is not a claim that anything is executing.
              </span>
            </div>
          )
        }
        if (state.outcome !== null && state.outcome !== "running") {
          return (
            <span className="text-body text-ink-muted">
              Nothing — the run reached a terminal outcome.
            </span>
          )
        }
        return <Absent>no node is marked due in the newest checkpoint</Absent>
      }),
    },
    {
      label: "Run",
      value: fact("w-40", (state) => code(state.thread_id)),
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

export function RunFactRail({
  findingId,
  data,
  failure,
}: {
  findingId: string
  data: WorkflowState | undefined
  /** What the rail says in every value slot when the query failed. Null while it has not. */
  failure: ReactNode | null
}) {
  return (
    <div className="flex min-w-0 flex-col gap-section lg:sticky lg:top-section lg:self-start">
      <FactList facts={railFacts(data, failure, findingId)} />

      <div className="flex flex-col gap-row">
        <p className="furniture text-meta text-ink-muted">Actions</p>
        <div className="flex flex-col items-start gap-field">
          {ACTIONS.map((action) => (
            <Button key={action.label} variant="outline" size="sm" disabled>
              {action.label}
            </Button>
          ))}
        </div>
        <p className="max-w-prose text-meta text-ink-muted">
          None of these can act. Sync's API is read-only — no route mutates a run or starts one —
          so each is shown disabled rather than omitted, because an action that disappears reads as
          an oversight. Copying the agent prompt needs{" "}
          {ACTIONS[0].needs}; feedback needs {ACTIONS[1].needs}; restarting needs {ACTIONS[2].needs}.
        </p>
      </div>
    </div>
  )
}
