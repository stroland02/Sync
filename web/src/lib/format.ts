/**
 * Rendering helpers whose job is to never render a blank where a value is absent.
 *
 * An empty cell reads as "nothing here" when the truth may be "not recorded", and a
 * console that blurs those two is worse than the payload it renders.
 */

import type { BindingSource } from "@/api/types"

/** What a missing value looks like. One glyph everywhere, so absence is recognisable. */
export const ABSENT = "—"

/** A string, or the absence marker. Never an empty cell. */
export function orAbsent(value: string | null | undefined): string {
  return value === null || value === undefined || value === "" ? ABSENT : value
}

/** An ISO 8601 timestamp in the reader's locale, or the absence marker. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return ABSENT
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleString()
}

/** What the rung claims, so an operator does not have to know the vocabulary. */
export function describeRung(rung: BindingSource): string {
  switch (rung) {
    case "static":
      return "read out of the source"
    case "resolved":
      return "read out of the source, then resolved"
    case "observed":
      return "correlated from watched traffic"
    case "unresolved":
      return "an observation that correlated to nothing"
    case "unattributed":
      return "recorded before the rung was tracked"
  }
}

/** "1-50 of 123", or "none" when there is nothing to place. */
export function describeRange(offset: number, shown: number, total: number): string {
  if (total === 0) return "none"
  return `${offset + 1}–${offset + shown} of ${total}`
}
