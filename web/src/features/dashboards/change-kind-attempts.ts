/**
 * Which kinds of change the pipeline has attempted, and how many of those attempts it gave up on.
 *
 * The abandonment payload is grouped by `(change_kind, tier)` and two panes already read the tier
 * half of it. Nothing read the change-kind half, and it is the half that answers the question
 * `abandon-reasons-option.ts` names as the point of the whole aggregate: *which change kinds are
 * not mechanically safe to attempt.* A reason code says why one run stopped; this says which
 * subject matter keeps stopping them.
 *
 * **Two counts per row, never a rate.** Attempts and abandoned attempts sit beside each other and
 * nothing divides them. An abandonment rate over three attempts is a percentage with a denominator
 * of three, which is the shape `web/CLAUDE.md` refuses — and the counts are printed on the bars, so
 * a reader who wants the ratio has both numbers.
 *
 * **The grain is one attempt.** `migration_outcome` stores one row per repair attempt, so a finding
 * retried three times contributes three. Every field name here says `attempts` for that reason.
 */

import type { AbandonmentResponse } from "@/api/types"
import type { RankedRow } from "@/components/ranked-bars"

export interface ChangeKindAttempts {
  /** One row per change kind the corpus holds, most attempts first, ties broken on the name. */
  readonly rows: readonly RankedRow[]
  /** Abandoned attempts by change kind, for the detail printed beside each bar. */
  readonly abandoned: Readonly<Record<string, number>>
  readonly totalAttempts: number
  readonly totalAbandoned: number
  /** Change kinds the corpus has attempted. Never the size of the vocabulary — it has no closed
      list here, so this counts what was seen rather than claiming what exists. */
  readonly kindCount: number
}

export function changeKindAttempts(payload: AbandonmentResponse): ChangeKindAttempts {
  const attempts = new Map<string, number>()
  const abandoned = new Map<string, number>()

  for (const group of payload.groups) {
    attempts.set(group.change_kind, (attempts.get(group.change_kind) ?? 0) + group.attempt_count)
    abandoned.set(
      group.change_kind,
      (abandoned.get(group.change_kind) ?? 0) + group.abandoned_attempt_count,
    )
  }

  const rows = [...attempts.entries()]
    .map(([key, value]) => ({ key, value }))
    .sort((a, b) => b.value - a.value || a.key.localeCompare(b.key))

  return {
    rows,
    abandoned: Object.fromEntries(abandoned),
    totalAttempts: rows.reduce((sum, row) => sum + row.value, 0),
    totalAbandoned: [...abandoned.values()].reduce((sum, n) => sum + n, 0),
    kindCount: rows.length,
  }
}
