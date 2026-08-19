/**
 * Dashboard 5, as a component Lane B mounts on the Runs route beside `AbandonReasonsCard`.
 *
 * Self-contained and propless, same contract as its sibling: it fetches the corpus aggregate
 * itself. `tier-outcomes-option.ts` carries what it counts.
 *
 * The sentence about thinness is the point of this card as much as the bars are. The plan
 * predicted a four-row corpus and said it must say so, because a cascade drawn confidently from
 * four attempts is the chart claiming to know something it does not.
 */

import { useCallback, useMemo } from "react"

import { useAbandonment } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  SPARSE_ATTEMPT_FLOOR,
  buildTierOutcomesOption,
  tierOutcomes,
} from "@/features/runs/tier-outcomes-option"

const EMPTY = { tiers: [], totalAttempts: 0, isSparse: false } as const

export function TierOutcomesCard() {
  const query = useAbandonment()
  const outcomes = useMemo(
    () => (query.data === undefined ? null : tierOutcomes(query.data)),
    [query.data],
  )

  const build = useCallback(
    (tokens: ChartTokens) => buildTierOutcomesOption(outcomes ?? EMPTY, tokens),
    [outcomes],
  )

  if (query.isPending) return <LoadingState what="how each tier's attempts ended" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="how each tier's attempts ended"
        onRetry={() => void query.refetch()}
      />
    )
  }
  if (outcomes === null) return null

  return (
    <MetricPanel
      className="h-full"
      label="How each tier's attempts ended"
      caption={
        <p className="max-w-prose">
          Repair attempts by the tier that routed them, split into those that were abandoned and
          those that were not. Tier 0 is the codemod path and costs nothing to run, so whether it
          settles work is the question worth asking of this chart. These are attempts rather than
          findings — one finding retried three times contributes three.
        </p>
      }
    >
      {outcomes.tiers.length === 0 ? (
        <EmptyState
          headline="No repair attempt has been recorded."
          detail="The corpus holds no attempt at any tier, so there is no cascade to draw. This table cannot be backfilled — every attempt processed before it existed is gone — so an empty chart here means nothing has run yet rather than that nothing was kept."
          command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
        />
      ) : (
        <div className="flex flex-col gap-field">
          <div className="h-64 w-full">
            <EChart
              buildOption={build}
              ariaLabel="Repair attempts by routing tier, settled against abandoned"
              style={{ height: "100%", width: "100%" }}
            />
          </div>

          <p className="text-meta text-ink-muted leading-relaxed">
            {outcomes.isSparse ? (
              <>
                <span className="text-ink">
                  {outcomes.totalAttempts} attempts in total, which is too few to read a cascade
                  from.
                </span>{" "}
                Below about {SPARSE_ATTEMPT_FLOOR} one unlucky abandonment swings a whole tier, so
                treat the bars as what has happened rather than as how the tiers behave. The
                shape is thin because the corpus is young, not because the chart is broken.
              </>
            ) : (
              <>{outcomes.totalAttempts} attempts in total.</>
            )}{" "}
            A tier with no bar had nothing routed to it, which is not the same as having attempted
            and settled everything. <span className="font-mono">settled</span> means the attempt
            was not abandoned — it reached the end of the pipeline. It does not mean the pull
            request it opened was any good, which is a different measurement this data does not
            carry.
          </p>
        </div>
      )}
    </MetricPanel>
  )
}
