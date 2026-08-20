/**
 * An integration's mark: a monogram in a palette slot, drawn here and fetched from nowhere.
 *
 * **M15 Task 5, owner ruling 2026-08-19: the neutral generated mark.** A vendor's logo is their
 * trademark, and `.claude/rules/interface-originality.md` excludes identity elements from every
 * reference Sync studies. That reasoning extends to the vendors Sync *watches*, so the console
 * draws its own mark rather than reproducing theirs.
 *
 * ## What this replaces, and why its removal is the point
 *
 * This module used to build a `logo.clearbit.com` URL and render an `<img>` from it, falling back
 * to letters when the request failed. Three things were wrong with that, and only the first is
 * about trademarks:
 *
 * - **It put third-party marks in the product**, each under its own licence, none reviewed.
 * - **It called a third party from the operator's browser on every render of every vendor.** That
 *   endpoint learns which integrations a customer watches, which is a fact about their codebase —
 *   and Sync's position is that it holds as little of that as it can.
 * - **It made the console's appearance depend on a network** it does not control. A mark that
 *   resolves at a desk and not in a locked-down deployment is a screen that looks broken there.
 *
 * Deleted rather than flagged off. `CLAUDE.md`: *delete rather than deprecate* — a disabled fetch
 * is one edit away from being a live one, and `fetchMarks` already defaulted to `true`.
 *
 * ## The colour is identity, not judgement
 *
 * `console-surface.md` lets three channels carry a claim, and none of them is this — a vendor's
 * slot says *which vendor*, exactly as a series colour on a chart says which series. It is drawn
 * from `SERIES_SLOTS`, the categorical palette `DESIGN.md` already argues and whose contrast is
 * already proven there, so this introduces **no new token**. A ninth vendor takes `OTHER_INK`,
 * the contract's own answer for a member past the eighth.
 *
 * The letters carry the identity on their own, so the colour is never the only channel — the same
 * rule a status colour follows.
 */

import { OTHER_INK, SERIES_SLOTS } from "@/lib/palette"
import { vendorName } from "@/features/vendors/vendor-name"

/**
 * The letters shown for a vendor: one per part of the id, at most two.
 *
 * `google-maps` gives `GM` and `stripe` gives `S`. Two is the cap because a third letter stops
 * being a monogram and starts being a truncated word.
 */
export function monogramFor(vendorId: string): string {
  const initials = vendorId
    .split(/[^a-zA-Z0-9]+/)
    .filter((part) => part.length > 0)
    .map((part) => part[0].toUpperCase())

  return initials.length === 0 ? "?" : initials.slice(0, 2).join("")
}

/**
 * Which palette slot a vendor takes.
 *
 * Hashed from the id rather than assigned by position, so a vendor keeps its colour wherever it
 * appears and whatever else is on screen beside it — a mark that changed colour between two
 * screens would be read as two different integrations.
 *
 * Deliberately not a generated hue: the slots are the contract's, and their contrast against the
 * surface is proven in `DESIGN.md` rather than hoped for here.
 */
export function slotFor(vendorId: string): string {
  const key = vendorId.trim().toLowerCase()
  if (key === "") return OTHER_INK

  let hash = 0
  for (const character of key) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0
  }
  return SERIES_SLOTS[hash % SERIES_SLOTS.length]
}

export interface VendorMarkProps {
  /** The vendor id: the source of both the monogram and the slot. */
  readonly vendorId: string
}

export function VendorMark({ vendorId }: VendorMarkProps) {
  return (
    <span
      className="flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-[4px] border border-line"
      style={{ backgroundColor: slotFor(vendorId) }}
      data-testid="vendor-mark-monogram"
      // The name is beside the mark everywhere it is used, so announcing the letters again would
      // read the vendor twice to a screen reader.
      aria-hidden="true"
      title={vendorName(vendorId)}
    >
      <span className="font-mono text-meta leading-none text-[#101211]">
        {monogramFor(vendorId)}
      </span>
    </span>
  )
}
