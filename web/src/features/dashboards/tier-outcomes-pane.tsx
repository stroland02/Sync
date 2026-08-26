/**
 * Dashboard 5 as a pane of the locked Corpus grid: how each routing tier's attempts ended.
 *
 * Rebuilt from `features/runs/tier-outcomes-card.tsx` on 2026-08-26, which this replaces.
 * `tier-outcomes-option.ts` still carries what it counts, including the argument for two
 * categorical slots rather than a good-to-bad gradient.
 *
 * The sentence about thinness is the point of this pane as much as the bars are. The plan
 * predicted a four-row corpus and said it must say so, because a cascade drawn confidently from
 * four attempts is the chart claiming to know something it does not.
 */

import { useCallback, useMemo } from "react"
import { Layers } from "lucide-react"

import { useAbandonment } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  SPARSE_ATTEMPT_FLOOR,
  buildTierOutcomesOption,
  tierOutcomes,
} from "@/features/runs/tier-outcomes-option"

const EMPTY = { tiers: [], totalAttempts: 0, isSparse: false } as const

const HINT = (
  <InfoHint label="About how each tier's attempts ended">
    Repair attempts by the tier that routed them, split into those that were abandoned and those
    that were not. Tier 0 is the codemod path and costs nothing to run, so whether it settles work
    is the question worth asking of this chart. These are attempts rather than findings — one
    finding retried three times contributes three. There is no percentage abandoned per tier: that
    is the score this console refuses, and a reader who wants it can divide two counts that are
    both on screen.
  </InfoHint>
)

export function TierOutcomesPane({ className }: { className?: string } = {}) {
  const query = useAbandonment()
  const outcomes = useMemo(
    () => (query.data === undefined ? null : tierOutcomes(query.data)),
    [query.data],
  )

  const build = useCallback(
    (tokens: ChartTokens) => buildTierOutcomesOption(outcomes ?? EMPTY, tokens),
    [outcomes],
  )

  if (query.isPending || query.isError || outcomes === null) {
    return (
      <PanelPane
        className={className}
        label="How each tier's attempts ended"
        icon={Layers}
        hint={HINT}
        bodyClassName="p-section"
      >
        {query.isError ? (
          <ErrorState
            error={query.error}
            what="how each tier's attempts ended"
            onRetry={() => void query.refetch()}
          />
        ) : (
          <LoadingState what="how each tier's attempts ended" />
        )}
      </PanelPane>
    )
  }

  return (
    <PanelPane
      className={className}
      label="How each tier's attempts ended"
      icon={Layers}
      hint={HINT}
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono tabular-nums text-ink">
            {outcomes.totalAttempts.toLocaleString()}
          </span>{" "}
          attempts · {outcomes.tiers.length} {outcomes.tiers.length === 1 ? "tier" : "tiers"}
        </span>
      }
      bodyClassName="p-section"
      footer={
        // Worded so it does not repeat the paragraph below verbatim: the grain claim is here in
        // its shortest form and argued once, under the chart.
        <span>All workspaces · one row is one attempt · two counts, never a rate.</span>
      }
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      <div className="flex min-w-0 flex-col gap-section">
      {outcomes.tiers.length === 0 ? (
        <EmptyState
          headline="No repair attempt has been recorded."
          detail="The corpus holds no attempt at any tier, so there is no cascade to draw. This table cannot be backfilled — every attempt processed before it existed is gone — so an empty chart here means nothing has run yet rather than that nothing was kept."
          command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
        />
      ) : (
        <div className="h-64 w-full shrink-0">
          <EChart
            buildOption={build}
            ariaLabel="Repair attempts by routing tier, settled against abandoned"
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
        <p className="max-w-prose text-meta text-ink-muted leading-relaxed">
          These are attempts rather than findings — one finding retried three times contributes
          three.{" "}
          {outcomes.isSparse ? (
            <>
              <span className="text-ink">
                {outcomes.totalAttempts} attempts in total, which is too few to read a cascade
                from.
              </span>{" "}
              Below about {SPARSE_ATTEMPT_FLOOR} one unlucky abandonment swings a whole tier, so
              treat the bars as what has happened rather than as how the tiers behave. The shape is
              thin because the corpus is young, not because the chart is broken.
            </>
          ) : (
            <>{outcomes.totalAttempts} attempts in total.</>
          )}{" "}
          A tier with no bar had nothing routed to it, which is not the same as having attempted and
          settled everything. <span className="font-mono">settled</span> means the attempt was not
          abandoned — it reached the end of the pipeline. It does not mean the pull request it
          opened was any good, which is a different measurement this data does not carry.
        </p>
      </div>
    </PanelPane>
  )
}
