/**
 * How much this integration has published, and of what kind — the rail's lower pane.
 *
 * **The form is chosen from the payload, which is the whole point of this file.** `web/CLAUDE.md`
 * learned twice that a chart must be able to draw its own data. `vendor-change-chart.tsx` (deleted)
 * always drew a monthly stacked bar; measured against the seeded corpus every vendor's changes land
 * in one month, so it rendered one column beside a ten-member legend and told a reader nothing. The
 * form now comes from `publishingForm`: two or more periods draw the timeline, one period ranks the
 * kinds instead, and a counted zero is a sentence rather than an empty axis.
 *
 * **Bars, not a ring, for the kinds.** Change kinds are oasdiff rule ids — over two hundred of them
 * — so the members on any one vendor are a subset the reader cannot name as a whole, and a kind at
 * nought is meaningful. A bar of length zero still has a row, a label and a count.
 *
 * **The total is the vendor's, and it used to be a page's.** This figure counts every change the
 * vendor has rather than whichever page of the changes table was loaded. Both readings are on
 * screen because they are different facts, and the record pane's own foot says which is which.
 */

import { useCallback, useMemo } from "react"
import { BarChart3 } from "lucide-react"

import { useVendorChangeVolume } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { InfoHint } from "@/components/info-hint"
import { PanelPane } from "@/components/pane"
import { RankedBars } from "@/components/ranked-bars"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import {
  buildVendorChangeVolumeOption,
  vendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"
import { publishingForm, rankedTally } from "@/features/vendors/vendor-record"

export function VendorPublishingPane({ vendorId }: { vendorId: string }) {
  const query = useVendorChangeVolume(vendorId)
  const payload = query.data

  const data = useMemo(
    () => (payload === undefined ? null : vendorChangeVolume(payload)),
    [payload],
  )

  const build = useCallback(
    (tokens: ChartTokens) =>
      buildVendorChangeVolumeOption(
        data ?? {
          periods: [],
          kinds: [],
          countsByPeriodAndKind: {},
          periodTotals: [],
          totalChanges: 0,
        },
        tokens,
      ),
    [data],
  )

  const form = payload === undefined ? null : publishingForm(payload)

  return (
    <PanelPane
      label="What this integration publishes"
      icon={BarChart3}
      hint={
        <InfoHint label={`About ${vendorId}'s publishing record`}>
          <p>
            Every change row Sync holds for {vendorId}, counted over the vendor rather than over any
            one repository — a vendor publishes a change once, to everyone.
          </p>
          <p>
            These rows are recorded at least once rather than exactly once: comparing the same two
            published specifications twice can return a different set. So the figure is a count of
            rows the feed produced, not a measurement of how often the vendor changed something.
          </p>
          <p>
            The shape drawn depends on what the record can support. One period of history has no
            shape over time, so the kinds are ranked instead and the span is stated in words.
          </p>
        </InfoHint>
      }
      bodyClassName="flex min-w-0 flex-col gap-section p-section"
    >
      {query.isPending && <LoadingState what={`${vendorId}'s publishing record`} />}
      {query.isError && (
        <ErrorState
          error={query.error}
          what={`${vendorId}'s publishing record`}
          onRetry={() => void query.refetch()}
        />
      )}

      {payload !== undefined && form !== null && form.kind === "none" && (
        <p className="max-w-prose text-meta text-ink-muted">
          {vendorId} has published no change Sync has seen. That is a counted zero, not an
          unanswered question — there is nothing here to draw rather than a read that failed.
        </p>
      )}

      {payload !== undefined && form !== null && form.kind === "kinds" && (
        <RankedBars
          label={`${payload.total_changes.toLocaleString()} change rows, by kind`}
          caption={
            form.period === null
              ? `Counted over every change row Sync holds for ${vendorId}, in every repository. Each bar's width is its share of the largest kind, not of the total.`
              : `Counted over every change row Sync holds for ${vendorId}, in every repository — all of them published in ${form.period}, so there is no shape over time to draw. Each bar's width is its share of the largest kind, not of the total.`
          }
          rows={rankedTally(payload.by_kind)}
          unit="change rows"
          colourByKey={false}
          max={6}
        />
      )}

      {payload !== undefined && form !== null && form.kind === "timeline" && (
        <div className="flex min-w-0 flex-col gap-field">
          <div className="flex items-baseline justify-between gap-row text-meta text-ink-muted">
            <span>
              {payload.total_changes.toLocaleString()} change rows across {form.periods} months
            </span>
            <span className="font-mono">stacked by kind</span>
          </div>
          <div className="h-44 w-full">
            <EChart
              buildOption={build}
              ariaLabel={`Change rows published by ${vendorId}, by month and kind`}
              style={{ height: "100%", width: "100%" }}
            />
          </div>
        </div>
      )}

      {/* The span is the fact the ranked bars cannot carry: two vendors with the same twelve rows
          are not the same integration if one published them over a year and the other in a week.
          In the body rather than a pinned foot — a 40px foot on a 158px pane at 1366×768 is a
          quarter of the chart. */}
      {payload !== undefined &&
        (payload.oldest_change_at === null || payload.newest_change_at === null ? (
          <p className="text-meta text-ink-muted">
            <Absent>no change recorded, so there is no span to state</Absent>
          </p>
        ) : (
          <p className="max-w-prose text-meta text-ink-muted">
            Published between <RelativeTime iso={payload.oldest_change_at} /> and{" "}
            <RelativeTime iso={payload.newest_change_at} /> — the span of the record, not a promise
            the feed is current.
          </p>
        ))}
    </PanelPane>
  )
}
