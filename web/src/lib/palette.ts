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
import { interpolateLab } from "d3-interpolate"

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
 * The monogram's ink on a series-slot background. One dark value rather than per-slot inks,
 * because every slot was chosen light enough to carry it -- `palette.test.ts` proves the pairing
 * against all eight, which is why the value lives here with the other computed-with colours.
 */
export const MONOGRAM_INK = "#101211"

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

/**
 * Sequential and diverging colour, for the marks a categorical scale cannot serve.
 *
 * **Added 2026-08-19 with the Sankey, chord and radial visuals, and deliberately narrow.** Those
 * three carry a *magnitude* per mark — a flow's volume, a ribbon's weight, an arc's duration —
 * and an ordinal scale answers identity rather than quantity. What is added is a ramp; what is
 * not added is a meaning.
 *
 * **The ramp is built from the contract's own slots, not from a stock d3 scheme.** `interpolateLab`
 * runs in a perceptually uniform space, so equal steps along the ramp look equally different —
 * which is the property that makes a ramp readable at all, and the reason `interpolateRgb` is
 * wrong here.
 *
 * **What a ramp still may not mean.** No bad-to-good. No health. No confidence. A ramp encodes
 * *how much*, and every mark that takes one also carries its number, because a reader cannot
 * recover a quantity from a shade and must never be asked to.
 *
 * That rules out a red-to-green diverging scale entirely — it is the traffic light this console
 * refuses, drawn as a gradient. The diverging ramp here runs between two *identity* slots and is
 * for a signed quantity (more of A versus more of B), never for worse versus better.
 */

/**
 * The smallest step toward `slot` that still clears the 3:1 mark floor on `surface`.
 *
 * Derived rather than chosen. A fixed fraction was tried first and shipped at 1.62:1 against the
 * console's own surface -- a ramp floor a reader cannot see, which is worse than a flat colour
 * because it looks measured. `palette.test.ts` caught it; this is the fix, and it is a search
 * because the answer differs per slot: a dark slot needs a longer step than a bright one.
 */
function legibleFloor(slot: string, surface: string): string {
  const ramp = interpolateLab(surface, slot)
  for (let step = 0; step <= 100; step += 1) {
    const candidate = ramp(step / 100)
    if (contrastRatio(candidate, surface) >= 3) return candidate
  }
  // No step clears the floor, so the slot itself does not -- return it and let the caller's
  // `rampClearsFloor` check fail loudly rather than shipping an invisible ramp quietly.
  return slot
}

/** A ramp from a legible floor to a series slot: low volume recedes, high volume asserts. */
export function volumeScale(
  slot: string = SERIES_SLOTS[0],
  surface: string = PLOTTING_SURFACE,
): (t: number) => string {
  const ramp = interpolateLab(legibleFloor(slot, surface), slot)
  return (t: number) => ramp(Math.min(Math.max(t, 0), 1))
}

/**
 * A ramp between two identity slots, for a signed quantity.
 *
 * Never worse-to-better. The midpoint is the surface-adjacent neutral, so "balanced" reads as
 * absent emphasis rather than as a third category.
 */
export function divergingScale(
  low: string = SERIES_SLOTS[2],
  high: string = SERIES_SLOTS[1],
  surface: string = PLOTTING_SURFACE,
): (t: number) => string {
  const neutral = legibleFloor(OTHER_INK, surface)
  const below = interpolateLab(low, neutral)
  const above = interpolateLab(neutral, high)
  return (t: number) => {
    const clamped = Math.min(Math.max(t, 0), 1)
    return clamped < 0.5 ? below(clamped * 2) : above((clamped - 0.5) * 2)
  }
}

/**
 * The proof that a ramp is legible end to end.
 *
 * A ramp can clear the mark floor at its top and vanish at its bottom, which is worse than a flat
 * colour because it looks measured. This checks the floor at both ends and at the midpoint, so a
 * ramp is verified where it is defined rather than assumed from the slot it was built out of.
 */
export function rampClearsFloor(
  ramp: (t: number) => string,
  surface: string = PLOTTING_SURFACE,
): boolean {
  return [0, 0.5, 1].every((t) => contrastRatio(ramp(t), surface) >= 3)
}
