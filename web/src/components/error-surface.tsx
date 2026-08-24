/**
 * Every genuine failure the console has seen so far, accumulated and central.
 *
 * `states.tsx` renders the honest per-view answer a reader gets, including the negative
 * ones — a 404, an empty page — that this surface must stay silent on. This is the
 * additional debugging view: a failure that a background poll hit, or that happened in a
 * view not currently on screen, has nowhere else to show up.
 *
 * **It displaces the console rather than floating over it, as of M7-W183.** It used to be `fixed`
 * with a drop shadow, over the content, and the owner's own capture of a branch with no API behind
 * it showed ninety-two stacked *"The API is unreachable"* cards covering the page. Both halves of
 * that were defects. A surface that occludes has to be worth occluding for, and a debugging log is
 * not; and ninety-two cards were one fact drawn ninety-two times. It now renders into a slot above
 * the top bar, in flow, so it pushes the chassis down and nothing a reader needs is behind it.
 *
 * **The cap is presentation and the log is not capped.** `groupErrorsByKind` reads the whole log,
 * so the counts on screen are counts over everything recorded; only the drawing stops at
 * `KINDS_SHOWN`, and the banner says how many kinds it is not drawing.
 */

import { AnimatePresence, motion } from "framer-motion"
import { useEffect, useSyncExternalStore } from "react"

import { Formatted, Status } from "@/components/status"
import { Button } from "@/components/ui/button"
import { describeFailure } from "@/lib/describe-failure"
import {
  type ErrorKind,
  KINDS_SHOWN,
  clearErrors,
  dismissKind,
  getErrorEntries,
  groupErrorsByKind,
  reportError,
  subscribeErrors,
} from "@/lib/error-log"
import { formatTimestamp, orAbsent } from "@/lib/format"
import { ERROR_SURFACE_DURATION, EASE_STANDARD, useReducedMotion } from "@/lib/motion"

/**
 * A rejection outside any component's render path — a background poll's own promise, a
 * fire-and-forget call — never reaches `ErrorBoundary` and never touches a query's error
 * state if it did not go through react-query. This is the only net under that gap.
 */
function useUnhandledRejections(): void {
  useEffect(() => {
    function onRejection(event: PromiseRejectionEvent): void {
      const reason: unknown = event.reason
      const failure = describeFailure(reason) ?? {
        summary: "An unhandled promise rejection occurred.",
        detail:
          reason instanceof Error ? (reason.stack ?? reason.message) : String(reason),
      }
      reportError(failure)
    }
    window.addEventListener("unhandledrejection", onRejection)
    return () => window.removeEventListener("unhandledrejection", onRejection)
  }, [])
}

/**
 * One kind of failure: its newest occurrence, and how many times it has happened.
 *
 * The count is the row's own grain and is stated with the word it counts, because a bare number
 * beside a summary is a number claiming to be whatever the reader guesses.
 */
function Kind({ kind, onDismiss }: { kind: ErrorKind; onDismiss: () => void }) {
  const entry = kind.newest
  return (
    <li className="border-b border-border p-row last:border-b-0">
      <div className="flex items-start justify-between gap-row">
        <p className="text-body font-medium">{entry.summary}</p>
        <div className="flex shrink-0 items-baseline gap-row">
          {kind.count > 1 && (
            <p className="text-meta text-ink-muted">{kind.count} times, most recently</p>
          )}
          <button
            type="button"
            onClick={onDismiss}
            className="text-meta text-ink-muted underline underline-offset-2 hover:text-foreground"
          >
            Dismiss
          </button>
        </div>
      </div>
      <p className="mt-field font-mono text-meta text-ink-muted">
        <Formatted value={orAbsent(entry.path)} />
        {entry.status !== undefined ? ` — HTTP ${entry.status}` : ""} —{" "}
        <Formatted value={formatTimestamp(entry.timestamp)} />
      </p>
      <pre className="mt-field max-h-32 overflow-auto text-meta whitespace-pre-wrap text-foreground">
        {entry.detail}
      </pre>
    </li>
  )
}

/**
 * Renders nothing while the log is empty — an absent failure is not a dismissed one.
 *
 * Every entry accumulated here is a genuine failure, so the header carries the one status
 * claim for the whole panel; individual rows are its detail and stay in plain ink.
 *
 * The animation is opacity alone. This surface changes the height of the page when it arrives, and
 * animating a translate on top of that would be animating a layout shift; the arrival is still a
 * state change worth marking, which is the bar `lib/motion.ts` sets for an entry in its registry.
 */
export function ErrorSurface() {
  useUnhandledRejections()
  const entries = useSyncExternalStore(subscribeErrors, getErrorEntries, getErrorEntries)
  const reduceMotion = useReducedMotion()

  const kinds = groupErrorsByKind(entries)
  const undrawn = kinds.length - KINDS_SHOWN

  return (
    <AnimatePresence>
      {entries.length > 0 && (
        <motion.div
          key="error-surface"
          className="shrink-0 border-b border-critical-ink/40 bg-critical-surface"
          role="alert"
          initial={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={reduceMotion ? { opacity: 1 } : { opacity: 0 }}
          transition={
            reduceMotion
              ? { duration: 0 }
              : { duration: ERROR_SURFACE_DURATION, ease: EASE_STANDARD }
          }
        >
          <div className="flex items-center justify-between gap-row border-b border-critical-ink/30 px-row py-row">
            <Status
              tone="critical"
              label={`${entries.length} ${entries.length === 1 ? "error" : "errors"}`}
              className="text-body font-medium"
            />
            <Button variant="outline" size="sm" onClick={() => clearErrors()}>
              Clear all
            </Button>
          </div>
          <ul className="max-h-64 overflow-auto bg-background">
            {kinds.slice(0, KINDS_SHOWN).map((kind) => (
              <Kind key={kind.key} kind={kind} onDismiss={() => dismissKind(kind.key)} />
            ))}
          </ul>
          {undrawn > 0 && (
            <p className="border-t border-border bg-background px-row py-row text-meta text-ink-muted">
              {undrawn} further {undrawn === 1 ? "kind is" : "kinds are"} in the log and not drawn
              here. Nothing was dropped; the newest {KINDS_SHOWN} kinds are shown.
            </p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  )
}
