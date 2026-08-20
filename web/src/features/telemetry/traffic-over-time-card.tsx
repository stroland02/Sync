/**
 * Requests and errors per hour — the live-signals page's time dimension.
 *
 * Reuses the day-stack builder at hour grain rather than growing a third option shape: two
 * bands partitioning one count (errored + succeeded = requests), so the stack's height is the
 * request count and the legend carries identity. Errors sit on the baseline where a change in
 * their share reads as a change in shape, not just height.
 *
 * The honesty caveat is the bucketing's: a span carries no timestamp of its own, so every span
 * lands on the hour its unit of work began. Stated under the chart because a reader supplies
 * per-request times unless told otherwise.
 */

import { useCallback } from "react"

import type { TrafficBucket } from "@/api/types"
import { buildDayStackOption } from "@/components/charts/day-stack-option"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { MetricPanel } from "@/components/metric-panel"
import { TRAFFIC_MEMBERS, seriesToDays } from "@/features/telemetry/traffic"

export function TrafficOverTimeCard({ series }: { series: TrafficBucket[] }) {
  const days = seriesToDays(series)
  const build = useCallback(
    (tokens: ChartTokens) =>
      buildDayStackOption({ days, members: TRAFFIC_MEMBERS, stackId: "traffic" }, tokens),
    [days],
  )

  if (series.length === 0) return null

  return (
    <MetricPanel
      label="Traffic over time"
      hint={
        <InfoHint label="About traffic over time">
          Statused requests per hour, split into errored and succeeded — the two partition the
          count, so a bar&rsquo;s height is the requests that hour. An hour with no bar is an hour
          nothing was recorded, which may be quiet traffic or nothing watching; the graph cannot
          say which, so neither does this.
        </InfoHint>
      }
      caption="Each span lands on the hour its unit of work began — spans carry no time of their own."
    >
      <EChart
        buildOption={build}
        ariaLabel="Observed requests per hour, split into errored and succeeded"
        style={{ height: 220 }}
      />
    </MetricPanel>
  )
}
