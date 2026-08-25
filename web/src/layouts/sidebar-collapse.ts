/**
 * What the sidebar draws, what the frame reserves for it, and what it remembers.
 *
 * **The two widths are page-layout numbers, argued in `DESIGN.md` before they were spent** (M14-W367,
 * the *chassis widths* decision). 240px expanded lands within 6px of mock v1's 246px and is 6× the
 * 40px frame; 48px minimised settles a contradiction the document carried, where the current-row
 * colour ramp argued from "a 48px column with no label in it" while the rail that shipped was 40px.
 * They are spelled here rather than as tokens because each is used once per view and neither is a
 * component value — `layouts/` sits outside the raw-spacing guard's scope for exactly this case.
 *
 * **Two derivations, and keeping them apart is the point.** `sidebarState` answers what the panel
 * draws; `railState` answers what the content column has given up. A pointer moves the first and
 * must never move the second — the reveal is an overlay, and a reserved box that tracked the
 * revealed one would jump the whole page sideways every time a pointer crossed the rail on its way
 * somewhere else.
 *
 * **The operator's choice persists and is never inferred.** `M7-W171` deleted a `collapsed` state
 * initialised from `window.innerWidth` once at mount with no resize listener, which meant a choice
 * did not survive a resize and a viewport that changed after mount was never noticed. Nothing here
 * reads a viewport.
 */

export const SIDEBAR_WIDTH_EXPANDED = "15rem"
export const SIDEBAR_WIDTH_MINIMISED = "3rem"

export type SidebarState = "expanded" | "minimised"

export const SIDEBAR_WIDTH: Record<SidebarState, string> = {
  expanded: SIDEBAR_WIDTH_EXPANDED,
  minimised: SIDEBAR_WIDTH_MINIMISED,
}

/**
 * The key holds the *pin*, which is a different fact from the one the pre-hover key held.
 *
 * The old key stored `minimised`, a state the reader set directly because nothing else could move
 * it. With hover-expand the width is derived from three inputs and only one of them is a stored
 * preference, so a key named for the width would be naming a value it no longer decides. Renamed
 * rather than reinterpreted: `sync-console-sidebar-minimised` holding `"false"` to mean *pinned
 * open* is the kind of double negative that gets read backwards once and is wrong forever after.
 */
export const SIDEBAR_STORAGE_KEY = "sync-console-sidebar-pinned"

/**
 * The stored value as a boolean.
 *
 * Only the exact string `"true"` pins. Absent, malformed, and every other value read as unpinned —
 * the rail, which reveals itself under a pointer or a focus.
 *
 * **The default flipped back on 2026-08-24, by the owner's own specification.** It defaulted to
 * expanded, then to the rail when hover-expand landed, and the Stitch technical specification now
 * asks for "a persistent 240px sidebar with a collapsed 48px icon-only state" — persistent being
 * the word that decides it. Hover-expand stays and so does the pin; what changes is which state a
 * reader who has never chosen gets, and the specification says the full one.
 *
 * Only the exact string `"false"` unpins, so a reader who collapsed it keeps that across reloads.
 */
export function parsePinned(raw: string | null): boolean {
  return raw !== "false"
}

/**
 * `localStorage`, or `null` where it cannot be used.
 *
 * Reading it throws rather than returning null under some privacy modes and inside a sandboxed
 * frame, so the access is guarded. A console that cannot remember the choice still has to render.
 */
function storage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

export function readPinned(): boolean {
  const store = storage()
  if (store === null) return false
  try {
    return parsePinned(store.getItem(SIDEBAR_STORAGE_KEY))
  } catch {
    return false
  }
}

export function writePinned(pinned: boolean): void {
  const store = storage()
  if (store === null) return
  try {
    store.setItem(SIDEBAR_STORAGE_KEY, pinned ? "true" : "false")
  } catch {
    // A full or unavailable store loses the preference for this session. It does not break the
    // chassis, and there is nothing useful to tell the operator about it.
  }
}

/** Everything that can hold the panel open, and nothing that cannot. */
export type Reveal = {
  pinned: boolean
  pointerInside: boolean
  focusInside: boolean
}

/**
 * What the panel draws.
 *
 * `focusInside` is not an afterthought beside `pointerInside`: hover alone would put every label
 * behind a pointer, and a reader tabbing through the sidebar has to see what they are tabbing
 * through. It is also what keeps the panel open after the pointer has left while focus stays in.
 */
export function sidebarState({ pinned, pointerInside, focusInside }: Reveal): SidebarState {
  return pinned || pointerInside || focusInside ? "expanded" : "minimised"
}

/**
 * What the content column has given up, which is exactly what the panel draws.
 *
 * **This used to disagree with `sidebarState` on purpose, and the owner ruled against it.** The
 * panel was an overlay: a reveal drew 240px over a page that had reserved 48px, so it never
 * reflowed the column. The argument was that reflowing under a reader is worse than covering them.
 * Having seen it running, the owner's answer is the opposite -- the sidebar pushes the page and
 * nothing is ever obscured. The screenshot that settled it showed the page heading rendering as
 * "W", the table's first column gone, and the repository names cut off mid-word.
 *
 * Kept as its own function rather than folded into `sidebarState` because the two answer different
 * questions and could diverge again. Today they agree, and the tests say so rather than assuming it.
 */
export function railState(reveal: Reveal): SidebarState {
  return sidebarState(reveal)
}
