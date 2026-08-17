/**
 * The frame every level renders inside: one full-height sidebar, and the content column beside it.
 */

import { useEffect, useRef } from "react"
import {
  FileWarning,
  FolderTree,
  GitPullRequest,
  Layers,
  Plug,
  Radar,
  Radio,
  Settings,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import { Link, NavLink, Outlet, useLocation } from "react-router"

import { ErrorSurface } from "@/components/error-surface"
import { CommandPaletteProvider, CommandPaletteTrigger } from "@/layouts/command-palette"
import { ScopeTrail } from "@/layouts/scope-switchers"
import {
  AREAS,
  DESTINATIONS,
  ROUTES,
  boundParams,
  destinationHref,
  isActiveMenuItem,
  type GraphLevel,
  type RouteEntry,
} from "@/lib/routes"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/vendor/supabase/ui/sidebar"

const DESTINATION_ICON: Record<string, LucideIcon> = {
  "/": Radar,
  "/repositories/:repoId": FolderTree,
  "/vendors/:vendorId": Plug,
  "/repositories/:repoId/observed": Radio,
  "/bindings/vendors/:vendorId/operations/:operationId": Layers,
  "/detectors": FileWarning,
  "/findings/:findingId": Wrench,
  "/findings/:findingId/workflow": Workflow,
  "/findings/:findingId/workflow/pull-request": GitPullRequest,
}

/**
 * The rail slot was a disabled button reading "Settings arrives with the write path" for as
 * long as no screen existed. The screen exists now and is read-only, so the note says which of
 * those two things is true rather than continuing to promise the other.
 */
const SETTINGS_NOTE = "Settings — read-only until the write path lands"



function DestinationRow({
  route,
  pathname,
  bound,
}: {
  route: RouteEntry
  pathname: string
  bound: Record<string, string>
}) {
  const Icon = DESTINATION_ICON[route.path] ?? Layers
  const current = isActiveMenuItem(route, pathname)
  const href = destinationHref(route, bound)
  const described =
    href === null && route.reachedFrom !== null
      ? `${route.label} — reached from ${route.reachedFrom}`
      : route.label
  const body = (
    <>
      <Icon aria-hidden="true" />
      <span>{route.label}</span>
    </>
  )

  if (href === null) {
    return (
      <SidebarMenuItem>
        <SidebarMenuButton
          asChild
          isActive={current}
          className="hover:bg-transparent hover:text-foreground-lighter"
        >
          <span
            data-destination={route.path}
            title={described}
            aria-label={described}
            aria-current={current ? "page" : undefined}
          >
            {body}
          </span>
        </SidebarMenuButton>
      </SidebarMenuItem>
    )
  }

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={current}>
        <Link
          to={href}
          data-destination={route.path}
          title={described}
          aria-label={described}
          aria-current={current ? "page" : undefined}
        >
          {body}
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}

function LevelGroup({
  level,
  pathname,
  bound,
}: {
  level: GraphLevel
  pathname: string
  bound: Record<string, string>
}) {
  const routes = ROUTES.filter((route) => route.level === level)
  if (routes.length === 0) return null

  return (
    <SidebarGroup>
      <SidebarGroupLabel className="furniture text-meta text-ink-muted">{level}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {routes.map((route) => (
            <DestinationRow key={route.path} route={route} pathname={pathname} bound={bound} />
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

/**
 * One sidebar, full height, holding every destination.
 *
 * **Two tiers became one, which is a return rather than a new idea.** `M7-W160` built exactly this
 * — its message says "a sidebar that expands to show extra information and minimises to a thin
 * width is one" component — after the owner ruled against a 56px icon rail beside a 240px
 * contextual panel on 2026-08-06. `M7-W171` then re-introduced the two-tier chassis, and the owner
 * ruled against it a second time. This restores the ruling.
 *
 * **Deleting the rail is what forces the list to hold every area.** The rail was the only way to
 * reach an area other than the current one, so a sidebar that still rendered `area.levels` alone
 * would have made five of six areas unreachable — a navigation regression that no route test would
 * catch, because the routes still exist. Every area is a group here for that reason, and
 * `app-frame.test.tsx` asserts the reachability directly.
 */
function AppSidebar({ pathname }: { pathname: string }) {
  const bound = boundParams(pathname)

  return (
    <Sidebar
      collapsible="none"
      className="sticky top-0 h-svh shrink-0 border-r border-line bg-sidebar"
    >
      <nav aria-label="Destinations" className="flex min-h-0 flex-1 flex-col">
        <SidebarHeader className="gap-field px-row py-section">
          <div className="flex items-baseline gap-field pb-field border-b border-line mb-field">
            <span className="font-semibold text-emphasis tracking-tight text-foreground">sync</span>
            <span className="ml-auto font-mono text-meta uppercase tracking-wider text-muted-foreground">console</span>
          </div>
        </SidebarHeader>
        <SidebarContent>
          {AREAS.map((entry) => (
            <div key={entry.id} className="flex flex-col">
              <p className="furniture px-row pt-field text-meta text-ink-muted">{entry.label}</p>
              {entry.levels.map((level) => (
                <LevelGroup key={level} level={level} pathname={pathname} bound={bound} />
              ))}
            </div>
          ))}

          {/* `DESTINATIONS` is a separate registry from `ROUTES` and its entries sit at no graph
              level, so `LevelGroup` — which filters `ROUTES` by level — renders none of them. The
              rail carried Settings in a hard-coded slot; deleting the rail without this group would
              have removed the only way to reach it, while every routing test stayed green because
              the route still exists. */}
          <div className="flex flex-col">
            <p className="furniture px-row pt-field text-meta text-ink-muted">Deployment</p>
            <SidebarGroup>
              <SidebarGroupContent>
                <SidebarMenu>
                  {DESTINATIONS.map((entry) => (
                    <SidebarMenuItem key={entry.path}>
                      <SidebarMenuButton asChild isActive={pathname === entry.path}>
                        <NavLink to={entry.path} title={SETTINGS_NOTE}>
                          <Settings aria-hidden="true" className="size-4 text-graphics" />
                          <span className="text-body">{entry.label}</span>
                        </NavLink>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          </div>
        </SidebarContent>
        <div className="mt-auto flex flex-col gap-field border-t border-line px-row py-field">
          <p className="text-meta text-ink-muted leading-snug">
            Nine graph levels, six areas. An area groups a run of levels — it is not a level itself.
          </p>
          {/* Whose data this is, which nothing on screen said until a console could be served
              somewhere a partner reaches it. The sentence claims only what this console can
              actually know: it reads one graph and filters nothing per viewer. It deliberately
              does not name a deployment — no route serves an identifier for one, and inventing a
              label here would be the console asserting something nothing computed, on the screen
              furniture rather than in a figure. */}
          <p className="text-meta text-ink-muted leading-snug">
            Every screen here reads one deployment's graph, and nothing is filtered per viewer — a
            repository you do not recognise is one this deployment was configured to watch, not
            another customer's.
          </p>
        </div>
      </nav>
    </Sidebar>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
  const contentRef = useRef<HTMLElement>(null)
  const arrivedAt = useRef<string | null>(null)

  /**
   * Focus follows the route, because `react-router` does not move it and this console's navigation
   * hierarchy *is* the API Dependency Graph — focus that stays behind makes the hierarchy itself
   * unavailable to a keyboard or a screen reader, which is the argument
   * `references/notes/roadmap-frontend-skills.md` made and nothing had acted on.
   *
   * The content region takes it rather than the page heading: the heading belongs to the routed
   * screen, and a screen still loading has not rendered one, which would leave focus nowhere on
   * exactly the slowest navigations. `tabIndex={-1}` makes it a programmatic target without adding
   * a stop to the tab order.
   *
   * **First paint is not a navigation.** Arriving at a URL directly should leave focus where the
   * browser put it, so the first pathname is recorded rather than acted on; only a change from it
   * moves focus.
   */
  useEffect(() => {
    if (arrivedAt.current === null) {
      arrivedAt.current = pathname
      return
    }
    if (arrivedAt.current === pathname) return
    arrivedAt.current = pathname
    contentRef.current?.focus()
  }, [pathname])

  // No area-selection state. It existed only so the rail could show one area's destinations while
  // the pointer hovered another; with one list holding every area, there is nothing to select.

  return (
    <CommandPaletteProvider>
      {/* The sidebar is the first child and owns the full height; the bar lives inside the content
          column beside it, not across the top of both. The owner's instruction was that the top bar
          must not sit in front of the sidebar, and mock v1 already draws it this way — its nav
          measures {x:0, y:0, 246x900} and its header starts at x:246.

          `ErrorSurface` moved inside the content column with the bar, and that is a decision rather
          than a consequence of moving the header. Above the chassis it displaced everything
          including the navigation; here it displaces only the content. Navigation should survive a
          panel's failure — you need it most when something is broken. `app-frame.test.tsx` passes
          either way, so nothing in CI would have told us which one shipped. */}
      <SidebarProvider
        defaultOpen={false}
        className="flex min-h-svh items-start bg-background text-foreground"
      >
        <AppSidebar pathname={pathname} />

        <div className="flex min-w-0 flex-1 flex-col">
          <ErrorSurface />

          <header
            role="banner"
            className="sticky top-0 z-30 flex h-12 shrink-0 items-center justify-between gap-section border-b border-line bg-background px-section"
          >
            <div className="flex min-w-0 flex-1 items-center">
              <ScopeTrail />
            </div>
            <CommandPaletteTrigger />
          </header>

          <main ref={contentRef} tabIndex={-1} className="flex flex-1 flex-col gap-8 p-frame outline-none">
            <Outlet />
          </main>
        </div>
      </SidebarProvider>
    </CommandPaletteProvider>
  )
}
