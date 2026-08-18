import { describe, expect, it } from "vitest"

import type { ChartTokens } from "@/components/charts/echart"
import type { VendorChangeRow } from "@/api/types"
import {
  buildVendorChangeVolumeOption,
  extractVendorChangeVolume,
} from "@/features/vendors/vendor-change-chart-option"

const DUMMY_TOKENS: ChartTokens = {
  ink: "#fff",
  inkSecondary: "#aaa",
  inkMuted: "#666",
  surface: "#111",
  grid: "#222",
  axis: "#333",
  labelOnLight: "#000",
  series: ["#f00", "#0f0", "#00f", "#ff0"],
}

describe("vendor-change-chart-option", () => {
  it("extracts monthly buckets and kinds correctly", () => {
    const items: VendorChangeRow[] = [
      {
        operation: "PostCharges",
        change_kind: "breaking",
        path_ptr: "/v1/charges",
        severity: "breaking",
        from_version: "v1",
        to_version: "v2",
        published_at: "2026-06-15T10:00:00Z",
      },
      {
        operation: "GetCharges",
        change_kind: "parameter_removed",
        path_ptr: "/v1/charges",
        severity: "warning",
        from_version: "v2",
        to_version: "v3",
        published_at: "2026-06-20T14:00:00Z",
      },
      {
        operation: "CreateCustomer",
        change_kind: "breaking",
        path_ptr: "/v1/customers",
        severity: "breaking",
        from_version: "v3",
        to_version: "v4",
        published_at: "2026-07-05T09:00:00Z",
      },
    ]

    const data = extractVendorChangeVolume(items)
    expect(data.periods).toEqual(["2026-06", "2026-07"])
    expect(data.kinds).toEqual(["breaking", "parameter_removed"])
    expect(data.totalChanges).toBe(3)
    expect(data.countsByPeriodAndKind["2026-06"]["breaking"]).toBe(1)
    expect(data.countsByPeriodAndKind["2026-06"]["parameter_removed"]).toBe(1)
    expect(data.countsByPeriodAndKind["2026-07"]["breaking"]).toBe(1)

    const option = buildVendorChangeVolumeOption(data, DUMMY_TOKENS)
    expect(option.animation).toBe(false)
    expect(option.series.length).toBe(2)
    expect(option.xAxis.data).toEqual(["2026-06", "2026-07"])
  })

  it("handles empty items safely", () => {
    const data = extractVendorChangeVolume([])
    expect(data.periods).toEqual([])
    expect(data.kinds).toEqual([])
    expect(data.totalChanges).toBe(0)

    const option = buildVendorChangeVolumeOption(data, DUMMY_TOKENS)
    expect(option.series).toEqual([])
  })
})
