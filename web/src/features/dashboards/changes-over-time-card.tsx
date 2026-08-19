/**
 * Dashboard T3: what the watched integrations published, by the day Sync detected it.
 *
 * **Its subject is the vendors' activity, where the findings series beside it is Sync's**, and
 * that is why both belong on this screen rather than either standing for the other. A day with
 * many changes and no findings is a day the vendors moved and nothing they moved touched this
 * codebase — which is the product working, not a gap in the data.
 *
 * **The dates are detection dates.** Nothing in the graph carries a vendor publication date; the
 * nearest field is when an adapter noticed. A reader looking at dated bars of API changes
 * supplies the vendor's timeline unless told otherwise, so the caption tells them.
 *
 * **A gap is not a zero**, the same rule the findings series carries: nothing records that an
 * adapter ran, so a day with no bar is a day nothing was recorded — which may be a day no vendor
 * published or a day nothing fetched.
 *
 * **Fleet-wide, and it says so.** A change is a fact about the vendor, so this series is not
 * narrowed to a repository — matching the feed it summarises rather than implying a scope the
 * query does not have.
 *
 * **One caveat this chart owes and no other does.** `oasdiff` returns a different answer on
 * consecutive runs over identical bytes, which `CLAUDE.md` names as the pipeline's single
 * idempotency exemption. So a day's height over that source is at-least-once rather than a
 * measurement, and the note beneath says which.
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
import { ErrorState, LoadingState } from "@/components/states"

interface ChangesOverTime {
  vendor_id: string | null
  vendors: string[]
  days: DayEntry[]
  total: number
}

async function fetchChangesOverTime(signal?: AbortSignal): Promise<ChangesOverTime> {
  const path = "/api/integration-changes/over-time"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as ChangesOverTime
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

export function ChangesOverTimeCard() {
  const query = useQuery({
    queryKey: ["integration-changes", "over-time"],
    queryFn: ({ signal }) => fetchChangesOverTime(signal),
  })

  const days = query.data?.days ?? []
  const vendors = query.data?.vendors ?? []
  const build = useCallback(
    (tokens: ChartTokens) =>
      buildDayStackOption({ days, members: vendors, stackId: "changes" }, tokens),
    [days, vendors],
  )

  if (query.isPending) return <LoadingState what="integration changes over time" />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what="integration changes over time"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const hint = (
    <InfoHint label="About integration changes over time">
      Every change the watched integrations published, stacked by integration, on the day Sync
      detected it. This is the vendors&rsquo; activity — the findings series beside it is
      Sync&rsquo;s, and a day with changes and no findings is a day nothing the vendors shipped
      touched this codebase. Fleet-wide rather than scoped to this workspace, because what a
      vendor publishes is a fact about the vendor.
    </InfoHint>
  )

  if (days.length === 0) {
    return (
      <MetricPanel
        label="Integration changes over time"
        hint={hint}
        caption="No integration change has been recorded on any day."
      >
        <p className="max-w-prose text-body text-ink-muted">
          Nothing to draw. No adapter has delivered a change yet, so there is no day with a
          height — which is the absence of a record rather than a stretch of quiet vendors.
        </p>
      </MetricPanel>
    )
  }

  return (
    <MetricPanel
      label="Integration changes over time"
      hint={hint}
      caption="Changes by the day Sync detected them, stacked by integration. Detection dates, never vendor publication dates — the graph holds no publication date."
      metric={{ value: query.data.total.toLocaleString(), unit: "changes across the window" }}
    >
      <EChart
        buildOption={build}
        ariaLabel="Integration changes per day, stacked by integration"
        style={{ height: 260 }}
      />
      <p className="max-w-prose text-meta text-ink-muted">
        A day with no bar is a day nothing was recorded, which may be a day no vendor published or
        a day nothing fetched — the graph does not record that an adapter ran, so it cannot tell
        you which. And a height over an <code className="font-mono">oasdiff</code> source is
        at-least-once rather than a measurement: that tool returns a different answer on
        consecutive runs over identical bytes, which is this pipeline&rsquo;s one recorded
        exemption from converging.
      </p>
    </MetricPanel>
  )
}
