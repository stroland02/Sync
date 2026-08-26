/**
 * One daily series as a pane of the locked Metrics grid: banded header, the pane's own measured
 * figure on the right of the band, the chart filling the body, the qualification pinned under it.
 *
 * The band's right-hand figure is the Stitch reference's own treatment
 * (`advanced_telemetry_trace_explorer`, whose trace pane carries `Latency: 420ms · CPU: 84%`
 * opposite its label). Here it carries what the chart below sums to and how many days it was
 * recorded over, which is what makes the drawing checkable instead of decorative.
 *
 * **The form comes from `daily-series.ts`, not from this file.** Three panes render through here
 * and each would otherwise have picked a shape from what its subject sounds like rather than from
 * what its payload holds — which is exactly how a one-day payload gets a time axis and a
 * thirty-four-member legend.
 *
 * **`claim` is pinned and `note` scrolls, and the split is measured rather than stylistic.** The
 * first draft pinned the whole qualification: at 1366x768 that rendered a 205px footer inside a
 * 175px pane, so the paragraph overflowed the pane it was qualifying and the chart was left 32px.
 * `console-surface.md` already draws the line — the claim is always visible in the fewest honest
 * words, the argument behind it is not — and this is that line as two props.
 */

import { useCallback, type ComponentType, type ReactNode, type SVGProps } from "react"

import { buildDayStackOption, type DayEntry } from "@/components/charts/day-stack-option"
import type { ChartTokens } from "@/components/charts/echart"
import { EChart } from "@/components/charts/echart"
import { PanelPane } from "@/components/pane"
import { RankedBars } from "@/components/ranked-bars"
import { Absent } from "@/components/status"
import {
  dailySeriesForm,
  memberTotals,
  spansOrdersOfMagnitude,
} from "@/features/dashboards/daily-series"

/** `RankedBars` draws its own bordered surface; inside a pane that is a card within a card. */
const FLATTENED = "h-auto rounded-none border-0 bg-transparent p-0"

export function DailySeriesPane({
  label,
  icon,
  hint,
  days,
  members,
  stackId,
  outcomeRamp = false,
  unit,
  memberNoun,
  total,
  colourByKey = false,
  absence,
  claim,
  note,
  className,
}: {
  label: string
  icon?: ComponentType<SVGProps<SVGSVGElement>>
  hint?: ReactNode
  days: readonly DayEntry[]
  /** The vocabulary this pane can stand behind. A member at nought keeps its bar and its count. */
  members: readonly string[]
  stackId: string
  /**
   * Read every band's colour from the reserved outcome ramp rather than from a categorical slot.
   *
   * For the one set whose members ARE states. Slot order once painted `abandoned` in the good ink
   * — a failure drawn as a success — which is why `DESIGN.md` reserves the ramp and why this is a
   * flag rather than a colour map a caller could get wrong.
   */
  outcomeRamp?: boolean
  /** What one unit is — "changes", "findings", "attempts". Never a rate. */
  unit: string
  /** What one member is — "integration", "severity", "outcome". */
  memberNoun: string
  /** What the drawing sums to, from the payload rather than re-added here. */
  total: number
  /** `true` only where the members are integrations: a vendor's hue is its identity everywhere. */
  colourByKey?: boolean
  /** Which nothing an empty payload is. Never "no activity". */
  absence: ReactNode
  /**
   * The scope and the absence rule in the fewest honest words. Pinned outside the scroll, so a
   * reader who never scrolls this pane still knows what it covers.
   *
   * **One line.** Measured at 1366x768 on 2026-08-26: a paragraph here rendered a 205px footer
   * inside a 175px pane — the qualification overflowed the pane it qualified, and the chart got
   * 32px. `console-surface.md` already draws the line this restores: the claim is always visible,
   * the argument is not.
   */
  claim: ReactNode
  /** The argument the claim compresses. Under the chart, inside the scroll. */
  note?: ReactNode
  className?: string
}) {
  const form = dailySeriesForm(days)
  const rows = memberTotals(days, members)

  const build = useCallback(
    (tokens: ChartTokens) =>
      buildDayStackOption(
        { days, members, stackId, memberColors: outcomeRamp ? tokens.outcome : undefined },
        tokens,
      ),
    [days, members, stackId, outcomeRamp],
  )

  return (
    <PanelPane
      className={className}
      label={label}
      icon={icon}
      hint={hint}
      actions={
        <span className="text-meta text-ink-muted">
          <span className="font-mono tabular-nums text-ink">{total.toLocaleString()}</span> {unit}
          {form !== "absent" && (
            <>
              {" · "}
              <span className="font-mono tabular-nums text-ink">{days.length}</span>{" "}
              {days.length === 1 ? "day" : "days"} recorded
            </>
          )}
        </span>
      }
      bodyClassName="p-section"
      footer={claim}
      footerClassName="h-auto min-h-[var(--row-lg)] items-start py-field leading-relaxed"
    >
      <div className="flex min-w-0 flex-col gap-section">
      {form === "absent" ? (
        <p className="max-w-prose text-body text-ink-muted">
          <Absent>nothing recorded</Absent> — {absence}
        </p>
      ) : form === "composition" ? (
        <RankedBars
          className={FLATTENED}
          label={`By ${memberNoun}`}
          caption={oneDayCaption(days[0].day, unit, memberNoun)}
          rows={rows}
          unit={unit}
          colourByKey={colourByKey}
          scale={spansOrdersOfMagnitude(rows.map((row) => row.value)) ? "log" : "linear"}
        />
      ) : (
        <div className="h-64 w-full shrink-0">
          <EChart
            buildOption={build}
            ariaLabel={`${label}: ${unit} per day, stacked by ${memberNoun}`}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
      {note !== undefined && (
        <p className="max-w-prose text-meta text-ink-muted leading-relaxed">{note}</p>
      )}
      </div>
    </PanelPane>
  )
}

/**
 * The sentence that stops a one-day composition being read as a series.
 *
 * Exported so `daily-series.test.ts` can assert the claim rather than a class name: the day itself
 * has to be on screen, because "one day" without saying *which* day is a scope qualified nowhere.
 */
export function oneDayCaption(day: string, unit: string, memberNoun: string): string {
  return (
    `Every ${unit.replace(/s$/, "")} recorded so far landed on one day, ${day}, so this is a ` +
    `composition by ${memberNoun} rather than a series. A time axis with one tick would invite a ` +
    `trend nothing here measured. Each bar's width is its share of the largest ${memberNoun}, ` +
    `not of the total.`
  )
}
