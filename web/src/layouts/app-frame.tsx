/**
 * The frame every level renders inside: a fixed icon rail, a contextual sidebar, and the content.
 */

import { useEffect, useRef, useState } from "react"
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
  areaForPathname,
  boundParams,
  destinationHref,
  isActiveMenuItem,
  type Area,
  type AreaEntry,
  type GraphLevel,
  type RouteEntry,
} from "@/lib/routes"
import { cn } from "@/lib/utils"
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
  useSidebar,
} from "@/vendor/supabase/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/vendor/supabase/ui/tooltip"

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

const AREA_ICON: Record<Area, LucideIcon> = {
  fleet: Radar,
  codebase: FolderTree,
  "api-services": Plug,
  signals: Radio,
  observe: Layers,
  remediation: Wrench,
}

const RAIL_ITEM = "flex size-8 items-center justify-center rounded-control"
/**
 * The rail slot was a disabled button reading "Settings arrives with the write path" for as
 * long as no screen existed. The screen exists now and is read-only, so the note says which of
 * those two things is true rather than continuing to promise the other.
 */
const SETTINGS_NOTE = "Settings — read-only until the write path lands"

const SETTINGS = DESTINATIONS.find((entry) => entry.path === "/settings")!

function RailItem({
  area,
  active,
  onSelect,
}: {
  area: AreaEntry
  active: boolean
  onSelect: (id: Area) => void
}) {
  const Icon = AREA_ICON[area.id]
  const className = cn(
    RAIL_ITEM,
    active
      ? "bg-surface-emphasis text-foreground"
      : "text-graphics hover:bg-surface-subtle hover:text-foreground"
  )
  const mark = <Icon aria-hidden="true" className="size-5" />

  return (
    <li>
      <Tooltip>
        <TooltipTrigger asChild>
          {area.landing === null ? (
            <button
              type="button"
              aria-label={area.label}
              aria-current={active ? "true" : undefined}
              onClick={() => onSelect(area.id)}
              className={className}
            >
              {mark}
            </button>
          ) : (
            <Link
              to={area.landing}
              aria-label={area.label}
              aria-current={active ? "true" : undefined}
              className={className}
            >
              {mark}
            </Link>
          )}
        </TooltipTrigger>
        <TooltipContent side="right">{area.label}</TooltipContent>
      </Tooltip>
    </li>
  )
}

function AreaRail({
  activeId,
  onSelect,
}: {
  activeId: Area
  onSelect: (id: Area) => void
}) {
  const { state, setOpen } = useSidebar()

  return (
    <nav
      aria-label="Areas"
      data-state={state}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      className="sticky top-12 flex h-[calc(100vh-3rem)] w-10 shrink-0 flex-col border-r border-line bg-sidebar py-row"
    >
      <ul className="flex flex-1 flex-col items-center gap-field">
        {AREAS.map((area) => (
          <RailItem
            key={area.id}
            area={area}
            active={area.id === activeId}
            onSelect={onSelect}
          />
        ))}
        <li className="mt-auto">
          <Tooltip>
            <TooltipTrigger asChild>
              <NavLink
                to={SETTINGS.path}
                aria-label={SETTINGS.label}
                title={SETTINGS_NOTE}
                className={({ isActive }) =>
                  cn(RAIL_ITEM, isActive ? "bg-surface-subtle text-foreground" : "text-graphics")
                }
              >
                <Settings aria-hidden="true" className="size-5" />
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">{SETTINGS_NOTE}</TooltipContent>
          </Tooltip>
        </li>
      </ul>
    </nav>
  )
}

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

function ContextualSidebar({ area, pathname }: { area: AreaEntry; pathname: string }) {
  const bound = boundParams(pathname)

  return (
    <Sidebar
      collapsible="none"
      className="sticky top-12 h-[calc(100vh-3rem)] shrink-0 border-r border-line bg-sidebar"
    >
      <nav aria-label="Destinations" className="flex min-h-0 flex-1 flex-col">
        <SidebarHeader className="gap-field px-row py-section">
          <div className="flex items-baseline gap-field pb-field border-b border-line mb-field">
            <span className="font-semibold text-base tracking-tight text-foreground">sync</span>
            <span className="font-semibold text-base text-emerald-400">.</span>
            <span className="ml-auto font-mono text-meta uppercase tracking-wider text-muted-foreground">console</span>
          </div>
          <h2 className="text-emphasis text-foreground">{area.label}</h2>
          <p className="text-meta text-ink-muted">{area.purpose}</p>
        </SidebarHeader>
        <SidebarContent>
          {area.levels.map((level) => (
            <LevelGroup key={level} level={level} pathname={pathname} bound={bound} />
          ))}
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

  const [picked, setPicked] = useState<{ id: Area; at: string } | null>(null)
  if (picked !== null && picked.at !== pathname) setPicked(null)

  const activeId = picked !== null && picked.at === pathname ? picked.id : areaForPathname(pathname)
  const area = AREAS.find((entry) => entry.id === activeId) ?? AREAS[0]

  return (
    <CommandPaletteProvider>
      <div className="flex min-h-svh flex-col bg-background text-foreground">
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

        <SidebarProvider defaultOpen={false} className="min-h-0 flex-1 items-start">
          <AreaRail activeId={activeId} onSelect={(id) => setPicked({ id, at: pathname })} />
          <ContextualSidebar area={area} pathname={pathname} />

          <div className="flex min-w-0 flex-1 flex-col">
            <main ref={contentRef} tabIndex={-1} className="flex flex-1 flex-col gap-8 p-frame outline-none">
              <Outlet />
            </main>
          </div>
        </SidebarProvider>
      </div>
    </CommandPaletteProvider>
  )
}
