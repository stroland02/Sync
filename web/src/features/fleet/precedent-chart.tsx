/**
 * The disposition chart.
 *
 * **The two KPI figures that opened this component are gone from it, and neither is gone from the
 * screen.** `attempts` is the fact rail's fourth tile and has been since M7-W163; rendering it here
 * as well put one number on screen twice at the same weight, which is the fact-written-twice defect
 * that ruling reversed. `distinct_findings` moved up into the panel's own metric slot, directly
 * above this chart, where `docs/superpowers/briefs/2026-08-07-substrate-fleet.md` records the whole
 * mapping. What is left here is the chart and the sentence that qualifies it.
 *
 * Disposition is the only `migration_outcome` dimension charted: `strategy` (read
 * from `sync.core.PatchStrategy`, a two-value literal) and `tier` (read from
 * `sync.remediate.corpus._TIERS`, which only ever writes 0 or 2) each carry two
 * classes, and `terminal_status` carries the handful `sync.remediate.nodes` records
 * (`tests/test_corpus_writer.py` holds the census) — all far under the
 * class-count ceiling a table would need instead. Strategy and tier stay tables
 * because a two-segment bar states nothing a two-row table doesn't, not because
 * they failed a count; disposition earns the chart because a stacked bar is the
 * form for part-to-whole, and it is the identity axis this screen's own grain rule
 * cares about.
 */
import { useCallback } from "react"

import type { PrecedentSummary, Tally } from "@/api/types"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import {
  INLINE_LABEL_SHARE_FLOOR,
  escapeHtml,
  labelInkFor,
} from "@/components/charts/chart-text"

/**
 * Disposition -> series slot, keyed on the value itself rather than where it lands in the
 * sorted tally, so a colour is the segment's identity and not its alphabetical rank.
 * The vocabulary is what `sync.remediate.nodes` records (`tests/test_corpus_writer.py`'s
 * census is the authority) plus the "null" `sync.dashboard.fleet._grouped` synthesises for
 * a row whose column was never written; check this table against that census before
 * changing it.
 *
 * "opened" and "abandoned" are the pair an operator most needs to tell apart at a glance —
 * a repair that landed versus one Sync gave up on — so they sit five slots apart in the
 * fixed series order rather than next to each other. Neither takes the green or red slot:
 * `DESIGN.md`'s series palette is identity, not a verdict, the same rule `run-outcome.tsx:21-23`
 * applies to this same field, and an abandoned run is not an error.
 */
const DISPOSITION_SLOT: Record<string, number> = {
  opened: 0, // slot 1, aqua — the disposition that closes the loop
  retried: 1, // slot 2, orange — still in motion, not yet opened or abandoned
  null: 2, // slot 3, blue — never written on purpose; a data gap, not an outcome
  no_change: 3, // slot 4, green-adjacent identity — examined, and nothing needed to move
  abandoned: 4, // slot 5, magenta — held far from "opened" on purpose, see above
  halted: 5, // slot 6 — verified with nowhere to deliver (a forge-less assembly)
  external_cause: 7, // slot 8 — ended by a condition outside the repository
}

// A disposition outside the vocabulary above — none exist today — lands here instead of
// displacing one of the four known slots. Fixed regardless of how many such values ever
// show up, so a fifth value cannot renumber the ones already on screen.
const OTHER_SLOT = 6 // slot 7, violet

function buildDispositionOption(tally: Tally, tokens: ChartTokens) {
  // Alphabetical, matching the `TallyTable` sort below it — a reader comparing the chart to
  // the table finds the same order in both. This governs layout only; colour comes from
  // `DISPOSITION_SLOT` and does not depend on this order or on what else is present.
  const entries = Object.entries(tally).sort(([a], [b]) => a.localeCompare(b))
  const total = entries.reduce((sum, [, count]) => sum + count, 0)

  const series = entries.map(([name, count], index) => {
    const isFirst = index === 0
    const isLast = index === entries.length - 1
    const color = tokens.series[DISPOSITION_SLOT[name] ?? OTHER_SLOT]
    const share = total === 0 ? 0 : count / total

    return {
      name,
      type: "bar",
      stack: "disposition",
      data: [count],
      barWidth: 24,
      itemStyle: {
        color,
        // The 2px surface-colour gap `marks-and-anatomy.md` specifies between
        // touching stacked segments, drawn as a border rather than a literal gap
        // because a stacked bar's segments must still sum to the full width.
        borderColor: tokens.surface,
        borderWidth: 2,
        borderRadius: [isFirst ? 4 : 0, isLast ? 4 : 0, isLast ? 4 : 0, isFirst ? 4 : 0],
      },
      label: {
        show: share >= INLINE_LABEL_SHARE_FLOOR,
        position: "inside" as const,
        color: labelInkFor(color, tokens.ink, tokens.labelOnLight),
        fontSize: 12,
        formatter: () => `${name}: ${count.toLocaleString()}`,
      },
      emphasis: { focus: "series" as const },
    }
  })

  return {
    grid: { left: 8, right: 16, top: 12, bottom: 58, containLabel: true },
    legend: {
      bottom: 4,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: tokens.inkSecondary, fontSize: 12 },
    },
    tooltip: {
      trigger: "item",
      backgroundColor: tokens.surface,
      borderColor: tokens.grid,
      borderWidth: 1,
      textStyle: { color: tokens.ink },
      // Values lead, labels follow — the tooltip's hierarchy is the legend's
      // inverted, because here the reader already has the series and wants the
      // number. `seriesName` is interpolated into an HTML string, which echarts'
      // own DOM tooltip renders via innerHTML, so it is escaped even though every
      // value this screen has ever produced is one of three literals.
      formatter: (params: { seriesName: string; value: number }) =>
        `<strong>${params.value.toLocaleString()}</strong> attempt${params.value === 1 ? "" : "s"} &middot; ${escapeHtml(params.seriesName)}`,
    },
    xAxis: {
      type: "value" as const,
      axisLine: { lineStyle: { color: tokens.axis } },
      splitLine: { lineStyle: { color: tokens.grid } },
      axisLabel: { color: tokens.inkMuted, fontSize: 12 },
    },
    yAxis: {
      type: "category" as const,
      data: ["Attempts"],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { show: false },
    },
    series,
  }
}

export function PrecedentChart({ data }: { data: PrecedentSummary }) {
  const buildOption = useCallback(
    (tokens: ChartTokens) => buildDispositionOption(data.by_terminal_status, tokens),
    [data.by_terminal_status],
  )

  const summary = Object.entries(data.by_terminal_status)
    .map(([name, count]) => `${count} ${name}`)
    .join(", ")

  return (
    <figure className="flex flex-col gap-field">
      <span className="furniture text-meta text-ink-muted">By disposition</span>
      <EChart
        buildOption={buildOption}
        ariaLabel={`Attempts by disposition: ${summary}`}
        style={{ height: 160 }}
      />
      <figcaption className="max-w-prose text-body text-muted-foreground">
        This table holds nothing for a run abandoned before any attempt (at{" "}
        <code className="font-mono">locate</code> or{" "}
        <code className="font-mono">prepare</code>), for a run where no tier applied, or for
        a run whose state was missing its finding, site, or change — those runs are real,
        and the runs table above still names them through an abandon reason, but they leave
        no attempt for this table to count. A <code className="font-mono">null</code> row
        below is an attempt whose column was never written, not a count of zero.
      </figcaption>
    </figure>
  )
}
