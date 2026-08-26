/**
 * Which form a daily series may honestly be drawn in — derived from the payload, never chosen by
 * the screen, and the fetch for the one series that had no data module of its own.
 *
 * `web/CLAUDE.md`: *a chart must be able to draw its own data — check the real payload before
 * choosing a form.* That was learned when provenance shipped as a donut over a set where four of
 * five members were measured zeros and rendered as a closed ring that read as broken. This is the
 * same failure one shape along, and it is live: measured against this deployment on 2026-08-26,
 * `/api/findings/over-time`, `/api/integration-changes/over-time` and `/api/precedent/activity`
 * each return **exactly one day**, and the changes payload stacks thirty-four integrations onto
 * it. A stacked column over a single category is not a series — it is one total wearing a time
 * axis, under a legend taller than the bar it explains.
 *
 * So the form is a derivation with a test rather than a paragraph asking the next agent to look:
 * no day is an absence, one day is a composition, two or more is a series. It keeps holding when
 * the corpus grows a second day and nobody remembers this file exists.
 */

import type { DayEntry } from "@/components/charts/day-stack-option"
import {
  ApiStatusError,
  MalformedResponseError,
  UnreachableApiError,
} from "@/api/errors"
import type { RankedRow } from "@/components/ranked-bars"

/**
 * `absent` — no day carries a row, so there is nothing to draw and the caller says which nothing.
 * `composition` — one day. Drawn as a ranking over the members, because a time axis with one tick
 * invites a slope nobody measured. `series` — two or more days, which is a series.
 */
export type DailySeriesForm = "absent" | "composition" | "series"

export function dailySeriesForm(days: readonly DayEntry[]): DailySeriesForm {
  if (days.length === 0) return "absent"
  return days.length === 1 ? "composition" : "series"
}

/**
 * Each member's total across every day, largest first, ties broken on the name.
 *
 * **Members measured at nought keep their row**, which is the opposite of what the stacked form
 * does and right for the opposite reason. A band of zeroes across a legend names a measurement
 * nobody took; a *bar* of zero is a row, a label and a printed 0 — `web/CLAUDE.md`'s reason for
 * preferring bars wherever a set has meaningful zeros. The caller passes the vocabulary it can
 * stand behind, so what arrives here is already only what was looked at.
 */
export function memberTotals(
  days: readonly DayEntry[],
  members: readonly string[],
): RankedRow[] {
  return members
    .map((key) => ({
      key,
      value: days.reduce((sum, day) => sum + (day.counts[key] ?? 0), 0),
    }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))
}

/** Two orders of magnitude. The point at which the smallest bar is a pixel beside the largest. */
export const ORDERS_OF_MAGNITUDE = 100

/**
 * Whether a set spans orders of magnitude, which is the condition `web/CLAUDE.md` puts on a log
 * scale — and the condition is checked rather than assumed, in both directions.
 *
 * A log axis a reader takes for linear is worse than no chart, so this returns `false` for every
 * set a linear scale draws fairly. Measured today the changes ranking runs 18 down to 1, which is
 * one order and stays linear; the severities run 35 to 38. `RankedBars` announces the scale on the
 * chart whenever this says yes.
 */
export function spansOrdersOfMagnitude(values: readonly number[]): boolean {
  const positive = values.filter((value) => value > 0)
  if (positive.length < 2) return false
  return Math.max(...positive) >= Math.min(...positive) * ORDERS_OF_MAGNITUDE
}

/**
 * What the watched integrations published, by the day Sync detected it.
 *
 * The type and the fetch, with no component attached: `trends-kpis.tsx` and the Metrics panes both
 * read this key, and while it lived inside a card file the strip imported a chart in order to
 * reach a `fetch`. The card is gone with the Metrics rebuild; the read is what the screen needed.
 */
export interface ChangesOverTime {
  vendor_id: string | null
  vendors: string[]
  days: DayEntry[]
  total: number
}

export async function fetchChangesOverTime(signal?: AbortSignal): Promise<ChangesOverTime> {
  const path = "/api/integration-changes/over-time"
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    if (signal?.aborted) throw cause
    throw new UnreachableApiError(path, { cause })
  }
  if (!response.ok) throw new ApiStatusError(response.status, path)
  try {
    return (await response.json()) as ChangesOverTime
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}
