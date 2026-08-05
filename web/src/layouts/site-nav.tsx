/**
 * The persistent navigation, rendered from the route registry.
 *
 * `app-shell.tsx` used to state the graph hierarchy as a caption:
 * "Fleet -> Codebase -> API Services -> Errors & Incidents -> Finding". That sentence was
 * true and led nowhere. It is not deleted here — `GRAPH_LEVELS` carries the same ordered
 * names, and this component is what turns each one into a group of destinations instead of
 * a word in a paragraph.
 *
 * Always visible, never behind a menu button: a hidden navigation is how this console ended
 * up with seven of eleven routes unreachable in the first place, one shortcut at a time.
 *
 * A route whose `params` is non-empty needs a subject this registry does not hold — a vendor
 * id, a repository id, a finding id — so it renders here as a description of a destination
 * rather than as a link with nothing to point at. It is still reachable, from the row that
 * names its subject on another screen; the two exceptions, `/findings/:findingId` and
 * `/vendors/:vendorId`, are already linked from the fleet and the codebase screens today.
 */

import { Link, matchPath, useLocation } from "react-router"

import { cn } from "@/lib/utils"
import { GRAPH_LEVELS, ROUTES, type RouteEntry } from "@/lib/routes"

function isCurrent(route: RouteEntry, pathname: string): boolean {
  return matchPath({ path: route.path, end: true }, pathname) !== null
}

function NavDestination({ route, current }: { route: RouteEntry; current: boolean }) {
  if (route.params.length === 0) {
    return (
      <Link
        to={route.path}
        aria-current={current ? "page" : undefined}
        className={cn(
          "text-body underline-offset-2 hover:underline",
          current ? "font-medium text-brand" : "text-foreground"
        )}
      >
        {route.label}
      </Link>
    )
  }

  // Needs a subject: rendered as text, not a link, so nothing here is a dead href. Still
  // marked current when its pattern matches, so an operator on a parameterised screen can
  // see where in the graph they landed.
  return (
    <span
      aria-current={current ? "page" : undefined}
      title={route.question}
      className={cn(
        "text-body",
        current ? "font-medium text-brand" : "text-muted-foreground"
      )}
    >
      {route.label}
      <span className="text-meta text-muted-foreground"> (needs a subject)</span>
    </span>
  )
}

export function SiteNav() {
  const { pathname } = useLocation()

  return (
    <nav aria-label="Console navigation" className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-7xl flex-wrap items-start gap-x-6 gap-y-3 px-4 py-3">
        {GRAPH_LEVELS.map((level, index) => {
          const routesAtLevel = ROUTES.filter((route) => route.level === level)
          if (routesAtLevel.length === 0) return null

          return (
            <div key={level} className="flex items-start gap-x-6">
              {index > 0 && (
                <span aria-hidden="true" className="pt-5 text-meta text-muted-foreground">
                  →
                </span>
              )}
              <div className="flex flex-col gap-1">
                <span className="text-meta tracking-wide text-muted-foreground uppercase">
                  {level}
                </span>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {routesAtLevel.map((route) => (
                    <NavDestination
                      key={route.path}
                      route={route}
                      current={isCurrent(route, pathname)}
                    />
                  ))}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </nav>
  )
}
