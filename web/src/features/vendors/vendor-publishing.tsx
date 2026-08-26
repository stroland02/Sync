/**
 * How much this integration has published, and of what kind — the last section of the rail pane.
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
 * **A section rather than its own pane, and that is a measurement.** It was a fourth pane until
 * 1366×768 said otherwise: four bounded panes, each with a head, a pinned provenance strip and a
 * pager, left the record's table eighteen pixels of rows and clipped the pane that held it. This
 * belongs beside the adapter that delivered these rows anyway — both are counted over the vendor,
 * in every repository, which is the rail's one scope.
 */

import { useCallback, useMemo } from "react"

import { useVendorChangeVolume } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { RankedBars } from "@/components/ranked-bars"
import { RelativeTime } from "@/components/relative-time"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import {
  buildVendorChangeVolumeOption,
  vendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"
import { publishingForm, rankedTally } from "@/features/vendors/vendor-record"

export function VendorPublishing({ vendorId }: { vendorId: string }) {
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
    <section className="flex min-w-0 flex-col gap-row">
      <h3 className="furniture text-meta text-ink-muted">What has come through it</h3>

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

      {/* The span is the fact the bars cannot carry: two vendors with the same twelve rows are not
          the same integration if one published them over a year and the other in a week. */}
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
    </section>
  )
}
