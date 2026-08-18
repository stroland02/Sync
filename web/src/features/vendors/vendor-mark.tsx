/**
 * A vendor's own mark, fetched, small, for identification.
 *
 * **This reverses a refusal, on the owner's ruling (decision 6).** The refusal reasoned that Sync
 * holds no image and no brand colour for a vendor, so rendering an id was the honest answer. The
 * half of that argument the decision keeps is the important half and it is kept here literally:
 * **the mark is never redrawn.** Nothing in this file draws a path, approximates a wordmark or
 * picks a brand colour. It requests the vendor's own file from a well-known endpoint and, when
 * that endpoint has none, falls back to letters from the id.
 *
 * **The id remains the identity.** The mark is an aid to finding a row in a list, so it is
 * decorative — `alt=""` — and never replaces the id beside it. A card that showed only a mark
 * would be claiming Sync knows which company a vendor id belongs to, which it does not; it knows
 * a string the graph keys on.
 *
 * **The domain is derived, not known.** Sync holds no homepage for a vendor, so the endpoint is
 * asked about `<id>.com` and the answer is allowed to be "no". That guess is wrong for some
 * vendors and the degradation is what makes being wrong harmless: a miss renders a monogram, which
 * is the same thing that renders when a vendor genuinely has no mark. The alternative — a
 * hard-coded id-to-domain table — would put vendor-specific knowledge in a shared component, which
 * is the arrangement `CLAUDE.md` refuses everywhere else.
 *
 * **This request leaves the machine, and that is a real consequence rather than a footnote.** The
 * endpoint learns which vendors a codebase depends on. Sync holds no customer secrets and a vendor
 * id is not one, but the set of them is a fact about a private codebase, and a deployment that
 * cannot accept that should render monograms. `withoutFetchedMarks` is how that is turned off.
 */

import { useState } from "react"

/**
 * Whether marks are fetched at all.
 *
 * A single switch rather than a prop on every call site, because the decision it encodes is a
 * deployment's, not a screen's.
 */
let fetchMarks = true

/** Render monograms only, never reaching the network. Returns the previous setting. */
export function withoutFetchedMarks(disabled: boolean): boolean {
  const previous = !fetchMarks
  fetchMarks = !disabled
  return previous
}

/** A hostname label: letters, digits and hyphens, not starting or ending with a hyphen. */
const HOSTNAME_LABEL = /^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/

/**
 * Where a vendor's mark is asked for, or `null` when the id cannot be part of a hostname.
 *
 * Returning `null` rather than a sanitised guess is deliberate: an id holding a space or a path
 * separator is not a company this endpoint can answer about, and encoding it into a URL would
 * send a malformed lookup rather than skip one.
 */
export function vendorMarkUrl(vendorId: string): string | null {
  const label = vendorId.trim().toLowerCase()
  if (!HOSTNAME_LABEL.test(label)) return null
  return `https://logo.clearbit.com/${label}.com?size=64`
}

/**
 * The letters shown when no mark is served: one per part of the id, at most two.
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

export interface VendorMarkProps {
  /** The vendor id. Both the lookup key and, on failure, the source of the monogram. */
  readonly vendorId: string
}

export function VendorMark({ vendorId }: VendorMarkProps) {
  const url = fetchMarks ? vendorMarkUrl(vendorId) : null
  const [served, setServed] = useState(true)

  const frame =
    "flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-[4px] border border-line bg-surface-muted"

  if (url === null || !served) {
    return (
      <span className={frame} data-testid="vendor-mark-monogram" aria-hidden="true">
        <span className="font-mono text-meta leading-none text-ink-muted">
          {monogramFor(vendorId)}
        </span>
      </span>
    )
  }

  return (
    <span className={frame}>
      <img
        data-testid="vendor-mark-image"
        src={url}
        alt=""
        width={24}
        height={24}
        loading="lazy"
        referrerPolicy="no-referrer"
        className="size-full object-contain"
        onError={() => setServed(false)}
      />
    </span>
  )
}
