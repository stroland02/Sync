/**
 * What happened, in a sentence, when there is no table to draw.
 *
 * "No findings", "that finding is not open", "the API is not running" and "still asking"
 * are four different answers. A spinner that never resolves and a silent empty table are
 * both the console refusing to say which one it is.
 *
 * A component that threw is a fifth answer and not one of the four kinds of nothing above:
 * the screen did not come back empty, it stopped. React 19 unmounts the subtree and leaves a
 * hole, which on this console is the worst available failure mode — indistinguishable by
 * eye from an honest empty state. `CrashState` is what stands in that hole.
 */

import { motion } from "framer-motion"
import { useState, type ReactNode } from "react"

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"
import { Status, statusSurfaceClass, type StatusTone } from "@/components/status"
import { Button } from "@/components/ui/button"
import { secondsSince, useNow } from "@/lib/elapsed"
import {
  EASE_STANDARD,
  LOADING_ELAPSED_THRESHOLD_MS,
  LOADING_SWEEP_DURATION,
  useReducedMotion,
} from "@/lib/motion"

function Panel({
  status,
  headline,
  children,
}: {
  /** Present only for a genuine failure. Absent, the headline is identity, not a verdict. */
  status?: StatusTone
  headline: string
  children: ReactNode
}) {
  return (
    <div
      role={status ? "alert" : undefined}
      className={
        status
          ? `max-w-prose rounded-surface border p-section ${statusSurfaceClass(status)}`
          : "max-w-prose rounded-surface border border-border p-section text-muted-foreground"
      }
    >
      {status ? (
        <Status tone={status} label={headline} className="text-emphasis" />
      ) : (
        <p className="text-emphasis text-foreground">{headline}</p>
      )}
      <div className="mt-field text-body">{children}</div>
    </div>
  )
}

/**
 * How long this component has been mounted, in whole seconds, or `null` before the threshold.
 *
 * A loading state is mounted exactly while its request is in flight, so its own lifetime is the
 * request's. That makes elapsed time the one figure this surface can report without inferring
 * anything — it is measured here rather than taken from the query client, which would report the
 * fetch's age across a retry and describe a different span than the one the operator is watching.
 */
function useElapsedSeconds(): number | null {
  const [startedAt] = useState(() => Date.now())
  const now = useNow(250)

  const elapsedMs = now - startedAt
  if (elapsedMs < LOADING_ELAPSED_THRESHOLD_MS) return null
  return secondsSince(startedAt, now)
}

/**
 * A sweep across a track, running while the request is.
 *
 * Indeterminate on purpose. Nothing here knows how far along the request is, so a fill that grew
 * toward an end would be claiming progress it cannot measure — the same defect as a percentage
 * invented to fill a bar. What this claims is only that time is passing, which is true for exactly
 * as long as the component is mounted.
 *
 * Under `prefers-reduced-motion` the track renders and does not move. The elapsed count below it
 * keeps running, because that is information rather than motion, and a reader who has asked for
 * less movement has not asked to be told less.
 */
function LoadingSweep() {
  const reduced = useReducedMotion()

  return (
    <div
      className="mt-row h-px w-full overflow-hidden bg-surface-subtle"
      role="presentation"
      aria-hidden="true"
    >
      {reduced ? null : (
        <motion.div
          className="h-px w-1/3 bg-surface-emphasis"
          initial={{ x: "-100%" }}
          animate={{ x: "300%" }}
          transition={{
            duration: LOADING_SWEEP_DURATION,
            ease: EASE_STANDARD,
            repeat: Infinity,
            repeatType: "loop",
          }}
        />
      )}
    </div>
  )
}

/** The request is in flight. Says what is being asked for, so a stuck screen names itself. */
export function LoadingState({ what }: { what: string }) {
  const elapsed = useElapsedSeconds()

  return (
    <Panel headline={`Loading ${what}…`}>
      <p>
        Waiting for the API to answer.
        {/* The sentence above is the honest minimum and does not move. What follows is added only
            once the wait is long enough to be a fact worth reporting: a screen that is slow and a
            screen that is stuck look identical without it, and telling those apart is the whole
            job of this file. */}
        {elapsed === null ? null : (
          <span className="text-muted-foreground"> {elapsed}s so far.</span>
        )}
      </p>
      <LoadingSweep />
    </Panel>
  )
}

