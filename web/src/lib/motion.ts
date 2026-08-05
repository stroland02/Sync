/**
 * The console's one motion system. `docs/superpowers/plans/2026-08-05-sync-console-design-
 * system.md`, "Where motion earns its place," names the three usages this file backs and
 * forbids the rest. A duration or easing written inline anywhere else is the start of a
 * second motion system.
 */

import { useReducedMotion as useFramerReducedMotion } from "framer-motion"

export const EASE_STANDARD: [number, number, number, number] = [0.4, 0, 0.2, 1]

/** `ErrorSurface` arriving and leaving — the one thing in the console that floats. */
export const ERROR_SURFACE_DURATION = 0.12
export const ERROR_SURFACE_TRANSLATE_PX = 4

/** The changed-under-poll wash: a real checkpoint, not a re-render. */
export const CHANGE_WASH_DURATION = 0.6

/** The paged table container settling into its new height after a page swap. */
export const HEIGHT_TRANSITION_DURATION = 0.2

/**
 * `prefers-reduced-motion: reduce` must remove every transition below, not shorten it.
 * Framer-motion's built-in reduction only ever strips transform distance, so a fade or a
 * colour wash would keep running under it; every caller reads this and gates its whole
 * animated prop set on it instead.
 */
export function useReducedMotion(): boolean {
  return useFramerReducedMotion() ?? false
}
