/**
 * The frame every level renders inside: a fixed rail, a contextual sidebar, and the content.
 *
 * This replaces `app-shell.tsx` and `site-nav.tsx`, which between them rendered a horizontal strip
 * of every linkable destination and put the whole page in a 24px gutter under it.
 * `docs/superpowers/reports/2026-08-06-why-the-console-came-out-flat.md` traces why that was built
 * and it was not a mistake: `.claude/rules/interface-originality.md` said a navigation shape may not
 * be taken, every agent read it correctly, and a strip is what you get. The rule was amended on
 * 2026-08-06 to separate the **conventions of the form** — a rail, a sidebar, a page header, a
 * footer bar — from identity, which is colour, wordmark, copy, illustration, and the specific
 * arrangement that makes a screen recognisably somebody else's. A rail is a convention. What goes
 * in it is ours.
 *
 * **Two levels of navigation, and they answer different questions.** The rail asks *which part of
 * the product*, does not change between routes, and is four items because `AREAS` groups the nine
 * specification levels into four contiguous runs. The sidebar asks *where inside it*, carries the
 * area's name as a heading and its levels as `.furniture` group labels, and changes with the rail
 * rather than with the route — so an operator can read what the Graph area contains before they
 * have picked a repository, which the strip could not express at all.
 *
 * **The sidebar shows a destination it cannot link.** Seven of nine routes need a subject the
 * registry does not hold, and the old strip solved that by omitting them: a reader learned the level
 * existed from `GRAPH_LEVELS` and never learned how to reach it. Here an unlinkable destination
 * renders with `reachedFrom` beside it — "the finding it remediates" — which is a fact about the
 * graph rather than a placeholder.
 *
 * The collapse is not a preference control. A nine-column evidence table at 1280px wants the
 * sidebar's 240px, and `M4.5-W144` measured what that width costs: the binding surface's own path
 * column was 40px short of one line. Collapsing keeps the rail, so the areas stay reachable and
 * only the labels go.
 */

