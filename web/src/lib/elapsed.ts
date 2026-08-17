/**
 * A clock that re-renders, for the two places the console reports how long something has been true.
 *
 * Both are the same question asked from opposite ends. `LoadingState` asks how long a request has
 * been in flight; `FetchedAt` asks how long ago the answer arrived. Neither can be a static string:
 * a screen that renders "0s" once and then holds still is the exact staticness that makes a stuck
 * screen and a slow one indistinguishable.
 *
 * **Wall clock rather than an accumulated tick count.** A background tab throttles timers, so a
 * counter that added one per fire would report a smaller number than the wait the operator actually
 * experienced — and being right about that number is the whole reason either caller exists.
 */

import { useEffect, useState } from "react"

/** Re-render on a cadence and hand back the current instant. */
export function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs])

  return now
}

/**
 * Whole seconds since `since`, never negative.
 *
 * Clamped at zero because `Date.now()` on this machine and a timestamp React Query stamped a
 * moment earlier can disagree by a millisecond, and "-0s ago" is the kind of detail that makes a
 * reader stop trusting every other number on the screen.
 */
export function secondsSince(since: number, now: number): number {
  return Math.max(0, Math.floor((now - since) / 1000))
}

/**
 * The age as an operator would say it: seconds under a minute, then minutes, then hours.
 *
 * Deliberately coarse past a minute. A screen that reports "127s ago" is asking the reader to do
 * arithmetic to learn something they wanted at a glance, and the precision is false comfort — what
 * they are deciding is whether this is current, recent, or old.
 */
export function formatAge(seconds: number): string {
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}
