/**
 * Dashboard 6 as a pane of the locked Corpus grid: why runs gave up, over the closed vocabulary.
 *
 * Rebuilt from `features/runs/abandon-reasons-card.tsx` on 2026-08-26, which this replaces — it
 * was a `MetricPanel` mounted on one screen, and that screen is a locked bento now. The chart, the
 * derivation and every sentence are unchanged; `abandon-reasons-option.ts` still carries what is
 * counted and why.
 *
 * The sentences under the chart are not decoration. This screen is where somebody decides which
 * change kinds are not mechanically safe, and three facts have to survive that reading: the bars
 * are attempts and not findings, an attempt with no recorded code is not `unclassified`, and a
 * reason with no bar was counted and found empty rather than skipped.
 */

import { useCallback, useMemo } from "react"
import { CircleSlash } from "lucide-react"

import { useAbandonment } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import {
  ABANDON_REASON_CODES,
  abandonReasonDistribution,
  buildAbandonReasonsOption,
} from "@/features/runs/abandon-reasons-option"

const EMPTY = {
  ranked: [],
  totalAbandonedAttempts: 0,
  uncoded: 0,
  unhitCodeCount: 0,
  undeclaredCodes: [],
} as const

const HINT = (
  <InfoHint label="About why runs gave up">
    Every abandoned repair attempt, grouped by the reason the run recorded. These are attempts
    rather than findings — a finding retried three times contributes three — and they are grouped
    on the recorded code rather than on the prose beside it, which is what makes two runs that gave
    up for the same cause count together. An abandoned attempt is data rather than a failure to
    hide: the reason code is queryable, and abandonment is how routing learns which changes are not
    mechanically safe to attempt.
  </InfoHint>
)

export function AbandonReasonsPane({ className }: { className?: string } = {}) {
  const query = useAbandonment()
  const distribution = useMemo(
    () => (query.data === undefined ? null : abandonReasonDistribution(query.data)),
    [query.data],
  )

  const build = useCallback(
    (tokens: ChartTokens) => buildAbandonReasonsOption(distribution ?? EMPTY, tokens),
    [distribution],
  )

  if (query.isPending || query.isError || distribution === null) {
    return (
      <PanelPane
        className={className}
        label="Why runs gave up"
        icon={CircleSlash}
        hint={HINT}
        bodyClassName="p-section"
      >
        {query.isError ? (
          <ErrorState
            error={query.error}
            what="why runs gave up"
            onRetry={() => void query.refetch()}
          />
        ) : (
          <LoadingState what="why runs gave up" />
        )}
      </PanelPane>
    )
  }

  // Measured on the running console 2026-08-26: this corpus holds one abandoned attempt and it
  // predates the reason column, so `ranked` is empty while `uncoded` is 1 — and the card drew a
  // ranked-bar chart with no categories, an empty plot rectangle that reads as broken. That is the
  // failure `web/CLAUDE.md` names: a chart must be able to draw its own data.
  const drawable = distribution.ranked.length > 0
  const empty = !drawable && distribution.uncoded === 0

  return (
    <PanelPane
      className={className}
      label="Why runs gave up"
      icon={CircleSlash}
      hint={HINT}
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono tabular-nums text-ink">
            {distribution.totalAbandonedAttempts.toLocaleString()}
          </span>{" "}
          abandoned attempts
        </span>
      }
      bodyClassName="p-section"
      footer={
        <span>All workspaces · one row is one attempt, grouped on the recorded code.</span>
      }
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      <div className="flex min-w-0 flex-col gap-section">
      {empty ? (
        <EmptyState
          headline="No attempt has been abandoned."
          detail="The corpus was read and holds no abandoned repair attempt. This is a count of nought rather than a question nobody asked — but it is also a young corpus, so it will stay sparse for a while and that is the corpus rather than the chart."
          command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
        />
      ) : !drawable ? (
        <EmptyState
          headline="No abandoned attempt carries a recorded reason."
          detail="There is no ranking to draw, and that is not the same as nothing having been abandoned — every abandoned attempt this corpus holds predates the reason column, so each carries no code at all. The paragraph below counts them."
        />
      ) : (
        <div className="h-64 w-full shrink-0">
          <EChart
            buildOption={build}
            ariaLabel="Abandoned repair attempts, by the reason recorded"
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
        <p className="max-w-prose text-meta text-ink-muted leading-relaxed">
          These are attempts rather than findings — a finding retried three times contributes
          three, and they are grouped on the recorded code rather than on the prose beside it.{" "}
          {distribution.totalAbandonedAttempts} abandoned{" "}
          {distribution.totalAbandonedAttempts === 1 ? "attempt carries" : "attempts carry"} a
          recorded reason.{" "}
          {distribution.unhitCodeCount > 0 && (
            <>
              {distribution.unhitCodeCount} of the {ABANDON_REASON_CODES.length} reasons the
              pipeline can record have no attempt against them — counted and found empty, not left
              out.{" "}
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
    </PanelPane>
  )
}
