/**
 * What the evidence on this screen rests on, and what the next rung would take.
 *
 * The rung has been a label since it shipped. It is a *path*, and rendering it as one is what makes
 * Sync's position visible: findings exist here before anything is configured, because the static
 * rung is read out of source code. A product that waits for traces has an empty screen until they
 * arrive. Saying "static" in a badge does not carry that; saying "static now, observed once you
 * attach telemetry" does.
 *
 * **No forecast.** Nothing here says how many bindings would upgrade. It counts what each rung holds
 * now, and the same panel shows the difference once telemetry is attached. That restraint is the
 * point rather than a limitation: an estimate would be a number nothing computed.
 */

import { useDetectors } from "@/api/queries"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import { nextStep, offPath, rungSteps, type RungStep } from "@/features/fleet/rung-upgrade"

/** What each rung means, and — for a rung not yet reached — what reaching it actually takes. */
const RUNG_COPY: Record<RungStep["rung"], { means: string; takes: string }> = {
  static: {
    means: "read out of your source code, with nothing attached and nothing configured",
    takes: "indexing the repository, which is the only step Sync needs to start",
  },
  resolved: {
    means: "a static read plus a resolution step, where the call target was inferred rather than literal",
    takes: "call sites whose target Sync must resolve — this rung appears on its own as the index meets them",
  },
  observed: {
    means: "correlated against traffic Sync actually watched",
    takes: "attaching telemetry, so watched calls can be matched to these call sites",
  },
}

export interface RungUpgradeBodyProps {
  readonly repoId?: string
}

/** The ladder itself. The Overview's bento pane supplies the chrome that used to be a card. */
export function RungUpgradeBody({ repoId }: RungUpgradeBodyProps) {
  const detectors = useDetectors(repoId)

  if (detectors.isPending) return <LoadingState what="the evidence behind these findings" />
  if (detectors.isError) {
    return (
      <ErrorState
        error={detectors.error}
        what="the evidence behind these findings"
        onRetry={() => void detectors.refetch()}
      />
    )
  }

  const rows = detectors.data?.detectors ?? []
  const steps = rungSteps(rows)
  const next = nextStep(steps)
  const off = offPath(rows)
  const anyEvidence = steps.some((step) => step.reached)

  return (
    <div className="flex flex-col gap-row">
        <dl className="flex flex-col gap-field">
          {steps.map((step) => (
            <div key={step.rung} className="flex flex-col gap-field">
              <div className="flex items-baseline gap-field">
                <dt className="font-mono text-meta uppercase tracking-wider text-foreground">
                  {step.rung}
                </dt>
                <dd className="font-mono text-body text-foreground">
                  {/* A measured zero, printed as a number. The scope was counted and this rung held
                      none of it — which is not the same as not having asked, and the absence marker
                      would say the wrong one. */}
                  {step.count.toLocaleString()}
                </dd>
                <span className="text-meta text-ink-muted">
                  {step.reached ? "reached" : "nothing rests here yet"}
                </span>
              </div>
              <p className="text-meta text-muted-foreground leading-relaxed">
                {step.reached ? RUNG_COPY[step.rung].means : RUNG_COPY[step.rung].takes}
              </p>
            </div>
          ))}
        </dl>

        {anyEvidence ? (
          <p className="text-meta text-muted-foreground max-w-prose leading-relaxed">
            Every finding counted above was read from your code before anything was configured. That
            is what the static rung is. Attaching telemetry does not create findings — it changes the
            evidence behind them, moving call sites onto a rung that says Sync watched the call
            happen rather than that it read the call in source.
            {next === null
              ? " Nothing above this rung exists, so there is no further step to take."
              : ` Nothing rests on ${next.rung} yet: ${RUNG_COPY[next.rung].takes}.`}
          </p>
        ) : (
          <p className="text-meta text-muted-foreground max-w-prose leading-relaxed">
            <Absent>no evidence at any rung in this scope</Absent> — nothing has been indexed here,
            so there is nothing to upgrade and no advice worth giving about a codebase Sync has not
            read yet.
          </p>
        )}

        {off.length > 0 && (
          <p className="text-meta text-muted-foreground max-w-prose leading-relaxed">
            Not on the path, and shown so these counts add up:{" "}
            {off.map((entry, index) => (
              <span key={entry.rung}>
                {index > 0 && ", "}
                <span className="font-mono">{entry.rung}</span> {entry.count.toLocaleString()}
              </span>
            ))}
            . <span className="font-mono">unresolved</span> is the named absence of a binding rather
            than weak evidence for one, and <span className="font-mono">unattributed</span> is a row
            written before the rung was recorded. Neither is a step anybody can take.
          </p>
      )}
    </div>
  )
}
