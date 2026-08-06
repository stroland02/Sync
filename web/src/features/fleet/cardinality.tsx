/**
 * The rule the lead screen turns on: below a fixed threshold, a panel lists every row it
 * holds and says so; at or above it, a panel states the count, the ordering it applied, and
 * the size of the slice it renders instead of the whole set. A panel that switches between
 * the two without saying which one it is in is the defect class this milestone has closed
 * six times, so every panel on this screen that can grow past a handful of rows speaks
 * through this module rather than composing its own sentence.
 */

/**
 * Ten rows is the boundary: fewer than that, a reader profits more from seeing every row
 * than from a count, and it is close to what today's fixture (`scripts/seed_console.py`)
 * actually holds, so the below-threshold sentence is what a fresh install shows. One
 * constant, so a revision touches one place rather than every panel that reads it.
 */
export const CARDINALITY_THRESHOLD = 10

/** Whether `total` rows are few enough to list every one rather than to count them. */
export function isCompleteListing(total: number): boolean {
  return total <= CARDINALITY_THRESHOLD
}

/**
 * The sentence a panel states about its own cardinality, computed once so the wording cannot
 * drift panel to panel. `shown` is how many rows the panel actually renders below the
 * sentence once the set is too large to list in full — it defaults to the threshold, but a
 * panel whose "page" is a different size (a paginated route, for instance) passes its real
 * count so the sentence never claims a size the table beneath it does not have.
 */
export function describeCardinality(
  total: number,
  singular: string,
  plural: string,
  ordering: string,
  shown: number = Math.min(total, CARDINALITY_THRESHOLD),
): string {
  const noun = total === 1 ? singular : plural
  if (isCompleteListing(total)) {
    return total === 0 ? `No ${plural}.` : `This is all ${total.toLocaleString()} ${noun}.`
  }
  return `Showing ${shown.toLocaleString()} of ${total.toLocaleString()} ${plural}, ordered by ${ordering}.`
}

/**
 * The top slice of a set that was already fetched whole and ordered. Never apply this to a
 * set a route paginates — Decision 4 makes client-side narrowing honest only over a set the
 * client already holds in full.
 */
export function sliceForDisplay<T>(rows: readonly T[]): T[] {
  return isCompleteListing(rows.length) ? [...rows] : rows.slice(0, CARDINALITY_THRESHOLD)
}

/** The cardinality sentence, rendered at the same weight as the panel's other prose. */
export function CardinalityStatement({ text }: { text: string }) {
  return <p className="max-w-prose text-body text-muted-foreground">{text}</p>
}

/**
 * The figure a stat tile renders for a count that may have stopped early: "1,000+" once the
 * transport's own bound was reached, the plain number otherwise. A fifth member of the
 * console's absence vocabulary — "at least N" is not "N", and rendering the bare total once
 * the system stopped counting would imply a completeness `total` does not have. Mirrors
 * `queryCount.tsx`'s `${max}+` convention (section 24 of the console architecture plan), but
 * this glyph is never the only channel: `boundedTotalCaveat` below states in words what it
 * means, the same way a status colour never ships without an icon and a word.
 */
export function describeBoundedTotal(total: number, boundReached: boolean): string {
  return boundReached ? `${total.toLocaleString()}+` : total.toLocaleString()
}

/**
 * The sentence that says what the bound figure means: the system stopped counting at a stated
 * ceiling, so the number is a floor on the true population, not the population itself. Also
 * names the consequence for any unbounded breakdown shown alongside it — the vendor and
 * severity distributions are each their own `GROUP BY` over every open finding, so past the
 * bound their sum legitimately exceeds this total, and a reader seeing that without this
 * sentence would read it as a bug rather than as two honestly different questions.
 */
export function boundedTotalCaveat(bound: number): string {
  return (
    `This total stopped counting at ${bound.toLocaleString()}: the graph holds at least that ` +
    "many open findings, and this figure does not say how many more. The breakdowns below are " +
    "each their own count across every open finding, not a slice of this total, so they can " +
    "sum to more than the number shown above."
  )
}