/** The API answered, and the answer was nothing. A true answer, not a failure. */
export function EmptyState({
  headline,
  detail,
  action,
  command,
}: {
  headline: string
  detail: string
  /** Where a reader goes to populate this. A link, usually into Settings or a sibling screen. */
  action?: ReactNode
  /**
   * The command that fills it, for the cases where the answer is a terminal rather than a screen.
   *
   * **Owner direction, 2026-08-19: no panel that just sits there.** An empty state that explains
   * itself and stops leaves a reader knowing what is missing and not how to get it -- twenty-seven
   * components did exactly that. The console cannot run these commands (`console-dev-loop.md`: no
   * route mutates the graph or triggers a run), so what it can honestly offer is the exact
   * invocation, copyable, rather than a button that would have to lie about what it did.
   */
  command?: string
}) {
  return (
    <Panel headline={headline}>
      <p>{detail}</p>
      {command !== undefined && (
        <code className="mt-row block overflow-x-auto rounded-control border border-line bg-surface-subtle px-field py-field font-mono text-meta text-ink select-all">
          {command}
        </code>
      )}
      {action !== undefined && <div className="mt-row flex flex-wrap gap-row">{action}</div>}
    </Panel>
  )
}

/** The API answered 404 for this identifier. */
export function NotFoundState({
  headline,
  detail,
  identifier,
}: {
  headline: string
  detail: string
  identifier: string
}) {
  return (
    <Panel headline={headline}>
      <p>{detail}</p>
      <p className="mt-field font-mono text-meta">{identifier}</p>
    </Panel>
  )
}

interface Explanation {
  headline: string
  detail: string
  /** What came back, quoted rather than interpreted. Rendered verbatim, below the prose. */
  evidence?: string
}

function explain(error: unknown, what: string): Explanation {
  if (error instanceof UnreachableApiError) {
    return {
      headline: "Could not reach the API.",
      detail:
        `The request for ${what} never reached a server. The Python API behind /api is ` +
        "probably not running: start it with uv run python -m sync.api.",
    }
  }
  if (error instanceof ApiStatusError && error.status >= 500) {
    return {
      headline: `The API failed to answer (HTTP ${error.status}).`,
      detail:
        `A server answered the request for ${what}, but with an error rather than data. ` +
        "In development this is also what the Vite proxy returns when the Python API is not listening.",
    }
  }
  if (error instanceof ApiStatusError) {
    return {
      headline: `The API refused the request (HTTP ${error.status}).`,
      detail: `The request for ${what} reached the API and was rejected.`,
    }
  }
  if (error instanceof MalformedResponseError) {
    return {
      headline: "The API answered with something that is not JSON.",
      detail:
        `Whatever served ${what} is not the Sync API — check that /api is proxied to the ` +
        "Python transport and not to a static server.",
    }
  }
  if (error instanceof NotFoundError) {
    // Two different failures arrive as one status and the response cannot tell them apart, so
    // this must not choose between them. B147 is the proof: /api/repositories/{repo_id}/coverage
    // takes the default path converter, which cannot match a repo_id containing slashes, so a
    // repository /api/repositories does list answers 404 anyway. Copy asserting the API does not
    // hold the identifier was false on that screen.
    return {
      headline: "The API answered 404 for this request.",
      detail:
        `The request for ${what} did not resolve. Either this URL matches no route, or the ` +
        "API holds no record behind it — a 404 does not say which.",
      evidence: `${error.message} — ${error.path}`,
    }
  }
  return {
    headline: "The request failed for a reason the console does not recognise.",
    detail: error instanceof Error ? error.message : String(error),
  }
}

