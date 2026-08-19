/**
 * Derivations for the live-signals page, kept pure so the rules the screen renders by are
 * testable without a render.
 *
 * The one rule that matters here: **a count is not a rate.** `rateSentence` is the only place a
 * percentage is spelled, and it spells the denominator into the same sentence — a screen that
 * wants the figure gets the whole claim or nothing.
 */

import type { TrafficBucket } from "@/api/types"
import type { DayEntry } from "@/components/charts/day-stack-option"

/** The stacked bands, in fixed order — errors first so the failure sits on the baseline. */
export const TRAFFIC_MEMBERS = ["errored", "succeeded"] as const

/**
 * "80 of 240 requests (33.3%)" — the percentage never travels without its denominator, and a
 * denominator of zero is a sentence about absence rather than a division.
 */
export function rateSentence(errors: number, requests: number): string {
  if (requests === 0) return "no statused requests"
  const percent = ((errors / requests) * 100).toFixed(1)
  return `${errors.toLocaleString()} of ${requests.toLocaleString()} requests (${percent}%)`
}

/**
 * The hourly series as the day-stack builder's input. `errored` and `succeeded` partition
 * `requests`, so the stack's height is the requests count and nothing is drawn twice. The
 * bucket label keeps the date: a series can span days, and an hour label alone would render
 * two different mornings as one.
 */
export function seriesToDays(series: readonly TrafficBucket[]): DayEntry[] {
  return series.map((bucket) => ({
    day: bucketLabel(bucket.bucket),
    counts: { errored: bucket.errors, succeeded: bucket.requests - bucket.errors },
  }))
}

/** "08-19 14:00" from an ISO instant — date kept, minutes shown as the bucket's floor. */
export function bucketLabel(iso: string): string {
  const match = /^\d{4}-(\d{2})-(\d{2})T(\d{2})/.exec(iso)
  if (match === null) return iso
  return `${match[1]}-${match[2]} ${match[3]}:00`
}
