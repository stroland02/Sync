/**
 * The frame every level renders inside: a fixed icon rail, a contextual sidebar, and the content.
 */

import { useState } from "react"
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
import { Link, Outlet, useLocation } from "react-router"

import { ErrorSurface } from "@/components/error-surface"
import { CommandPaletteProvider, CommandPaletteTrigger } from "@/layouts/command-palette"
import { ScopeTrail } from "@/layouts/scope-switchers"
import {
  AREAS,
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
const SETTINGS_NOTE = "Settings arrives with the write path"

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
              <button
                type="button"
                aria-disabled="true"
                aria-label="Settings"
                title={SETTINGS_NOTE}
                className={cn(RAIL_ITEM, "cursor-not-allowed text-graphics")}
              >
                <Settings aria-hidden="true" className="size-5" />
              </button>
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
        <div className="mt-auto border-t border-line px-row py-field">
          <p className="text-meta text-ink-muted leading-snug">
            Nine graph levels, six areas. An area groups a run of levels — it is not a level itself.
          </p>
        </div>
      </nav>
    </Sidebar>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
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
            <main className="flex flex-1 flex-col gap-8 p-frame">
              <Outlet />
            </main>
          </div>
        </SidebarProvider>
      </div>
    </CommandPaletteProvider>
  )
}
