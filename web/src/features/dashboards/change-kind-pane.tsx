/**
 * Which kinds of change the pipeline has attempted, ranked — a pane of the locked Corpus grid.
 *
 * New with the Corpus rebuild of 2026-08-26, and it draws data the console already held and never
 * showed: `/api/precedent/abandonment` groups by `(change_kind, tier)`, and until now only the tier
 * half of that grouping reached a screen. `change-kind-attempts.ts` carries the derivation.
 *
 * Bars rather than a ring, because this is a ranking and its members do not partition a whole a
 * reader can name — a change kind absent here has never been attempted, which is not a slice of
 * nought.
 */

import { useMemo } from "react"
import { Shapes } from "lucide-react"

import { useAbandonment } from "@/api/queries"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { changeKindAttempts } from "@/features/dashboards/change-kind-attempts"
import { spansOrdersOfMagnitude } from "@/features/dashboards/daily-series"

const HINT = (
  <InfoHint label="About attempts by change kind">
    Every repair attempt the corpus holds, grouped by the kind of API change that provoked it, with
    the abandoned attempts printed beside each count. This is the routing question in its most
    direct form: a change kind whose attempts keep being abandoned is one the mechanical path
    cannot yet handle. Two counts and no ratio — an abandonment rate computed over three attempts
    is a percentage with a denominator of three, and both numbers are on screen for anyone who
    wants to divide them. A change kind missing from this ranking has never been attempted, which
    is a different fact from one attempted and never abandoned.
  </InfoHint>
)

export function ChangeKindPane({ className }: { className?: string } = {}) {
  const query = useAbandonment()
  const attempts = useMemo(
    () => (query.data === undefined ? null : changeKindAttempts(query.data)),
    [query.data],
  )

  if (query.isPending || query.isError || attempts === null) {
    return (
      <PanelPane
        className={className}
        label="What has been attempted, by change kind"
        icon={Shapes}
        hint={HINT}
        bodyClassName="p-section"
      >
        {query.isError ? (
          <ErrorState
            error={query.error}
            what="attempts by change kind"
            onRetry={() => void query.refetch()}
          />
        ) : (
          <LoadingState what="attempts by change kind" />
        )}
      </PanelPane>
    )
  }

  return (
    <PanelPane
      className={className}
      label="What has been attempted, by change kind"
      icon={Shapes}
      hint={HINT}
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono tabular-nums text-ink">
            {attempts.totalAttempts.toLocaleString()}
          </span>{" "}
          attempts ·{" "}
          <span className="font-mono tabular-nums text-ink">
            {attempts.totalAbandoned.toLocaleString()}
          </span>{" "}
          abandoned
        </span>
      }
      bodyClassName="p-section"
      footer={
        <span>
          {attempts.kindCount} change{" "}
          {attempts.kindCount === 1 ? "kind has" : "kinds have"} been attempted at all — the corpus
          has no closed list of kinds, so this counts what was seen rather than what exists. Two
          counts per row and no rate between them.
        </span>
      }
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      {attempts.rows.length === 0 ? (
        <p className="max-w-prose text-body text-ink-muted">
          <Absent>no attempt recorded</Absent> — the corpus was read and holds no repair attempt of
          any kind. That is a count of nought rather than a question nobody asked.
        </p>
      ) : (
        <RankedBars
          className="h-auto rounded-none border-0 bg-transparent p-0"
          label="By change kind"
          caption="Each row reads as abandoned-of-attempted, and the bar's width is its share of the busiest change kind rather than of the total. One row is one attempt, not one finding."
          rows={attempts.rows}
          unit="attempts"
          colourByKey={false}
          // "1 abandoned of" reading straight into the bar's own count, which `RankedBars` prints
          // immediately after it. "1 abandoned" beside a 2 was two numbers with no relation stated.
          detail={(key) => `${attempts.abandoned[key] ?? 0} abandoned of`}
          scale={
            spansOrdersOfMagnitude(attempts.rows.map((row) => row.value)) ? "log" : "linear"
          }
        />
      )}
    </PanelPane>
  )
}
