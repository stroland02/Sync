/**
 * The frame every level renders inside.
 *
 * The header used to state the hierarchy as a caption — a sentence describing a navigation
 * that did not exist. `SiteNav` is what the caption becomes: the same ordered graph levels,
 * rendered as destinations instead of words in a paragraph. An operator who knows where they
 * are in the graph still knows what the screen is claiming; now they can also get there.
 */

import { Link, Outlet } from "react-router"

import { ErrorBoundary } from "@/components/error-boundary"
import { ErrorSurface } from "@/components/error-surface"
import { ThemeToggle } from "@/components/theme-toggle"
import { CommandPalette } from "@/layouts/command-palette"
import { SiteNav } from "@/layouts/site-nav"

export function AppShell() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <ErrorSurface />
      <CommandPalette />
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <Link to="/" className="text-emphasis">
            Sync — operator console
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-meta text-muted-foreground">
              <kbd className="rounded-control border border-border bg-muted px-field font-mono text-meta">
                ⌘K
              </kbd>{" "}
              to jump to a screen
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>
      <SiteNav />
      <main className="mx-auto max-w-7xl px-4 py-6">
        <ErrorBoundary>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
