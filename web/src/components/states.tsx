/**
 * What happened, in a sentence, when there is no table to draw.
 *
 * "No findings", "that finding is not open", "the API is not running" and "still asking"
 * are four different answers. A spinner that never resolves and a silent empty table are
 * both the console refusing to say which one it is.
 */

import type { ReactNode } from "react"

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"

function Panel({
  tone,
  headline,
  children,
}: {
  tone: "neutral" | "alarm"
  headline: string
  children: ReactNode
}) {
  return (
    <div
      role={tone === "alarm" ? "alert" : undefined}
      className={
        tone === "alarm"
          ? "rounded border border-destructive bg-destructive/10 p-4 text-destructive"
          : "rounded border border-border p-4 text-muted-foreground"
      }
    >
      <p className="font-medium">{headline}</p>
      <div className="mt-1 text-sm">{children}</div>
    </div>
  )
}

/** The request is in flight. Says what is being asked for, so a stuck screen names itself. */
export function LoadingState({ what }: { what: string }) {
  return (
    <Panel tone="neutral" headline={`Loading ${what}…`}>
      <p>Waiting for the API to answer.</p>
    </Panel>
  )
}

/** The API answered, and the answer was nothing. A true answer, not a failure. */
export function EmptyState({ headline, detail }: { headline: string; detail: string }) {
  return (
    <Panel tone="neutral" headline={headline}>
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
    <Panel tone="neutral" headline={headline}>
      <p>{detail}</p>
      <p className="mt-1 font-mono text-xs">{identifier}</p>
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
    <Panel tone="alarm" headline={headline}>
      <p>{detail}</p>
    </Panel>
  )
}
