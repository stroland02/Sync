/**
 * How often this vendor publishes changes, and of what kind.
 *
 * **The total is the vendor's, and it used to be a page's.** This component took
 * `VendorChangeRow[]` -- whichever page of the changes table was loaded -- aggregated it in the
 * browser and printed the result as "total changes". It was wrong by an amount that changed when a
 * reader paginated: plausible on every screen and never right, which is the worst shape a wrong
 * figure takes because nothing ever contradicts it. Found by Lane H under a dead link.
 *
 * It reads `GET /api/vendors/{vendor_id}/change-volume` now, which counts every change the vendor
 * has. The client-side aggregate is deleted rather than left beside the call.
 *
 * `M0-W329` dashboard 4.
 */

import { useCallback, useMemo } from "react"

import { useVendorChangeVolume } from "@/api/queries"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { Absent } from "@/components/status"
import { ErrorState, LoadingState } from "@/components/states"
import {
  buildVendorChangeVolumeOption,
  vendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"

export function VendorChangeVolumeChart({ vendorId }: { vendorId: string }) {
  const query = useVendorChangeVolume(vendorId)
  const payload = query.data

  const data = useMemo(
    () => (payload === undefined ? null : vendorChangeVolume(payload)),
    [payload]
  )

  const build = useCallback(
    (tokens: ChartTokens) =>
      buildVendorChangeVolumeOption(
        data ?? { periods: [], kinds: [], countsByPeriodAndKind: {}, periodTotals: [], totalChanges: 0 },
        tokens
      ),
    [data]
  )

  if (query.isPending) return <LoadingState what={`${vendorId}'s change history`} />
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        what={`${vendorId}'s change history`}
        onRetry={() => void query.refetch()}
      />
    )
  }

  return (
    <div className="flex flex-col gap-field rounded-panel border border-border bg-card p-section">
      <div className="flex items-center justify-between text-meta text-muted-foreground">
        <span>Change volume, all time</span>
        {/* The vendor's own count, not this view's. A confirmed zero prints as a number; an answer
            that never arrived is the pending branch above and never reaches here, so there is no
            default to conflate the two. */}
        <span className="font-mono">
          {payload === undefined ? (
            <Absent>not counted</Absent>
          ) : (
            `${payload.total_changes.toLocaleString()} changes published`
          )}
        </span>
      </div>
      {data !== null && data.totalChanges === 0 ? (
        <p className="text-meta text-muted-foreground">
          This vendor has published no change Sync has seen. That is a counted zero, not an
          unanswered question -- the timeline below is empty because there is nothing in it.
        </p>
      ) : (
        <div className="h-44 w-full">
          <EChart
            buildOption={build}
            ariaLabel={`Change volume for ${vendorId}, all time`}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
    </div>
  )
}
