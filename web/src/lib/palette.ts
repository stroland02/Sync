/**
 * Categorical colour, assigned by one scale and proved against the contract.
 *
 * **`DESIGN.md` remains the authority and none of its values move here.** The eight series
 * slots were enumerated, scored for colour-vision separation across all eight orderings, and
 * measured against the plotting surface; swapping them for a stock d3 scheme would trade
 * validated work for a library default. What d3 supplies is the two things this console was
 * doing by hand:
 *
 * - **Assignment.** `d3-scale`'s ordinal scale maps a domain onto the slots with a stable,
 *   documented rule, so "which colour is stripe" has one answer everywhere instead of an index
 *   computed separately in each chart. A domain that outgrows the palette folds into the
 *   contract's own answer — `other` — rather than cycling, because a ninth series wearing slot
 *   1's hue is two identities in one colour.
 * - **Proof.** `d3-color` computes relative luminance, so a contrast ratio is *derived from the
 *   tokens* rather than transcribed beside them. A hand-maintained table is a fact written
 *   twice, and this repository has paid for that class of drift before.
 *
 * **What colour is still not allowed to mean**, unchanged and restated because this file is
 * where someone would try: no ramp from bad to good, no health, no confidence, no status
 * without an icon and a word. A series colour carries *identity* — which vendor, which kind —
 * and identity is legible without hue because every mark that takes one also takes a label.
 */

import { scaleOrdinal } from "d3-scale"
import { color as d3color, rgb } from "d3-color"

/**
 * The eight series slots, in the contract's order.
 *
 * Literal hex rather than `var(--color-series-n)` because these are read by code that computes
 * with them — a CSS variable is a string to JavaScript, and a contrast ratio cannot be derived
 * from one. `tests/test_console_design_tokens.py` is what holds these equal to the tokens.
 */
export const SERIES_SLOTS = [
  "#199e70",
  "#d95926",
  "#3987e5",
  "#008300",
  "#d55181",
  "#c98500",
  "#9085e9",
  "#e66767",
] as const

/** What a member past the eighth takes. The contract's own answer, not a generated hue. */
export const OTHER_INK = "#8b8b8b"

/**
 * A stable colour per member of a closed vocabulary — vendors, change kinds, sources.
 *
 * The domain is sorted before assignment, so the same set of vendors takes the same colours on
 * every screen and across reloads: a legend that changed colour between two visits would make
 * a reader compare two pictures that do not mean the same thing.
 *
 * Past eight members every further member takes `OTHER_INK`. That is the contract's rule
 * applied rather than reinvented: a ninth series is folded, faceted, or turned into a table.
 */
export function seriesScale(domain: readonly string[]): (member: string) => string {
  const ordered = [...new Set(domain)].sort()
  const within = ordered.slice(0, SERIES_SLOTS.length)
  const scale = scaleOrdinal<string, string>().domain(within).range([...SERIES_SLOTS])
  return (member: string) => (within.includes(member) ? scale(member) : OTHER_INK)
}

/** Relative luminance per WCAG, computed from the colour rather than looked up beside it. */
export function relativeLuminance(input: string): number {
  const parsed = d3color(input)
  if (parsed === null) throw new Error(`not a colour this console can measure: ${input}`)
  const { r, g, b } = rgb(parsed)
  const channel = (value: number) => {
    const v = value / 255
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

/**
 * The contrast ratio between two colours, derived.
 *
 * `DESIGN.md` states a 5.05:1 floor for text and 3:1 for non-text marks, with the arithmetic
 * written beside every pairing. This is that arithmetic as a function, so a pairing can be
 * checked where it is used instead of trusted from a table.
 */
export function contrastRatio(foreground: string, background: string): number {
  const a = relativeLuminance(foreground)
  const b = relativeLuminance(background)
  const [lighter, darker] = a >= b ? [a, b] : [b, a]
  return (lighter + 0.05) / (darker + 0.05)
}

/** The plotting surface every series slot is measured against — the substrate's card. */
export const PLOTTING_SURFACE = "#181a19"

/** Whether a mark clears the non-text floor on the surface it is drawn on. */
export function clearsMarkFloor(mark: string, surface: string = PLOTTING_SURFACE): boolean {
  return contrastRatio(mark, surface) >= 3
}
