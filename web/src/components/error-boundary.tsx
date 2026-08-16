/**
 * The last line between a render crash and a blank screen.
 *
 * React 19 unmounts the subtree an uncaught exception passed through and leaves nothing
 * behind — no message, no box, no clue. On a console whose whole argument is that every state
 * says what happened, a blank region is the worst available failure mode, because it is
 * indistinguishable by eye from an honest empty state.
 *
 * Two things this must not do, and both are easy to get wrong:
 *
 * - **It must not swallow the error.** React hands a caught error to a boundary instead of to
 *   the page, so Vite's overlay never sees it and the browser console may not either. The
 *   throw is therefore logged, and handed to the global error handlers through `reportError`,
 *   which is what puts the overlay back. The overlay is the fastest path from a symptom to a
 *   line in development; this panel is for production and for when nobody is watching it.
 * - **It must not look like an empty state.** `CrashState` carries the reserved critical
 *   treatment for exactly that reason — a screen that failed is not a screen with no data.
 */

import { Component, type ErrorInfo, type ReactNode } from "react"

import { CrashState } from "@/components/states"
import { reportError } from "@/lib/error-log"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
  /** React's own component stack, held so the panel can name what threw. */
  componentStack: string | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    this.setState({ componentStack: info.componentStack ?? null })
    // A crash below the fold must not be visible only where the fold hid it.
    reportError({
      summary: "A component crashed while rendering.",
      detail: `${error.stack ?? error.message}\n${info.componentStack ?? ""}`,
    })
    console.error(error, info.componentStack)
    // `reportError` above is this project's error log, which shadows the global of the same
    // name — hence `globalThis`. This is the line that keeps Vite's overlay working: it
    // raises the original error to the page's own handlers, which a caught error never
    // reaches on its own.
    globalThis.reportError?.(error)
  }

  render(): ReactNode {
    const { error, componentStack } = this.state
    if (error === null) return this.props.children
    return <CrashState error={error} componentStack={componentStack} />
  }
}
