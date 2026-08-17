/**
 * Whether the sidebar is minimised, and the two widths it takes.
 *
 * **The two widths are page-layout numbers, argued in `DESIGN.md` before they were spent** (M14-W367,
 * the *chassis widths* decision). 240px expanded lands within 6px of mock v1's 246px and is 6× the
 * 40px frame; 48px minimised settles a contradiction the document carried, where the current-row
 * colour ramp argued from "a 48px column with no label in it" while the rail that shipped was 40px.
 * They are spelled here rather than as tokens because each is used once per view and neither is a
 * component value — `layouts/` sits outside the raw-spacing guard's scope for exactly this case.
 *
 * **The operator's choice persists and is never inferred.** `M7-W171` deleted a `collapsed` state
 * initialised from `window.innerWidth` once at mount with no resize listener, which meant a choice
 * did not survive a resize and a viewport that changed after mount was never noticed. Nothing here
 * reads a viewport.
 */

export const SIDEBAR_WIDTH_EXPANDED = "15rem"
export const SIDEBAR_WIDTH_MINIMISED = "3rem"

export const SIDEBAR_STORAGE_KEY = "sync-console-sidebar-minimised"

/**
 * The stored value as a boolean.
 *
 * Only the exact string `"true"` minimises. Absent, malformed, and every other value read as
 * expanded — the state a reader who has never chosen should get, and the state that shows labels.
 * Defaulting the other way would hide every destination's name from someone who never asked.
 */
export function parseMinimised(raw: string | null): boolean {
  return raw === "true"
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

export function readMinimised(): boolean {
  const store = storage()
  if (store === null) return false
  try {
    return parseMinimised(store.getItem(SIDEBAR_STORAGE_KEY))
  } catch {
    return false
  }
}

export function writeMinimised(minimised: boolean): void {
  const store = storage()
  if (store === null) return
  try {
    store.setItem(SIDEBAR_STORAGE_KEY, minimised ? "true" : "false")
  } catch {
    // A full or unavailable store loses the preference for this session. It does not break the
    // chassis, and there is nothing useful to tell the operator about it.
  }
}
