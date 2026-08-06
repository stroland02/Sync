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
 * id, a repository id, a finding id. A destination you can only reach by way of a subject is
 * not a nav destination, it is where you arrive after picking one on another screen, so it is
 * left out of this bar entirely rather than listed as a description of somewhere it cannot
 * link. The graph-level grouping stays even though a level can lose every route this way —
 * `GRAPH_LEVELS.map` below already drops a group with nothing left to show it.
 */

import { Link, matchPath, useLocation } from "react-router"

import { cn } from "@/lib/utils"
import { GRAPH_LEVELS, ROUTES, type RouteEntry } from "@/lib/routes"

function isCurrent(route: RouteEntry, pathname: string): boolean {
  return matchPath({ path: route.path, end: true }, pathname) !== null
}

function NavDestination({ route, current }: { route: RouteEntry; current: boolean }) {
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

export function SiteNav() {
  const { pathname } = useLocation()

  return (
    <nav aria-label="Console navigation" className="border-b border-border bg-surface">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2">
        {GRAPH_LEVELS.map((level, index) => {
          const routesAtLevel = ROUTES.filter(
            (route) => route.level === level && route.params.length === 0
          )
          if (routesAtLevel.length === 0) return null

          return (
            <div key={level} className="flex items-center gap-x-5">
              {index > 0 && (
                <span aria-hidden="true" className="text-meta text-muted-foreground">
                  →
                </span>
              )}
              <div className="flex items-center gap-x-2">
                <span className="text-meta tracking-wide text-muted-foreground uppercase">
                  {level}
                </span>
                <div className="flex flex-wrap items-center gap-x-3">
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