/**
 * Something went wrong between here and the graph. Says which something, and offers a way back.
 *
 * **`onRetry` is optional and its absence renders no control**, rather than a button that reloads
 * the page. A caller with a query in hand passes that query's `refetch`; a caller without one has
 * nothing honest to offer, and a dead control that appears to retry and does not is worse than no
 * control at all.
 *
 * The button is an addition to the explanation and never a replacement for it. The reader still
 * needs to know what failed — `reports/2026-08-17-gate-3-empty-state.md` measured that the console
 * already distinguishes a failed fetch from an empty answer, and that distinction lives in this
 * headline. What was missing was only the recourse: without it the sole option is a full page
 * reload, which re-fetches every other panel and discards the reader's scroll position and filters.
 */
export function ErrorState({
  error,
  what,
  onRetry,
}: {
  error: unknown
  what: string
  onRetry?: () => void
}) {
  const { headline, detail, evidence } = explain(error, what)
  return (
    <Panel status="critical" headline={headline}>
      <p>{detail}</p>
      {evidence !== undefined && <p className="mt-field font-mono text-meta">{evidence}</p>}
      {onRetry !== undefined && (
        <p>
          <button
            type="button"
            onClick={onRetry}
            className="text-body underline underline-offset-2 hover:text-foreground"
          >
            Try again
          </button>
        </p>
      )}
    </Panel>
  )
}

/**
 * The component React names first in its stack: the one that threw.
 *
 * Returns null rather than a guess when the stack is absent or shaped differently — React
 * does not promise this format, and a wrong component name sends a reader to the wrong file,
 * which is worse than sending them to the stack below.
 */
function throwingComponent(componentStack: string | null): string | null {
  const frame = (componentStack ?? "")
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("at "))
  if (frame === undefined) return null
  const name = frame.slice(3).split(" ")[0]
  return name === undefined || name === "" ? null : name
}

/**
 * Everything a reader would otherwise have to retype out of a screenshot.
 *
 * The copy exists because the alternative is a bug report that says "it went blank", which
 * is the report this whole panel exists to stop being the only one available.
 */
function CopyReport({ text }: { text: string }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle")
  return (
    <div className="flex flex-col gap-field">
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          void navigator.clipboard.writeText(text).then(
            () => setState("copied"),
            () => setState("failed"),
          )
        }}
      >
        {state === "copied" ? "Copied" : "Copy this error"}
      </Button>
      {state === "failed" && (
        <p className="text-meta">
          The browser refused the clipboard. Select the text above instead — it is the whole
          report.
        </p>
      )}
    </div>
  )
}

/**
 * A component threw while rendering, and this is what stands where it was.
 *
 * Deliberately not an empty state and deliberately not silent: it carries the reserved
 * critical treatment the four answers above reserve for a genuine failure, because a screen
 * that stopped is one. `ErrorBoundary` also logs the throw, so the browser console and Vite's
 * overlay still see it — this panel is what a reader gets in production and whenever the
 * overlay is not being watched, never a replacement for either.
 */
export function CrashState({
  error,
  componentStack,
}: {
  error: Error
  componentStack: string | null
}) {
  const component = throwingComponent(componentStack)
  const report = [error.stack ?? error.message, componentStack ?? ""]
    .filter((part) => part !== "")
    .join("\n\n")

  return (
    <Panel status="critical" headline="This screen stopped rendering.">
      <div className="flex flex-col gap-row">
        <p>
          A component threw while React was rendering it, so React removed the subtree. This
          is a failure of the console, not an answer about the data — nothing below was read
          from the graph.
        </p>
        <p>
          {component === null ? (
            "React recorded no component stack for this throw, so the component that threw is not named here; the stack below is everything it did record."
          ) : (
            <>
              The component that threw is <code className="font-mono">{component}</code>.
            </>
          )}
        </p>
        <p className="font-mono">{error.message}</p>
        <pre className="max-h-72 overflow-auto rounded border border-border p-row font-mono text-meta whitespace-pre-wrap">
          {report}
        </pre>
        <CopyReport text={report} />
      </div>
    </Panel>
  )
}
