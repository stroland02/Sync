/**
 * The activity timeline, rendered.
 *
 * `activity.ts` carries the honesty boundary; this file only lays out what it returns. The
 * caption states the boundary in the reader's own words rather than assuming they have read
 * the module doc, and the omitted-count sentence is the one place absence is stated rather
 * than left as a shorter list than the node count would suggest.
 *
 * The panel is titled "Checkpoint timeline" rather than "Activity" because the screen now has an
 * `Activity` tab, and a panel sharing its container's name tells a reader nothing about which of
 * the two they are looking at. The title moved; not one sentence under it did.
 */

import { activityEntries, omittedCount } from "@/features/workflows/activity"
import { Absent } from "@/components/status"
import { formatTimestamp } from "@/lib/format"
import { MetricPanel } from "@/components/metric-panel"
import type { WorkflowState } from "@/api/types"

export function ActivityTimeline({ state }: { state: WorkflowState }) {
  const entries = activityEntries(state)
  const omitted = omittedCount(state)

  return (
    <MetricPanel
      label="Checkpoint timeline"
      caption="Assembled at read time from the checkpointer. Nothing writes a timeline row."
    >
      {entries.length === 0 ? (
        <p className="text-body text-ink-muted">
          <Absent>no node has written a checkpoint timestamp yet</Absent>
        </p>
      ) : (
        <ol className="flex flex-col gap-row">
          {entries.map((entry, index) => (
            <li key={`${entry.name}-${index}`} className="grid grid-cols-[auto_1fr] gap-row">
              <time
                dateTime={entry.at ?? undefined}
                className="font-mono text-meta text-ink-muted"
              >
                {entry.at === null ? <Absent /> : formatTimestamp(entry.at)}
              </time>
              <div className="flex flex-col gap-field">
                <span className="font-mono text-meta text-foreground">{entry.name}</span>
                {entry.detail !== null && (
                  <span className="text-meta text-ink-muted">{entry.detail}</span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {omitted > 0 && (
        <p className="text-meta text-ink-muted">
          {omitted === 1
            ? "One node has written no checkpoint timestamp and has no row here"
            : `${omitted} nodes have written no checkpoint timestamp and have no row here`}{" "}
          — absence, not zero.
        </p>
      )}
    </MetricPanel>
  )
}
