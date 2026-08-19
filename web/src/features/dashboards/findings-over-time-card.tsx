/**
 * Dashboard 1, as a propless card the Overview mounts.
 *
 * Propless and fleet-scoped on purpose: with no repository named the wider answer is the true
 * one, and the route echoes back which scope it gave.
 *
 * Three sentences under the chart carry what the bars cannot say for themselves:
 *
 * - **The dates are Sync's, not the vendors'.** `created_at` is when Sync first recorded the
 *   claim. A reader looking at dated bars of API findings assumes the vendor's publication
 *   timeline, and nothing in the graph can supply one — the nearest field is a detection date too.
 * - **A gap is not a zero.** Nothing records that DETECT ran, so a day with no bar is a day
 *   nothing was recorded, which may be a day with no changes or a day with no run.
 * - **The series counts findings as produced, including ones since closed**, because a series
 *   filtered to still-open findings shrinks its own past every time a patch lands. The
 *   outstanding count sits beside it rather than replacing it.
 */

import { useCallback } from "react"

import { useFindingsOverTime } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { MetricPanel } from "@/components/metric-panel"
import { EmptyState, ErrorState, LoadingState } from "@/components/states"
import { buildFindingsOverTimeOption } from "@/features/dashboards/findings-over-time-option"

const EMPTY = {
  repo_id: null,
  severities: [],
  days: [],
  by_rung: {},
  total: 0,
  still_open: 0,
}

export function FindingsOverTimeCard() {
  const query = useFindingsOverTime(null)

  const build = useCallback(
    (tokens: ChartTokens) => buildFindingsOverTimeOption(query.data ?? EMPTY, tokens),
    [query.data],
  )

  if (query.isPending) return <LoadingState what="findings over time" />
  if (query.isError) {
    return (
      <ErrorState error={query.error} what="findings over time" onRetry={() => void query.refetch()} />
    )
  }

  const payload = query.data
  const rungs = Object.entries(payload.by_rung).sort(([a], [b]) => a.localeCompare(b))

  return (
    <MetricPanel
      label="What Sync has found, over time"
      caption={
        <p className="max-w-prose">
          Findings by severity, on the day Sync recorded them. This is Sync&apos;s own timeline
          rather than the vendors&apos; — a bar sits on the day a detector raised the claim, not
          the day the API changed, and the distance between those is however long a feed took to
          arrive and a run took to happen. Nothing in the graph carries a publication date to draw
          instead.
        </p>
      }
    >
      {payload.days.length === 0 ? (
        <EmptyState
          headline="No finding has been recorded."
          detail="The graph holds no finding at any severity, so there is no series to draw. This is a read that found nothing rather than a read that did not happen — but it is also a young deployment, so an empty chart means DETECT has produced nothing yet, not that anything was lost."
          command="uv run sync run --repo <git-remote> --vendor <vendor> --from-version <a> --to-version <b>"
        />
      ) : (
        <div className="flex flex-col gap-field">
          <div className="h-64 w-full">
            <EChart
              buildOption={build}
              ariaLabel="Findings by severity, by the day Sync recorded them"
              style={{ height: "100%", width: "100%" }}
            />
          </div>

          <p className="text-meta text-ink-muted leading-relaxed">
            {payload.total.toLocaleString()} findings recorded across{" "}
            {payload.days.length.toLocaleString()}{" "}
            {payload.days.length === 1 ? "day" : "days"}, of which{" "}
            {payload.still_open.toLocaleString()} {payload.still_open === 1 ? "is" : "are"} still
            open. The bars count findings as produced, including ones since patched or abandoned —
            a series filtered to what is still open would shrink its own past every time work
            landed.{" "}
            <span className="text-ink">A day with no bar is a day nothing was recorded</span>,
            never a day measured at nought: nothing here records that a detector ran, so an absent
            day may be one with no changes or one with no run, and those are different facts.
          </p>

          <p className="text-meta text-ink-muted leading-relaxed">
            These findings rest on:{" "}
            {rungs.map(([rung, count], index) => (
              <span key={rung}>
                {index > 0 && ", "}
                <span className="font-mono">{rung}</span> {count.toLocaleString()}
              </span>
            ))}
            . A rung travels with every figure derived from a binding, because a false positive
            that cannot be attributed to one cannot be fixed.
          </p>
        </div>
      )}
    </MetricPanel>
  )
}
