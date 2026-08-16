/**
 * A tally per detector, turned into one series per rung across every detector.
 *
 * The payload is shaped for a table — `by_rung` on each row, holding only the keys that
 * detector actually carries — and a stacked bar needs the transpose: a fixed set of series, each
 * with one value per category, gaps filled. That transpose is where the two honesty rules for
 * this chart live, and neither is arithmetic.
 *
 * **A rung nothing carries is still a series.** Dropping it would make "no open finding here
 * rests on observed traffic" indistinguishable from "this console does not have that rung", and
 * those are opposite facts about the same picture. It renders as a zero-width segment and as a
 * legend entry, and `absentRungs` is what lets the panel say so in words as well.
 *
 * **A rung this console has never heard of is counted, not skipped.** The graph's column is
 * text and the vocabulary belongs to the transport; a key silently dropped would draw every bar
 * shorter than the total printed beside it, which reads as a rendering bug rather than as a
 * console that has fallen behind. Every such key folds into one series — never a generated hue
 * per value, which is what `DESIGN.md`'s fixed slot order exists to prevent.
 */

import { BINDING_SOURCES } from "@/api/types"
import type { DetectorRow } from "@/api/types"

export interface RungSeries {
  /** A declared rung, or the folded label for everything this console does not recognise. */
  rung: string
  /** False only for the folded series. Drives the wording, never the colour. */
  known: boolean
  /**
   * The categorical slot this series takes, fixed by the rung's own position in the declared
   * vocabulary rather than by where it lands in a sorted result. A filter that removed a
   * detector must not repaint the survivors.
   */
  slot: number
  /** One count per detector, in the order `detectors` gives. */
  counts: number[]
  total: number
}

export interface RungComposition {
  detectors: string[]
  series: RungSeries[]
  /**
   * Each detector's own open-finding count, in `detectors` order.
   *
   * The chart draws composition rather than volume — every bar is full width — so this is the
   * number that has to be printed instead of encoded, and it is also the denominator every
   * share is taken against. Zero is possible and must not be divided by.
   */
  rowTotals: number[]
  /** Declared rungs no detector in this scope carries. Absence, named so it can be said. */
  absentRungs: string[]
  /** The keys the folded series is made of, sorted, so the panel can name them. */
  unrecognisedRungs: string[]
  total: number
}

/** The folded series' label. One entry however many unknown keys arrive. */
export const UNRECOGNISED_RUNG = "unrecognised"

export function rungComposition(rows: DetectorRow[]): RungComposition {
  const detectors = rows.map((row) => row.detector)

  const series: RungSeries[] = BINDING_SOURCES.map((rung, slot) => {
    const counts = rows.map((row) => row.by_rung[rung] ?? 0)
    return {
      rung,
      known: true,
      slot,
      counts,
      total: counts.reduce((sum, n) => sum + n, 0),
    }
  })

  const declared = new Set<string>(BINDING_SOURCES)
  const unrecognisedRungs = [
    ...new Set(rows.flatMap((row) => Object.keys(row.by_rung).filter((key) => !declared.has(key)))),
  ].sort()

  if (unrecognisedRungs.length > 0) {
    const counts = rows.map((row) =>
      unrecognisedRungs.reduce((sum, key) => sum + (row.by_rung[key] ?? 0), 0),
    )
    series.push({
      rung: UNRECOGNISED_RUNG,
      known: false,
      slot: BINDING_SOURCES.length,
      counts,
      total: counts.reduce((sum, n) => sum + n, 0),
    })
  }

  return {
    detectors,
    series,
    rowTotals: detectors.map((_, index) =>
      series.reduce((sum, entry) => sum + entry.counts[index], 0),
    ),
    absentRungs: series.filter((s) => s.known && s.total === 0).map((s) => s.rung),
    unrecognisedRungs,
    total: series.reduce((sum, s) => sum + s.total, 0),
  }
}
