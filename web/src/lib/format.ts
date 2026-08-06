/**
 * Formatting helpers whose job is to never let a caller render a blank where a value is
 * absent. They format; they do not render. A helper that returned the absence glyph as a
 * bare string once let two call sites paint it two different colours — this module knows
 * only `string | null` now, and `<Formatted>` in `@/components/status` is the one place a
 * `null` becomes ink. There is nothing left for a call site to forget.
 */

import type { BindingSource } from "@/api/types"

/** What a missing value looks like. One glyph everywhere, so absence is recognisable. */
export const ABSENT = "—"

/** A string, or null for absence. Render through `<Formatted>`, never as bare text. */
export function orAbsent(value: string | null | undefined): string | null {
  return value === null || value === undefined || value === "" ? null : value
}

/** An ISO 8601 timestamp in the reader's locale, or null for absence. */
export function formatTimestamp(iso: string | null | undefined): string | null {
  if (!iso) return null
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleString()
}

/**
 * How long ago an ISO 8601 timestamp was, in the coarsest unit that stays readable.
 *
 * This is staleness, not liveness — it says how old the evidence is, not whether the thing
 * it describes is still going. The fleet screen's legend carries why that distinction
 * matters for a checkpoint specifically; this function only formats the duration.
 */
export function formatElapsed(iso: string | null | undefined): string | null {
  if (!iso) return null
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return null

  const seconds = Math.max(0, Math.round((Date.now() - parsed.getTime()) / 1000))
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  return `${days}d ago`
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
    default:
      return "a rung this console does not recognise — the provenance vocabulary has changed since this view was written"
  }
}

/** "1-50 of 123", or "none" when there is nothing to place. */
export function describeRange(offset: number, shown: number, total: number): string {
  if (total === 0) return "none"
  return `${offset + 1}–${offset + shown} of ${total}`
}

/**
 * The part of a call site's path that is not the directory every row on the screen shares.
 *
 * On a real repository most of a path column's width is a prefix identical on every row, and the
 * binding surface's path column is the widest thing on that page. The payload reports the shared
 * directory (`call_sites_common_directory`, computed in SQL over the filtered set), the screen
 * states it once, and each row renders what follows it — so nothing is hidden and no fact leaves the
 * page: the whole path is the prefix plus this.
 *
 * Two fallbacks, both returning the whole path, and neither is reachable through the payload — the
 * prefix is computed from the same set the rows came from. They are here because of what the
 * alternative looks like when wrong: slicing blind would render `ing/charges/create.ts`, which a
 * reader takes for a real file, and a path equal to its prefix would render an empty cell that names
 * no file at all. Wrong-but-legible beats wrong-and-plausible.
 */
export function pathAfter(commonDirectory: string, path: string): string {
  if (commonDirectory === "" || !path.startsWith(commonDirectory)) return path
  const rest = path.slice(commonDirectory.length)
  return rest === "" ? path : rest
}
