/**
 * Every genuine failure the console has seen so far, accumulated and central.
 *
 * `states.tsx` renders the honest per-view answer a reader gets, including the negative
 * ones — a 404, an empty page — that this surface must stay silent on. This is the
 * additional debugging view: a failure that a background poll hit, or that happened in a
 * view not currently on screen, has nowhere else to show up.
 */

import { AnimatePresence, motion } from "framer-motion"
import { useEffect, useSyncExternalStore } from "react"

import { Status } from "@/components/status"
import { Button } from "@/components/ui/button"
import { describeFailure } from "@/lib/describe-failure"
import {
  type ErrorEntry,
  clearErrors,
  dismissError,
  getErrorEntries,
  reportError,
  subscribeErrors,
} from "@/lib/error-log"
import { formatTimestamp, orAbsent } from "@/lib/format"
import {
  EASE_STANDARD,
  ERROR_SURFACE_DURATION,
  ERROR_SURFACE_TRANSLATE_PX,
  useReducedMotion,
} from "@/lib/motion"

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

function Entry({ entry, onDismiss }: { entry: ErrorEntry; onDismiss: () => void }) {
  return (
    <li className="border-b border-border p-3 last:border-b-0">
      <div className="flex items-start justify-between gap-2">
        <p className="text-body font-medium">{entry.summary}</p>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 text-meta text-ink-muted underline underline-offset-2 hover:text-foreground"
        >
          Dismiss
        </button>
      </div>
      <p className="mt-1 font-mono text-meta text-ink-muted">
        {orAbsent(entry.path)}
        {entry.status !== undefined ? ` — HTTP ${entry.status}` : ""} —{" "}
        {formatTimestamp(entry.timestamp)}
      </p>
      <pre className="mt-1 max-h-32 overflow-auto text-meta whitespace-pre-wrap text-foreground">
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
 */
export function ErrorSurface() {
  useUnhandledRejections()
  const entries = useSyncExternalStore(subscribeErrors, getErrorEntries, getErrorEntries)
  const reduceMotion = useReducedMotion()

  const hidden = { opacity: 0, y: -ERROR_SURFACE_TRANSLATE_PX }
  const shown = { opacity: 1, y: 0 }

  return (
    <AnimatePresence>
      {entries.length > 0 && (
        <motion.div
          key="error-surface"
          className="fixed inset-x-0 top-16 z-50 flex justify-center px-4"
          role="alert"
          initial={reduceMotion ? shown : hidden}
          animate={shown}
          exit={reduceMotion ? shown : hidden}
          transition={
            reduceMotion
              ? { duration: 0 }
              : { duration: ERROR_SURFACE_DURATION, ease: EASE_STANDARD }
          }
        >
          <div className="max-h-[70vh] w-full max-w-2xl overflow-hidden rounded border border-critical-ink/40 bg-background shadow-lg">
            <div className="flex items-center justify-between gap-2 border-b border-critical-ink/30 bg-critical-surface px-3 py-2">
              <Status
                tone="critical"
                label={`${entries.length} ${entries.length === 1 ? "error" : "errors"}`}
                className="text-body font-medium"
              />
              <Button variant="outline" size="sm" onClick={() => clearErrors()}>
                Clear all
              </Button>
            </div>
            <ul className="max-h-[calc(70vh-2.5rem)] overflow-auto">
              {entries.map((entry) => (
                <Entry key={entry.id} entry={entry} onDismiss={() => dismissError(entry.id)} />
              ))}
            </ul>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
