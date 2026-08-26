/**
 * The earlier runs the checkpointer still holds for this finding.
 *
 * **It never returns null any more, and that is the change.** The top bar states a `Generations`
 * figure on every run; when it read `1` this component rendered nothing at all, so the figure was
 * followed by silence and a reader could not tell whether one generation meant *there is only one*
 * or *the rest are somewhere this screen does not show*. One sentence closes that.
 *
 * Each superseded run is named with its generation, its outcome, and the reason the attempt
 * stopped. Kept rather than hidden: an abandoned attempt is what teaches routing which change kinds
 * are not mechanically safe.
 */

import type { GenerationSummary } from "@/api/types"
import { MetricPanel } from "@/components/metric-panel"
import { Absent } from "@/components/status"

export interface SupersededGenerationsProps {
  readonly generations?: readonly GenerationSummary[]
  readonly currentThreadId: string
}

export function SupersededGenerations({
  generations = [],
  currentThreadId,
}: SupersededGenerationsProps) {
  const superseded = generations.filter((g) => g.thread_id !== currentThreadId)

  if (superseded.length === 0) {
    return (
      <MetricPanel label="Generations">
        <p className="max-w-prose text-body text-ink-muted">
          This is the only generation the checkpointer holds for this finding.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label={`Superseded ${superseded.length === 1 ? "generation" : "generations"}`}
      caption={`Previous remediation ${superseded.length === 1 ? "attempt" : "attempts"} for this finding, superseded by the current run.`}
    >
      <div className="flex flex-col divide-y divide-border">
        {superseded.map((gen) => (
          <div key={gen.thread_id} className="flex flex-col gap-field py-section first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-baseline justify-between gap-field">
              <span className="font-mono text-body font-semibold text-foreground">
                Run {gen.generation + 1}
              </span>
              <code className="font-mono text-meta text-muted-foreground break-all">
                {gen.thread_id}
              </code>
            </div>

            <div className="flex flex-wrap items-center gap-field text-meta">
              <span className="font-medium text-foreground capitalize">
                {gen.outcome ?? <Absent>in flight</Absent>}
              </span>
              {gen.abandon_reason && (
                <span className="text-muted-foreground">— {gen.abandon_reason}</span>
              )}
              {gen.report_reason && (
                <span className="text-muted-foreground">— {gen.report_reason}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </MetricPanel>
  )
}
