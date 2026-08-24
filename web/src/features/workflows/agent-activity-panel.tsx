/**
 * The agent-activity feed: what the patch agent read, edited, ran and said, as the run recorded
 * it. The turn-by-turn record the checkpoint timeline cannot carry — a checkpoint is one write
 * per node, and the patch node's says nothing about the forty tool calls inside it.
 */

import { useRunActivity } from "@/api/queries"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"
import { activityPollMs, activityRowLabel } from "@/features/workflows/agent-activity"
import type { WorkflowState } from "@/api/types"

export function AgentActivityPanel({
  repoId,
  findingId,
  run,
}: {
  repoId: string
  findingId: string
  run: WorkflowState | undefined
}) {
  const query = useRunActivity(repoId, findingId, { refetchIntervalMs: activityPollMs(run) })
  const events = query.data?.events

  return (
    <MetricPanel
      label="Agent activity"
      caption="Recorded by the run itself as it works — each tool call, each refusal, and the agent's own notes. Oldest first, newest last; a refusal row is the gate turning a call away, not a failure of the run."
    >
      {query.isPending ? (
        <p className="text-body text-muted-foreground">Asking for the run&#39;s recorded activity…</p>
      ) : query.isError ? (
        <p className="text-body text-muted-foreground">
          <Absent>the API did not answer for this feed</Absent>
        </p>
      ) : events === undefined || events.length === 0 ? (
        /* One sentence for two nothings, deliberately: the payload cannot distinguish a run
           that predates activity capture from one that has not started, so the empty state
           names both rather than picking one and being wrong half the time. */
        <p className="text-body text-muted-foreground">
          <Absent>no activity recorded — the run predates activity capture or has not started</Absent>
        </p>
      ) : (
        <ol className="flex min-w-0 flex-col gap-row">
          {events.map((event) => (
            <li key={event.seq} className="grid min-w-0 grid-cols-[auto_1fr] gap-row">
              <span className="font-mono text-meta text-foreground">
                {activityRowLabel(event)}
              </span>
              <span className="min-w-0 font-mono text-meta break-words whitespace-pre-wrap text-muted-foreground">
                {event.summary}
              </span>
            </li>
          ))}
        </ol>
      )}
    </MetricPanel>
  )
}
