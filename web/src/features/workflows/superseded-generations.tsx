import type { GenerationSummary } from "@/api/types"
import { Absent } from "@/components/status"

export interface SupersededGenerationsProps {
  readonly generations?: readonly GenerationSummary[]
  readonly currentThreadId: string
}

/**
 * Renders the superseded remediation generations for a finding.
 *
 * Each superseded run is rendered with its generation identifier, outcome,
 * and abandon/report reason where the attempt stopped.
 */
export function SupersededGenerations({
  generations = [],
  currentThreadId,
}: SupersededGenerationsProps) {
  const list = generations ?? []
  const superseded = list.filter((g) => g.thread_id !== currentThreadId)
  if (superseded.length === 0) return null

  return (
    <section
      aria-label="Superseded remediation generations"
      className="flex flex-col gap-section rounded border border-border bg-card p-card"
    >
      <div>
        <h3 className="text-body font-medium text-foreground">
          Superseded {superseded.length === 1 ? "generation" : "generations"}
        </h3>
        <p className="mt-field text-meta text-muted-foreground">
          Previous remediation {superseded.length === 1 ? "attempt" : "attempts"} for this finding, superseded by the current run.
        </p>
      </div>

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
                <span className="text-muted-foreground">
                  — {gen.abandon_reason}
                </span>
              )}
              {gen.report_reason && (
                <span className="text-muted-foreground">
                  — {gen.report_reason}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
