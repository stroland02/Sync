/**
 * How long ago something happened, stated relatively and kept true.
 *
 * Decision 38 asks for relative time with the exact timestamp on hover, and names the defect that
 * comes with it: a relative string is computed against `now`, and a console tab sits open for
 * hours. A component that formats once and never recomputes says "14 minutes ago" at nine in the
 * morning about something from four — the console stating a falsehood with complete confidence,
 * reached through a formatting helper rather than through a claim anybody wrote.
 *
 * So this re-renders on an interval. `useNow` is mounted only while this component is, so the
 * timer exists exactly as long as something is displaying an age.
 *
 * **This replaces `formatElapsed`, which was the static half of the same idea.** Two spellings of
 * "how long ago" is the duplication that disagrees with itself, and here the disagreement was the
 * defect: one re-rendered and the other did not.
 *
 * **The absolute carries its UTC offset.** A bare local string cannot be checked against a log
 * line by a reader in another zone, which is most of what an exact timestamp is for.
 */

import { Absent } from "@/components/status"
import { formatAge, secondsSince, useNow } from "@/lib/elapsed"

/** A minute. Finer than the coarsest unit this renders, so no displayed value is ever stale. */
const TICK_MS = 60_000

function absoluteWithOffset(parsed: Date): string {
  return parsed.toLocaleString(undefined, { timeZoneName: "shortOffset" })
}

export interface RelativeTimeProps {
  /** ISO 8601. `null` renders the absence marker rather than a guess at a time. */
  readonly iso: string | null | undefined
}

export function RelativeTime({ iso }: RelativeTimeProps) {
  const now = useNow(TICK_MS)

  if (!iso) return <Absent />
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return <Absent />

  return (
    <time dateTime={iso} title={absoluteWithOffset(parsed)}>
      {formatAge(secondsSince(parsed.getTime(), now))}
    </time>
  )
}
