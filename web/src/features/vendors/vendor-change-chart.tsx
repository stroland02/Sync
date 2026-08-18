/**
 * Vendor change volume chart over time and kind breakdown.
 *
 * M0-W329 Dashboard 4: Vendor change volume, per vendor, over time.
 */

import { useCallback, useMemo } from "react"

import type { VendorChangeRow } from "@/api/types"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import {
  buildVendorChangeVolumeOption,
  extractVendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"

export function VendorChangeVolumeChart({
  changes,
  vendorId,
}: {
  changes: VendorChangeRow[]
  vendorId: string
}) {
  const data = useMemo(() => extractVendorChangeVolume(changes), [changes])

  const build = useCallback(
    (tokens: ChartTokens) => buildVendorChangeVolumeOption(data, tokens),
    [data],
  )

  if (changes.length === 0) {
    return null
  }

  return (
    <div className="flex flex-col gap-2 rounded-panel border border-border bg-card p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Change Volume Timeline</span>
        <span className="font-mono">{changes.length} total changes</span>
      </div>
      <div className="h-44 w-full">
        <EChart
          buildOption={build}
          ariaLabel={`Vendor change volume for ${vendorId}`}
          style={{ height: "100%", width: "100%" }}
        />
      </div>
    </div>
  )
}
