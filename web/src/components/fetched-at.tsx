/**
 * When what is on screen was last true, and whether anything is still asking.
 *
 * Staleness apart from liveness is one of the four distinctions this console exists to render, and
 * until now it was rendered on exactly one screen — `workflow-page.tsx` reached for
 * `query.dataUpdatedAt`, and nothing else did. Every other polled surface showed rows with no
 * answer to "when was this true?", which is the question a reviewer has to answer before acting on
 * any of them.
 *
 * **No dot, no pulse, no `Live` badge.** `CLAUDE.md` refuses a liveness pulse by name, and the
 * refusal is right for the reason it always was: nothing in our data distinguishes a poll that is
 * working from one whose last three attempts quietly failed, so a lit indicator would assert a
 * health we cannot check. What we do hold is the instant the last successful fetch returned. That
 * is a recorded value, so it renders as a recorded value — in words, with its age, ticking.
 *
 * **A poll that has stopped is not the same as a poll that has stalled**, and the difference is
 * always the caller's to state. `useRuns` stops the moment no run on the page is in flight and
 * `useWorkflow` stops at a terminal outcome; both are the query finishing its job. A reader who
 * cannot tell that from a broken poll will either distrust fresh data or trust stale data, and
 * there is no third outcome.
 */

import { formatAge, secondsSince, useNow } from "@/lib/elapsed"

/** One second, because the number this renders is measured in seconds. */
const TICK_MS = 1000

export function FetchedAt({
  at,
  polling,
  idleReason,
  className,
}: {
  /** `query.dataUpdatedAt` — when the last successful fetch returned, not when it was asked. */
  at: number
  /** Whether a background refetch is still scheduled. */
  polling: boolean
  /**
   * Why nothing is polling, in the operator's terms, when `polling` is false.
   *
   * Required rather than optional so a caller cannot leave the screen silent about it. A surface
   * that stops polling and says nothing reads as one that is still watching, which is the more
   * dangerous of the two misreadings.
   */
  idleReason: string
  className?: string
}) {
  const now = useNow(TICK_MS)

  // A query that has never resolved has no instant to report. Its own loading state is already
  // saying so, and a second component inventing "0s ago" for data that does not exist would be
  // asserting a fetch that never happened.
  if (!at) return null

  return (
    <p className={className ? `text-body text-muted-foreground ${className}` : "text-body text-muted-foreground"}>
      As of {formatAge(secondsSince(at, now))}.{" "}
      {polling ? "Refreshing in the background." : idleReason}
    </p>
  )
}
