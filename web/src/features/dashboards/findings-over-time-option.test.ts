/**
 * Dashboard 1's chart option, against decision 58.
 *
 * The interesting half is the legend, because this is the one chart of mine whose series count
 * varies with the data: five severities exist in the vocabulary, and a window where only one
 * occurred should not carry a legend naming it.
 */

import { describe, expect, it } from "vitest"

import type { FindingsOverTimeResponse } from "@/api/types"
import { CHART_TOKENS, expectQuietChart } from "@/components/charts/chart-test-support"
import { buildFindingsOverTimeOption } from "@/features/dashboards/findings-over-time-option"

const payload = (days: FindingsOverTimeResponse["days"]): FindingsOverTimeResponse => ({
  repo_id: null,
  severities: ["breaking", "warning", "deprecation", "addition", "info"],
  days,
  by_rung: {},
  total: 0,
  still_open: 0,
})

describe("buildFindingsOverTimeOption", () => {
  it("draws a band only for a severity that actually occurred", () => {
    const option = buildFindingsOverTimeOption(
      payload([{ day: "2026-08-16", counts: { breaking: 2 } }]),
      CHART_TOKENS,
    ) as Record<string, any>

    expect(option.series).toHaveLength(1)
    expect(option.series[0].name).toBe("breaking")
  })

  it("carries no legend when one severity occurred, because it would name the obvious", () => {
    const option = buildFindingsOverTimeOption(
      payload([{ day: "2026-08-16", counts: { breaking: 2 } }]),
      CHART_TOKENS,
    ) as Record<string, any>

    expectQuietChart(option)
    expect(option.legend).toBeUndefined()
  })

  it("carries a legend once two severities occurred", () => {
    const option = buildFindingsOverTimeOption(
      payload([{ day: "2026-08-16", counts: { breaking: 2, warning: 1 } }]),
      CHART_TOKENS,
    ) as Record<string, any>

    expect(option.series).toHaveLength(2)
    expectQuietChart(option)
    expect(option.legend).toBeDefined()
  })

  /** A gap stays a gap: the axis is categorical over days that have rows. */
  it("plots only the days the payload carried", () => {
    const option = buildFindingsOverTimeOption(
      payload([
        { day: "2026-08-16", counts: { breaking: 1 } },
        { day: "2026-08-18", counts: { breaking: 1 } },
      ]),
      CHART_TOKENS,
    ) as Record<string, any>

    expect(option.xAxis.data).toEqual(["2026-08-16", "2026-08-18"])
  })

  it("keeps the severities in the vocabulary's order, never by volume", () => {
    const option = buildFindingsOverTimeOption(
      payload([{ day: "2026-08-16", counts: { warning: 9, breaking: 1 } }]),
      CHART_TOKENS,
    ) as Record<string, any>

    expect(option.series.map((s: { name: string }) => s.name)).toEqual(["breaking", "warning"])
  })
})
