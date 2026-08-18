/**
 * Dashboard 7: observed-call volume per operation — derivation and echarts option.
 *
 * The telemetry rung, asked the one question the other rungs cannot answer: not *does this code
 * call the operation* but *did anything actually call it, and how much*.
 *
 * **Never-measured is not nought, and this dashboard exists because of that distinction.**
 * `telemetry_attached_at` decides it (B157). With no telemetry attached, nobody looked, and the
 * honest answer is an absence — not a bar of height zero, which would state that traffic was
 * watched for and never arrived. With telemetry attached and no rows, nought is the measurement.
 * The derivation reports the two as different states rather than as one empty list.
 *
 * **Every operation carries the rungs its rows arrived at, and never just the strongest.** A rung
 * is a column rather than a join, and an operation seen once correlated and once uncorrelated is
 * two facts. Collapsing to `observed` would claim a correlation for traffic that never got one.
 *
 * **An aggregate over one page is not a total.** `calls` is paginated, so summing `items` and
 * printing the result as the operation's volume is a false figure of exactly the kind this
 * console refuses. `countedRows`, `totalRows` and `complete` travel with the answer so the frame
 * can say what it counted over, and the ranking can be described as provisional when it is.
 *
 * **Errors stay a count.** `error_count` sits beside `call_count`, never divided into it. A
 * failure rate is a ratio averaging two facts, which the refusals name directly.
 *
 * **One point is not a trend.** `drawable` is false for a series with fewer than two days, so the
 * frame can print the figure instead of drawing a line whose slope nothing measured.
 */

import type { ObservedTelemetryResponse } from "@/api/types"
import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

/** Below two distinct days there is no direction to read, only a point. */
const DRAWABLE_MIN_DAYS = 2

export interface VolumePoint {
  readonly day: string
  readonly calls: number
}

export interface OperationVolume {
  readonly operationId: string
  readonly vendorId: string
  /** Calls summed over the rows this page holds. Never described as the operation's total. */
  readonly calls: number
  /** Failures, as a count. Never divided by `calls`. */
  readonly errors: number
  /** Every rung this operation's rows arrived at, sorted. Never collapsed to one. */
  readonly rungs: readonly string[]
  readonly series: readonly VolumePoint[]
  /** Whether the series spans enough days to draw a direction from. */
  readonly drawable: boolean
}

export interface ObservedVolume {
  /** Whether anything ever looked. `false` is never-measured, not a volume of nought. */
  readonly telemetryAttached: boolean
  readonly attachedAt: string | null
  readonly operations: readonly OperationVolume[]
  readonly countedRows: number
  readonly totalRows: number
  /** Whether `countedRows` is every row, or only the page this answer was built from. */
  readonly complete: boolean
}

function day(iso: string): string {
  return iso.slice(0, 10)
}

export function observedVolumeByOperation(payload: ObservedTelemetryResponse): ObservedVolume {
  const attachedAt = payload.telemetry_attached_at
  const items = payload.calls.items

  const grouped = new Map<
    string,
    { vendorId: string; calls: number; errors: number; rungs: Set<string>; days: Map<string, number> }
  >()

  for (const row of items) {
    const existing = grouped.get(row.operation_id) ?? {
      vendorId: row.vendor_id,
      calls: 0,
      errors: 0,
      rungs: new Set<string>(),
      days: new Map<string, number>(),
    }
    existing.calls += row.call_count
    existing.errors += row.error_count
    existing.rungs.add(row.binding_rung)
    const key = day(row.first_seen)
    existing.days.set(key, (existing.days.get(key) ?? 0) + row.call_count)
    grouped.set(row.operation_id, existing)
  }

  const operations = [...grouped.entries()]
    .map(([operationId, row]) => {
      const series = [...row.days.entries()]
        .map(([d, calls]) => ({ day: d, calls }))
        .sort((a, b) => a.day.localeCompare(b.day))
      return {
        operationId,
        vendorId: row.vendorId,
        calls: row.calls,
        errors: row.errors,
        rungs: [...row.rungs].sort(),
        series,
        drawable: series.length >= DRAWABLE_MIN_DAYS,
      }
    })
    .sort((a, b) => b.calls - a.calls || a.operationId.localeCompare(b.operationId))

  return {
    telemetryAttached: attachedAt !== null,
    attachedAt,
    operations,
    countedRows: items.length,
    totalRows: payload.calls.total,
    complete: items.length === payload.calls.total,
  }
}

/**
 * One operation's volume over time, as a sparkline.
 *
 * Deliberately unlabelled and axis-free: it sits inside a table row beside the figure it
 * summarises, so the number is already on screen and repeating it would be the fact written
 * twice. It carries no colour meaning — one series in one token — because a volume is not a
 * change kind, a rung or a run outcome, which are the only three things colour speaks here.
 */
export function buildOperationSparklineOption(
  series: readonly VolumePoint[],
  tokens: ChartTokens,
): EChartsOption {
  return {
    grid: { left: 2, right: 2, top: 4, bottom: 2 },
    tooltip: {
      trigger: "axis",
      formatter: (params: unknown) => {
        const points = params as Array<{ name: string; value: number }>
        const point = points[0]
        if (point === undefined) return ""
        const calls = point.value === 1 ? "call" : "calls"
        return `${escapeHtml(point.name)}<br/>${point.value} ${calls}`
      },
    },
    xAxis: { type: "category", show: false, data: series.map((p) => p.day) },
    yAxis: { type: "value", show: false, min: 0 },
    series: [
      {
        type: "line",
        data: series.map((p) => p.calls),
        smooth: false,
        symbol: "none",
        lineStyle: { width: 1.5, color: tokens.series[0] },
        areaStyle: { color: tokens.series[0], opacity: 0.12 },
      },
    ],
  }
}