import { useState } from "react"
import {
  Layers,
  ListTree,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import { Link, Outlet, matchPath, useLocation } from "react-router"

import { ErrorSurface } from "@/components/error-surface"
import { CommandPalette } from "@/layouts/command-palette"
import { AREAS, ROUTES, type AreaEntry, type RouteEntry } from "@/lib/routes"
import { cn } from "@/lib/utils"

/**
 * One icon per area, keyed by `AreaEntry.id`.
 *
 * Kept here rather than in `routes.ts` because that registry is pinned by two Python tests and a
 * vitest file and has no business importing a React component. `lucide-react` is already the
 * console's icon source — `DESIGN.md` names it in the rule that a status colour never travels
 * without an icon and a word — and a generic icon set is not somebody's iconography.
 */
const AREA_ICON: Record<string, LucideIcon> = {
  fleet: Radar,
  graph: ListTree,
  findings: Layers,
  remediation: Wrench,
}

function routesInArea(area: AreaEntry): RouteEntry[] {
  return ROUTES.filter((route) => area.levels.includes(route.level))
}

/** The area a path is inside, by the level of the route that matches it. */
function areaOfPath(pathname: string): AreaEntry | null {
  const route = ROUTES.find((r) => matchPath({ path: r.path, end: true }, pathname) !== null)
  if (route === undefined) return null
  return AREAS.find((area) => area.levels.includes(route.level)) ?? null
}

function RailItem({
  area,
  active,
  onSelect,
}: {
  area: AreaEntry
  active: boolean
  onSelect: () => void
}) {
  const Icon = AREA_ICON[area.id] ?? Layers
  const surface = active
    ? "bg-surface-emphasis text-foreground"
    : "text-ink-muted hover:bg-surface-subtle hover:text-foreground"
  const shape = "flex size-10 items-center justify-center rounded-control"

  // An area with a landing route is a link, so browser Back and open-in-new-tab both work. One
  // without is a button: it selects the sidebar and navigates nowhere, because there is nowhere to
  // navigate to until a subject has been picked.
  if (area.landing !== null) {
    return (
      <Link
        to={area.landing}
        aria-current={active ? "page" : undefined}
        title={area.label}
        onClick={onSelect}
        className={cn(shape, surface)}
      >
        <Icon aria-hidden="true" className="size-5" />
        <span className="sr-only">{area.label}</span>
      </Link>
    )
  }

  return (
    <button
      type="button"
      aria-pressed={active}
      title={area.label}
      onClick={onSelect}
      className={cn(shape, surface)}
    >
      <Icon aria-hidden="true" className="size-5" />
      <span className="sr-only">{area.label}</span>
    </button>
  )
}

function SidebarDestination({ route, current }: { route: RouteEntry; current: boolean }) {
  if (route.params.length > 0) {
    return (
      <div className="flex flex-col gap-field">
        <span className="text-body text-ink-muted">{route.label}</span>
        <span className="text-meta text-ink-muted">Reached from {route.reachedFrom}.</span>
      </div>
    )
  }

  return (
    <Link
      to={route.path}
      aria-current={current ? "page" : undefined}
      className={cn(
        "rounded-control px-row py-field text-body",
        current
          ? "bg-surface-emphasis font-medium text-foreground"
          : "text-foreground hover:bg-surface-subtle"
      )}
    >
      {route.label}
    </Link>
  )
}

function Sidebar({ area, pathname }: { area: AreaEntry; pathname: string }) {
  return (
    <div className="flex w-60 shrink-0 flex-col gap-section border-r border-line px-section py-section">
      <div className="flex flex-col gap-field">
        <h2 className="text-section">{area.label}</h2>
        <p className="text-meta text-ink-muted">{area.purpose}</p>
      </div>
      {area.levels.map((level) => {
        const routes = routesInArea(area).filter((route) => route.level === level)
        if (routes.length === 0) return null
        return (
          <div key={level} className="flex flex-col gap-field">
            <span className="furniture text-meta text-ink-muted">{level}</span>
            {routes.map((route) => (
              <SidebarDestination
                key={route.path}
                route={route}
                current={matchPath({ path: route.path, end: true }, pathname) !== null}
              />
            ))}
          </div>
        )
      })}
    </div>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
  const routeArea = areaOfPath(pathname)
  // The rail's selection follows the route until an operator overrides it, and a navigation clears
  // the override: `selected` is keyed by the area the path resolves to, so landing on a finding puts
  // you back in Findings rather than leaving you in whatever you last clicked.
  const [override, setOverride] = useState<{ areaId: string; from: string } | null>(null)
  const activeAreaId =
    override !== null && override.from === (routeArea?.id ?? "")
      ? override.areaId
      : (routeArea?.id ?? AREAS[0].id)
  const activeArea = AREAS.find((area) => area.id === activeAreaId) ?? AREAS[0]
  // Open where there is room for it, closed where it costs a row. Measured on the binding surface —
  // the console's densest screen, nine columns — at `--scale 10000`, reading the content box inside
  // the frame and the row height it produces:
  //
  //   1440, sidebar closed:  1289px, call site 279px, row 57px   <- M4.5-W144's number, held
  //   1440, sidebar open:    1049px, call site 204px, row 77px
  //   1280, sidebar closed:  1129px, call site 229px, row 77px
  //
  // So the breakpoint is a measurement rather than a convention. **And it does not recover
  // everything: at 1280 the row is 77px with the sidebar already closed**, because the frame growing
  // 24 -> 40px and the rail taking 56px remove 88px between them, which is enough on its own to push
  // the call-site path onto a third line. That is a real cost of this item paid by the one screen
  // B115 already measured as 5–22px short of fitting, and it is recorded there rather than left for
  // somebody to rediscover as a mystery regression.
  //
  // The rail is never what collapses: every area stays one click away at any width, which is the
  // half of the navigation that replaced the old horizontal strip. Read once at mount rather than
  // through a resize listener — an operator who has opened the sidebar has said what they want, and
  // a window drag must not overrule them.
  const [sidebarOpen, setSidebarOpen] = useState(
    () => typeof window === "undefined" || window.innerWidth >= 1440
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <ErrorSurface />
      <CommandPalette />

      <nav
        aria-label="Product areas"
        className="flex w-14 shrink-0 flex-col items-center gap-row border-r border-line bg-surface py-section"
      >
        <button
          type="button"
          aria-expanded={sidebarOpen}
          title={sidebarOpen ? "Collapse the sidebar" : "Expand the sidebar"}
          onClick={() => setSidebarOpen((open) => !open)}
          className="flex size-10 items-center justify-center rounded-control text-ink-muted hover:bg-surface-subtle hover:text-foreground"
        >
          {sidebarOpen ? (
            <PanelLeftClose aria-hidden="true" className="size-5" />
          ) : (
            <PanelLeftOpen aria-hidden="true" className="size-5" />
          )}
          <span className="sr-only">
            {sidebarOpen ? "Collapse the sidebar" : "Expand the sidebar"}
          </span>
        </button>
        {AREAS.map((area) => (
          <RailItem
            key={area.id}
            area={area}
            active={area.id === activeAreaId}
            onSelect={() => setOverride({ areaId: area.id, from: routeArea?.id ?? "" })}
          />
        ))}
      </nav>

      {sidebarOpen && <Sidebar area={activeArea} pathname={pathname} />}

      {/* `min-w-0` is what lets a nine-column table shrink instead of pushing the sidebar off the
          viewport: a flex child defaults to its content's minimum width, and a table's is the sum
          of its columns. Without it, collapsing the sidebar would be the only way to read the
          binding surface, which is the opposite of what the collapse is for. */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* No error boundary here. `App.tsx` puts one inside each routed screen instead, keyed by
            pathname — one out here survives navigation and turns a single crash into a console that
            stays crashed. */}
        <main className="flex flex-1 flex-col gap-8 p-frame">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
