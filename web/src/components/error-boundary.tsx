/**
 * The last line between a render crash and a blank screen.
 *
 * A blank page during dogfooding destroys the evidence of what broke, so this renders the
 * error in place of the subtree that threw it, and also files it on the central surface —
 * a crash below the fold must not be visible only where the fold hid it.
 */

import { Component, type ErrorInfo, type ReactNode } from "react"

import { reportError } from "@/lib/error-log"
import { Status, statusSurfaceClass } from "@/components/status"

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportError({
      summary: "A component crashed while rendering.",
      detail: `${error.stack ?? error.message}\n${info.componentStack ?? ""}`,
    })
  }

  render(): ReactNode {
    const { error } = this.state
    if (error === null) return this.props.children
    return (
      <div role="alert" className={`rounded border p-4 ${statusSurfaceClass("critical")}`}>
        <Status tone="critical" label="This part of the console crashed." className="font-medium" />
        <p className="mt-1 text-sm">
          {error.message} — recorded on the error surface above, with the full stack.
        </p>
      </div>
    )
  }
}
