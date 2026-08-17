/**
 * The console's one motion system. `DESIGN.md`'s Motion section and
 * `docs/superpowers/plans/2026-08-05-sync-console-design-system.md`, "Where motion earns its place,"
 * name the usages this file backs and forbid the rest. A duration or easing written inline anywhere
 * else is the start of a second motion system.
 *
 * **Two usages, not three, as of M4.5-W143.** The third — a `layout` prop on the paginator,
 * described here as "the paged table container settling into its new height after a page swap" —
 * was measured and had never once run: every screen that paginates returns a loading state while
 * `query.isPending`, so a page change unmounts the subtree and a layout animation has no persisting
 * node to measure against. `components/page-controls.tsx` carries the numbers.
 */

import { useReducedMotion as useFramerReducedMotion } from "framer-motion"

/**
 * Every module allowed to import `framer-motion`, and the state change each one tracks.
 *
 * This is a registry, not documentation. `DESIGN.md` and this file's own docstring both already
 * said that motion outside this list is forbidden, and neither could stop a fourth `import
 * { motion } from "framer-motion"` landing in a review nobody ran.
 * `tests/test_console_design_tokens.py` reads this array and asserts it and the tree name the same
 * modules **in both directions**: an unlisted importer fails, and so does an entry that no longer
 * imports anything, so a deletion cannot leave a permission behind for the next person to find.
 *
 * The bar for an entry is the one `DESIGN.md`'s Motion section sets, and it is not "how long feels
 * right": **motion claims a time, so it is permitted where the data holds one, and the surface has
 * to be one the operator meets occasionally rather than crosses on every pointer move.** Adding an
 * entry means writing the state change here, in the operator's terms, beside the module that
 * animates it. If that sentence cannot be written, the animation has not earned itself.
 */
export const MOTION_USAGES = [
  // An unhandled error arrived, and the arrival is the state change. Rare by construction: a
  // console with an API behind it shows this surface on a genuine failure and never otherwise.
  // **It stopped occluding content in M7-W183** — it is now a banner above the chassis that
  // displaces it — so the animated prop is opacity alone. A translate here would be animating a
  // layout shift, which claims a time for a movement the reader did not ask for.
  "components/error-surface.tsx",
  // A node's status changed under a poll: the checkpointer wrote a checkpoint at a moment, which is
  // a time the graph actually holds. Guarded against its own mount and against an unchanged
  // refetch, so it washes only on a real transition — `node-sequence.test.tsx` holds that.
  "features/workflows/node-sequence.tsx",
  // A request is in flight, and how long it has been in flight is the state change. This is the
  // one surface where the claim motion makes is unarguable: the operator is waiting, the waiting
  // has a duration, and the duration is elapsed wall clock rather than anything inferred.
  //
  // **It is a sweep and deliberately not a skeleton.** A skeleton claims a shape — this will be a
  // table, these will be the rows, they will be this wide — and the answer may have no rows at
  // all, which is one of the four kinds of nothing this file exists to keep apart. `B90`'s slice
  // recorded that refusal and it still stands: the words say what is being waited for, the sweep
  // says only that time is passing, and neither asserts what will arrive.
  "components/states.tsx",
] as const

export const EASE_STANDARD: [number, number, number, number] = [0.4, 0, 0.2, 1]

/** `ErrorSurface` arriving and leaving. */
export const ERROR_SURFACE_DURATION = 0.12

/** The changed-under-poll wash: a real checkpoint, not a re-render. */
export const CHANGE_WASH_DURATION = 0.6

/**
 * One pass of the loading sweep.
 *
 * Slow enough to read as waiting rather than as progress: a fast sweep is read as a progress bar
 * that has nearly finished, and this one knows nothing about how far along the request is. The
 * honest reading is "still going", and a sweep at this rate is what produces it.
 */
export const LOADING_SWEEP_DURATION = 1.4

/**
 * How long a request may run before the screen starts saying how long.
 *
 * Under this, the number would appear and vanish on every navigation, which is noise rather than
 * information. Over it, the operator has begun to wonder, and the elapsed count is the honest
 * answer to what they are wondering — it is also the difference between a screen that is slow and
 * a screen that is stuck, which nothing on this console could previously tell apart.
 */
export const LOADING_ELAPSED_THRESHOLD_MS = 2000

/**
 * `prefers-reduced-motion: reduce` must remove every transition below, not shorten it.
 * Framer-motion's built-in reduction only ever strips transform distance, so a fade or a
 * colour wash would keep running under it; every caller reads this and gates its whole
 * animated prop set on it instead.
 */
export function useReducedMotion(): boolean {
  return useFramerReducedMotion() ?? false
}
