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

import { useState, type ReactNode } from "react"

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"
import { Status, statusSurfaceClass, type StatusTone } from "@/components/status"
import { Button } from "@/components/ui/button"

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
          ? `max-w-prose rounded border p-4 ${statusSurfaceClass(status)}`
          : "max-w-prose rounded border border-border p-4 text-muted-foreground"
      }
    >
      {status ? (
        <Status tone={status} label={headline} className="text-emphasis" />
      ) : (
        <p className="text-emphasis text-foreground">{headline}</p>
      )}
      <div className="mt-1 text-body">{children}</div>
    </div>
  )
}

/** The request is in flight. Says what is being asked for, so a stuck screen names itself. */
export function LoadingState({ what }: { what: string }) {
  return (
    <Panel headline={`Loading ${what}…`}>
      <p>Waiting for the API to answer.</p>
    </Panel>
  )
}

/** The API answered, and the answer was nothing. A true answer, not a failure. */
export function EmptyState({ headline, detail }: { headline: string; detail: string }) {
  return (
    <Panel headline={headline}>
      <p>{detail}</p>
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
      <p className="mt-1 font-mono text-meta">{identifier}</p>
    </Panel>
  )
}

interface Explanation {
  headline: string
  detail: string
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
    return {
      headline: "The API does not hold that identifier.",
      detail: `${error.message} (${error.identifier})`,
    }
  }
  return {
    headline: "The request failed for a reason the console does not recognise.",
    detail: error instanceof Error ? error.message : String(error),
  }
}

/** Something went wrong between here and the graph. Says which something. */
export function ErrorState({ error, what }: { error: unknown; what: string }) {
  const { headline, detail } = explain(error, what)
  return (
    <Panel status="critical" headline={headline}>
      <p>{detail}</p>
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
