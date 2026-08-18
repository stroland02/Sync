/**
 * Dashboard 6: why runs gave up, over the closed vocabulary — derivation and echarts option.
 *
 * `abandon_reason` stays free text on the row. This aggregates the *code* beside it, which is
 * `B128`'s whole argument: two runs that abandoned for the same cause read differently in prose
 * and group together here, so "which change kinds are not mechanically safe, and why" is a query
 * rather than a substring match. `CLAUDE.md` puts it plainly — abandoned runs are data, and this
 * is where routing learns from them.
 *
 * **The grain is one attempt, not one finding.** `migration_outcome`'s grain comment is explicit
 * and this module honours it in its naming: every total here says `attempts`, because a finding
 * retried three times contributes three. A chart labelled "findings" over this data would be
 * wrong, and wrong quietly.
 *
 * **A null code is not `unclassified`.** `unclassified` is a real member of the vocabulary: a run
 * reached the fallback because no routing path claimed it, which is a fact about routing. A null
 * is a row recorded before the column existed, which is a fact about a schema migration. Folding
 * the second into the first would manufacture routing evidence out of history, so `uncoded` is
 * kept separate and rendered as never-recorded rather than drawn as a bar.
 *
 * **A code nobody hit is a measured nought.** The corpus was read and held none, which is why
 * `unhitCodeCount` is reported rather than the missing codes being silently absent — but they are
 * not drawn as twelve mostly-empty bars either, because a ranked chart of zeroes hides the ranking
 * that is the point.
 *
 * **No composite and no ratio.** Counts over a closed vocabulary, which is the one thing
 * `2026-08-18-dashboards.md` permits a chart to render.
 */

import type { AbandonmentResponse } from "@/api/types"
import { escapeHtml } from "@/components/charts/chart-text"
import type { ChartTokens } from "@/components/charts/echart"
import type { EChartsOption } from "echarts-for-react"

/**
 * `sync.remediate.state.AbandonReasonCode`, in the order that module declares it.
 *
 * Duplicated from Python deliberately and narrowly: it is a closed vocabulary the payload keys
 * on, and the console needs to know how many members exist in order to say how many nobody hit.
 * `undeclaredCodes` is what stops the copy going stale silently — a code the payload carries and
 * this list does not is reported on screen rather than dropped.
 */
export const ABANDON_REASON_CODES = [
  "locate_failed",
  "prepare_failed",
  "patch_attempts_exhausted",
  "static_verify_fault",
  "static_verify_exhausted",
  "replay_exhausted",
  "push_failed",
  "ci_poll_failed",
  "ci_attempts_exhausted",
  "ci_feedback_patch_budget_exhausted",
  "open_pr_failed",
  "unclassified",
] as const

/** The key the payload uses for an attempt whose code column predates the column. */
const UNCODED_KEY = "null"

export interface ReasonSlice {
  readonly code: string
  readonly attempts: number
}

export interface AbandonReasonDistribution {
  /** Codes with at least one attempt, most first, ties broken on the code. */
  readonly ranked: readonly ReasonSlice[]
  /** Abandoned attempts carrying a code. Attempts, never findings. */
  readonly totalAbandonedAttempts: number
  /** Abandoned attempts recorded before `abandon_reason_code` existed. Never a bar. */
  readonly uncoded: number
  /** Vocabulary members no attempt reached. A measured nought, not an absence. */
  readonly unhitCodeCount: number
  /** Codes the payload carried that `ABANDON_REASON_CODES` does not declare. */
  readonly undeclaredCodes: readonly string[]
}

export function abandonReasonDistribution(
  payload: AbandonmentResponse,
): AbandonReasonDistribution {
  const totals = new Map<string, number>()
  let uncoded = 0

  for (const group of payload.groups) {
    for (const [code, count] of Object.entries(group.abandon_reason_codes)) {
      if (code === UNCODED_KEY) {
        uncoded += count
        continue
      }
      totals.set(code, (totals.get(code) ?? 0) + count)
    }
  }

  const ranked = [...totals.entries()]
    .map(([code, attempts]) => ({ code, attempts }))
    .sort((a, b) => b.attempts - a.attempts || a.code.localeCompare(b.code))

  const declared = new Set<string>(ABANDON_REASON_CODES)

  return {
    ranked,
    totalAbandonedAttempts: ranked.reduce((sum, slice) => sum + slice.attempts, 0),
    uncoded,
    unhitCodeCount: ABANDON_REASON_CODES.filter((code) => !totals.has(code)).length,
    undeclaredCodes: ranked.map((slice) => slice.code).filter((code) => !declared.has(code)),
  }
}

/**
 * Horizontal ranked bars in one colour.
 *
 * One colour rather than twelve: on this console colour carries a change kind, a rung or a run
 * outcome, and a reason for giving up is none of the three. Twelve hues would read as a severity
 * ordering across the vocabulary, which nothing measured — and decision 5 permits a categorical
 * palette while refusing exactly that kind of ramp.
 */
export function buildAbandonReasonsOption(
  distribution: AbandonReasonDistribution,
  tokens: ChartTokens,
): EChartsOption {
  const codes = distribution.ranked.map((slice) => slice.code)
  const attempts = distribution.ranked.map((slice) => slice.attempts)

  return {
    grid: { left: 8, right: 32, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (params: unknown) => {
        const { name, value } = params as { name: string; value: number }
        return `${escapeHtml(name)}<br/>${value} ${value === 1 ? "attempt" : "attempts"}`
      },
    },
    xAxis: {
      type: "value",
      minInterval: 1,
      axisLine: { lineStyle: { color: tokens.axis } },
      axisLabel: { color: tokens.inkMuted },
      splitLine: { lineStyle: { color: tokens.grid } },
    },
    yAxis: {
      type: "category",
      // Reversed because echarts draws a category axis bottom-up and the ranking reads top-down.
      data: [...codes].reverse(),
      axisLine: { lineStyle: { color: tokens.axis } },
      axisTick: { show: false },
      axisLabel: { color: tokens.ink },
    },
    series: [
      {
        type: "bar",
        data: [...attempts].reverse(),
        barMaxWidth: 16,
        itemStyle: { color: tokens.series[0] },
        label: { show: true, position: "right", color: tokens.inkMuted },
      },
    ],
  }
}
