/**
 * Dashboards L2, L3 and T4: what the repair pipeline attempted, over time and by tier.
 *
 * One read, three panels — the callers place them, and Solutions mounts the first two while
 * Trends mounts the series. Splitting one grouping of one table into three routes would be three
 * round trips for one answer.
 *
 * **One row is one attempt, not one finding**, and every panel says so. A finding retried three
 * times contributes three attempts, so a total here exceeds the finding count on every other
 * screen and neither figure is wrong. That is `migration_outcome`'s declared grain and the single
 * most misreadable thing on these panels.
 *
 * **Fleet-wide, and it could not be otherwise.** `migration_outcome` stores no repository — the
 * schema decision that makes it safe to aggregate across customers — so there is no narrower
 * answer being withheld. Said on screen rather than left for a reader to assume the workspace.
 *
 * **The tier panel is a count, never a success rate.** Which tier produced an outcome is the
 * routing question; how often a tier succeeds is `merge_rate_by_tier` on the Corpus tab, computed
 * over a denominator these counts do not have. Two panels, two questions, and neither derived
 * from the other.
 *
 * **Empty is expected here for a long time and is drawn as a measurement.** This deployment holds
 * one attempt. A panel that hid itself when thin would leave a reader unable to tell an idle
 * pipeline from a missing screen, so each states which nothing it is.
 */

import { useCallback } from "react"
import { useQuery } from "@tanstack/react-query"

import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import { buildDayStackOption, type DayEntry } from "@/components/charts/day-stack-option"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { RankedBars } from "@/components/ranked-bars"
import { ErrorState, LoadingState } from "@/components/states"
import { Absent } from "@/components/status"
import { CORPUS_SCOPE, ScopeChip } from "@/components/scope-chip"

interface RemediationActivity {
  days: DayEntry[]
  /** Tier as a string key, to what each attempt at that tier reached. */
  by_tier: Record<string, Record<string, number>>
}

export async function fetchRemediationActivity(
  signal?: AbortSignal,
): Promise<RemediationActivity> {
  const path = "/api/precedent/activity"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as RemediationActivity
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

/** A panel title with the corpus scope beside it, written once for both panels. */
function ScopeLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex flex-wrap items-center gap-row">
      {children}
      <ScopeChip scope="all workspaces">{CORPUS_SCOPE}</ScopeChip>
    </span>
  )
}

function useActivity() {
  return useQuery({
    queryKey: ["corpus-activity"],
    queryFn: ({ signal }) => fetchRemediationActivity(signal),
  })
}

/** L2 and T4: attempts per day, stacked by what each reached. */
export function AttemptsOverTime() {
  const query = useActivity()
  const days = query.data?.days ?? []
  // Every status that occurs anywhere, so one status is the same colour on every day.
  const statuses = [...new Set(days.flatMap((day) => Object.keys(day.counts)))].sort()
  const build = useCallback(
    (tokens: ChartTokens) =>
      buildDayStackOption(
        {
          days,
          members: statuses,
          stackId: "attempts",
          // Every band here means an outcome, so every band reads the ramp rather than a
          // categorical slot. Before this, slot order painted `abandoned` in the good ink --
          // a failure drawn as a success -- and `retried` in a pink that belongs to no palette
          // this console declares. `DESIGN.md`, "The outcome ramp".
          memberColors: tokens.outcome,
        },
        tokens,
      ),
    [days, statuses],
  )

  if (query.isPending) return <LoadingState what="repair attempts over time" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="repair attempts over time"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const hint = (
    <InfoHint label="About repair attempts over time">
      Every repair the pipeline attempted, on the day it was recorded, stacked by what the attempt
      reached. One bar segment is one <em>attempt</em>, not one finding — a finding retried three
      times contributes three. Dated by when the attempt happened rather than by when a pull
      request merged, because a series keyed on the merge date would drop every attempt that never
      opened one, which is most of them. Rehearsals are excluded: they halt before the remote and
      never count toward an activity figure.
    </InfoHint>
  )

  if (days.length === 0) {
    return (
      <MetricPanel
        label="Repair attempts over time"
        hint={hint}
        caption="No repair attempt has been recorded on any day."
      >
        <span className="text-body">
          <Absent>nothing recorded yet</Absent>
        </span>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label={<ScopeLabel>Repair attempts over time</ScopeLabel>}
      hint={hint}
      caption="Attempts by the day they were recorded, stacked by what each reached. One row is one attempt, not one finding."
    >
      <EChart
        buildOption={build}
        ariaLabel="Repair attempts per day, stacked by outcome"
        style={{ height: 260 }}
      />
    </MetricPanel>
  )
}

/** L3: which tier produced the attempts, and what each reached. */
export function AttemptsByTier() {
  const query = useActivity()

  if (query.isPending) return <LoadingState what="attempts by repair tier" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="attempts by repair tier"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const tiers = Object.entries(query.data.by_tier).sort(([a], [b]) => Number(a) - Number(b))
  const rows = tiers.map(([tier, counts]) => ({
    key: `tier ${tier}`,
    value: Object.values(counts).reduce((sum, n) => sum + n, 0),
  }))

  const hint = (
    <InfoHint label="About attempts by repair tier">
      Which repair tier produced each attempt. Tier 0 is the mechanical path and the higher tiers
      cost more, so the distribution is what says whether routing is working — a codebase whose
      repairs all land at tier 0 is one Sync is fixing cheaply. This is a count and not a success
      rate: how often a tier succeeds is the merge-rate axis on the Corpus tab, computed over a
      denominator these counts do not have. A tier absent here never ran, which is not the same as
      a tier that ran and failed.
    </InfoHint>
  )

  if (rows.length === 0) {
    return (
      <MetricPanel
        label="Attempts by repair tier"
        hint={hint}
        caption="No repair attempt has been recorded."
      >
        <span className="text-body">
          <Absent>no tier has run</Absent>
        </span>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label={<ScopeLabel>Attempts by repair tier</ScopeLabel>}
      hint={hint}
      caption="Attempts grouped by the tier that produced them. A count of attempts, never a success rate — and a tier missing here never ran rather than running and reaching nothing."
    >
      <RankedBars
        label="By tier"
        caption="Each bar's width is its share of the busiest tier, not of the total."
        rows={rows}
        unit="attempts"
        colourByKey={false}
      />
      <div className="flex flex-col gap-field border-t border-line pt-row">
        {tiers.map(([tier, counts]) => (
          <div key={tier} className="flex flex-wrap items-baseline gap-row">
            <span className="w-[4.5rem] shrink-0 font-mono text-meta text-ink">tier {tier}</span>
            <span className="min-w-0 text-meta text-ink-muted">
              {Object.entries(counts)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([status, n]) => `${n} ${status}`)
                .join(" · ")}
            </span>
          </div>
        ))}
      </div>
    </MetricPanel>
  )
}
