/**
 * Dashboard 6, as a component Lane B mounts on the Runs route (decision 30).
 *
 * Self-contained: it fetches `/api/corpus/abandonment` itself and takes no props, so mounting it
 * is one import and one tag. `abandon-reasons-option.ts` carries what it counts and why.
 *
 * The sentences under the chart are not decoration. This screen is where somebody decides which
 * change kinds are not mechanically safe, and three facts have to survive that reading: the bars
 * are attempts and not findings, an attempt with no recorded code is not `unclassified`, and a
 * reason with no bar was counted and found empty rather than skipped.
 */

import { useCallback, useMemo } from "react"

import { useAbandonment } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { MetricPanel } from "@/components/metric-panel"
import {
  ABANDON_REASON_CODES,
  abandonReasonDistribution,
  buildAbandonReasonsOption,
} from "@/features/runs/abandon-reasons-option"

export function AbandonReasonsCard() {
  const query = useAbandonment()
  const distribution = useMemo(
    () => (query.data === undefined ? null : abandonReasonDistribution(query.data)),
    [query.data],
  )

  const build = useCallback(
    (tokens: ChartTokens) =>
      buildAbandonReasonsOption(
        distribution ?? { ranked: [], totalAbandonedAttempts: 0, uncoded: 0, unhitCodeCount: 0, undeclaredCodes: [] },
        tokens,
      ),
    [distribution],
  )

  if (query.isPending) return <LoadingState what="why runs gave up" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="why runs gave up"
        onRetry={() => void query.refetch()}
      />
    )
  }
  if (distribution === null) return null

  // `h-full`, because this card shares a grid row with its sibling: two panels in one row at
  // two heights read as a mistake rather than as two answers.
  return (
    <MetricPanel
      className="h-full"
      label="Why runs gave up"
      caption={
        <p className="max-w-prose">
          Every abandoned repair attempt, grouped by the reason the run recorded. These are
          attempts rather than findings — a finding retried three times contributes three — and
          they are grouped on the recorded code rather than on the prose beside it, which is what
          makes two runs that gave up for the same cause count together.
        </p>
      }
    >
      {distribution.ranked.length === 0 && distribution.uncoded === 0 ? (
        <EmptyState
          headline="No attempt has been abandoned."
          detail="The corpus was read and holds no abandoned repair attempt. This is a count of nought rather than a question nobody asked — but it is also a young corpus, so it will stay sparse for a while and that is the corpus rather than the chart."
          command="uv run sync run --repo-id <repo> --vendor <vendor> --from-version <a> --to-version <b>"
        />
      ) : (
        <div className="flex flex-col gap-field">
          <div className="h-64 w-full">
            <EChart
              buildOption={build}
              ariaLabel="Abandoned repair attempts, by the reason recorded"
              style={{ height: "100%", width: "100%" }}
            />
          </div>

          <p className="text-meta text-ink-muted leading-relaxed">
            {distribution.totalAbandonedAttempts} abandoned{" "}
            {distribution.totalAbandonedAttempts === 1 ? "attempt carries" : "attempts carry"} a
            recorded reason.{" "}
            {distribution.unhitCodeCount > 0 && (
              <>
                {distribution.unhitCodeCount} of the {ABANDON_REASON_CODES.length} reasons the
                pipeline can record have no attempt against them — counted and found empty, not
                left out.{" "}
              </>
            )}
            {distribution.uncoded > 0 && (
              <>
                A further {distribution.uncoded}{" "}
                {distribution.uncoded === 1 ? "attempt was" : "attempts were"} recorded before the
                reason was stored as a code, so they carry none. That is not{" "}
                <span className="font-mono">unclassified</span>, which is a reason a run actually
                reached; it is history from before the column, and it cannot be backfilled.{" "}
              </>
            )}
            {distribution.undeclaredCodes.length > 0 && (
              <>
                The payload also carried{" "}
                <span className="font-mono">{distribution.undeclaredCodes.join(", ")}</span>, which
                this screen does not know. Shown rather than dropped: a reason the console cannot
                name is still a reason a run gave up.
              </>
            )}
          </p>
        </div>
      )}
    </MetricPanel>
  )
}
