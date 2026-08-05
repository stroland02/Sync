/**
 * The frame every level renders inside.
 *
 * The header states the hierarchy because the navigation *is* the API Dependency Graph:
 * an operator who knows where they are in the graph knows what the screen is claiming.
 */

import { Link, Outlet } from "react-router"

import { ErrorBoundary } from "@/components/error-boundary"
import { ErrorSurface } from "@/components/error-surface"

export function AppShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <ErrorSurface />
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-baseline justify-between gap-2 px-4 py-3">
          <Link to="/" className="text-base font-medium">
            Sync — operator console
          </Link>
          <p className="font-mono text-xs text-muted-foreground">
            Fleet → Codebase → API Services → Errors &amp; Incidents → Finding
          </p>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
