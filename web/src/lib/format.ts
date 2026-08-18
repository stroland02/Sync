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
export function describeRange(
  offset: number,
  shown: number,
  total: number,
  unfilteredTotal?: number,
): string {
  // Decision 60: never a bare row count while a filter is active. The owner did not take filter
  // chips, so this string is the only thing standing between a narrowed table and being read as
  // the whole set. The decision's example is single-page ("showing 4 of 31"); across pages that
  // would be false, so the range stays and the filtered clause travels with it.
  const hidden =
    unfilteredTotal !== undefined && unfilteredTotal > total ? unfilteredTotal - total : 0

  if (total === 0) {
    return hidden > 0 ? `none of ${unfilteredTotal}, all ${hidden} filtered out` : "none"
  }
  const range = `${offset + 1}–${offset + shown} of ${total}`
  // A filter that excluded nothing needs no warning, and "0 filtered out" is noise that makes the
  // real case easier to miss.
  return hidden > 0 ? `${range} matched, ${hidden} filtered out` : range
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

/** Human-friendly short badge for a finding ID (e.g. "f-2f725b"), avoiding jumbled hex strings. */
export function formatFindingBadge(findingId: string | null | undefined): string {
  if (!findingId) return "f-unknown"
  if (findingId.startsWith("f-")) return findingId
  return `f-${findingId.slice(0, 7)}`
}

/** Human-friendly short badge for a thread ID (e.g. "thread-8f21c0"). */
export function formatThreadBadge(threadId: string | null | undefined): string {
  if (!threadId) return "thread-unknown"
  if (threadId.startsWith("thread-")) return threadId
  return `thread-${threadId.slice(0, 6)}`
}

