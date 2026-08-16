/**
 * The frame every level renders inside: a fixed icon rail, a contextual sidebar, and the content.
 *
 * **Ruled by the owner on 2026-08-06, and it reverses the ruling this file used to carry.** The
 * chassis M7-W160 built was one sidebar at two widths with a collapse threshold, because an earlier
 * two-tier attempt had traded reachability for width: collapsed, four area icons remained and the
 * nine specification levels could not be reached at all. That was a defect in that attempt, not in
 * the arrangement, and the arrangement is what the console adopts now — Supabase's, described from
 * source in `docs/superpowers/references/notes/supabase-control-plane-mechanism.md` §1.
 *
 * **What makes the two tiers work is that only one of them moves.** The rail is the same six areas
 * in the same order on every route, so no icon travels under the pointer as an operator navigates;
 * the sidebar is the only thing that changes, and it changes to the destinations inside the area the
 * address is in. `app-frame.test.tsx` holds exactly that, because jsdom has no layout and the
 * sequence is the only place the property is visible.
 *
 * **Two pieces of Studio's shell are deliberately not inherited**, both named in that note: the
 * resizable panel group and the mount deferred behind an `isMounted` flag. They exist to stop a
 * second AI sidebar rendering at 50% and jumping. We have one sidebar at a fixed width, which needs
 * neither, and inheriting them would be machinery with nothing behind it.
 *
 * **An area with no landing route selects without navigating, and that is a real distinction rather
 * than a workaround.** Seven of nine destinations need a subject the registry does not hold — a
 * Solution Workflow exists *for* a finding — so four of the six areas have no address of their own.
 * Their rail item is a button that opens the area's sidebar, which is what makes those levels
 * discoverable before an operator has picked a subject. The pick is dropped the moment the address
 * changes, so a navigation always wins over a browse and the two can never disagree.
 *
 * `Settings` is on the rail and is not an area. No route declares it and the specification declares
 * no level for it; it renders `aria-disabled` with the sentence naming what it is waiting for, which
 * is cheaper than a level invented to give it somewhere to point.
 *
 * **The rail shows its labels while a pointer or the keyboard is on it (M7-W199).** It was 48px and
 * fixed, so six areas were six permanently unlabelled glyphs. The state machine underneath is the
 * vendored primitive's — `SidebarProvider`'s open state, `--sidebar-width` and
 * `--sidebar-width-icon`, `data-state` and `data-collapsible`, and `SidebarMenuButton`'s collapsed
 * geometry — and what this file adds is the pointer that drives it, which is exactly the layer
 * Studio adds it at. **No vendored file changes.** Three consequences are decisions rather than
 * details, and `docs/superpowers/briefs/2026-08-07-substrate-fidelity-task-5.md` argues each:
 *
 * - **The rail keeps its own positioned box** instead of rendering `<Sidebar collapsible="icon">`.
 *   That branch of the primitive positions its panel against a spacer that takes its height from a
 *   stretched flex parent; this chassis row is `items-start` with both tiers `sticky` at a
 *   viewport-derived height, where the same branch resolves to zero height. The contextual sidebar
 *   already takes `collapsible="none"` and supplies its own box for the same reason.
 * - **The expanded rail overlays what is beside it and never displaces it.** Growing in flow would
 *   push the sidebar and the whole content column 160px sideways every time a pointer crossed the
 *   rail.
 * - **The width is not animated.** `tests/test_console_design_tokens.py` bans geometry transitions,
 *   and `transition-[width]` would slip past its pattern while being the thing it exists to stop.
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
} from "@/vendor/supabase/ui/sidebar"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/vendor/supabase/ui/tooltip"

/**
 * One icon per destination, keyed by route path, and one per area.
 *
 * Kept here rather than in `routes.ts` because that registry is pinned by two Python tests and a
 * vitest file and has no business importing a React component. `lucide-react` is already the
 * console's icon source — `DESIGN.md` names it in the rule that a status colour never travels without
 * an icon and a word — and a generic icon set is not somebody else's iconography.
 *
 * Keyed by path rather than by level so a second route at one level gets its own mark. An area's
 * icon is the mark of the destination it opens onto, which is what makes the rail legible as the
 * levels rather than as six abstractions.
 */
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

/** Every rail control is this square, so the column reads as one grid rather than six controls. */
const RAIL_ITEM = "flex size-8 items-center justify-center rounded-control"

/**
 * Why the last item on the rail does not go anywhere.
 *
 * Declared once and rendered twice — as the entry's `title` and as its tooltip — because a Radix
 * tooltip is in the document only while it is open, and a sentence a reader can only reach by
 * hovering is a sentence most readers never reach.
 */
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
          {/* The tooltip supplements the name; `aria-label` supplies it. A rail whose only name is
              a tooltip is a column of unnamed controls to anything that does not hover. */}
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
  return (
    <nav
      aria-label="Areas"
      // `sticky` and one viewport tall, not a full-height static column. Every level here scrolls
      // well past one viewport, and a static rail is as tall as the document — a persistent
      // navigation that leaves the screen after one scroll is not persistent. The height is the
      // viewport less the bar above it, and `top-12` is that same bar: both tiers begin under it.
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
              {/* `aria-disabled` rather than `disabled`: a disabled button leaves the tab order, and
                  the sentence explaining the entry would then be reachable only by pointer. */}
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

function DestinationRow({ route, pathname }: { route: RouteEntry; pathname: string }) {
  const Icon = DESTINATION_ICON[route.path] ?? Layers
  const needsSubject = route.params.length > 0
  const current = isActiveMenuItem(route, pathname)
  const described = needsSubject
    ? `${route.label} — reached from ${route.reachedFrom}`
    : route.label
  const body = (
    <>
      <Icon aria-hidden="true" />
      <span>{route.label}</span>
    </>
  )

  if (needsSubject) {
    // Not a link, and deliberately not a disabled control either: there is nothing to activate, so
    // the row is text that says what it is. `reachedFrom` is how a reader learns where to go.
    // It still carries the current state, because seven of the nine destinations are this shape and
    // a sidebar that marked only the other two would fail to say where the operator is standing.
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
          to={route.path}
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

function LevelGroup({ level, pathname }: { level: GraphLevel; pathname: string }) {
  const routes = ROUTES.filter((route) => route.level === level)
  if (routes.length === 0) return null

  return (
    <SidebarGroup>
      {/* The group label is the specification's own level name in the furniture register. The
          sidebar prints the hierarchy rather than a second one of its own. */}
      <SidebarGroupLabel className="furniture text-meta text-ink-muted">{level}</SidebarGroupLabel>
      <SidebarGroupContent>
        <SidebarMenu>
          {routes.map((route) => (
            <DestinationRow key={route.path} route={route} pathname={pathname} />
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

function ContextualSidebar({ area, pathname }: { area: AreaEntry; pathname: string }) {
  return (
    <Sidebar
      collapsible="none"
      className="sticky top-12 h-[calc(100vh-3rem)] shrink-0 border-r border-line bg-sidebar"
    >
      <nav aria-label="Destinations" className="flex min-h-0 flex-1 flex-col">
        <SidebarHeader className="gap-field px-row py-section">
          <h2 className="text-emphasis text-foreground">{area.label}</h2>
          <p className="text-meta text-ink-muted">{area.purpose}</p>
        </SidebarHeader>
        <SidebarContent>
          {area.levels.map((level) => (
            <LevelGroup key={level} level={level} pathname={pathname} />
          ))}
        </SidebarContent>
      </nav>
    </Sidebar>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
  // A pick lasts exactly as long as the address it was made at, and it is **cleared** here rather
  // than merely ignored while the address differs. Ignoring it is not the same thing: the pick then
  // survives out of sight and revives the moment its own address comes back, so Back onto that
  // address would leave the rail marking one area while another area's screen renders beneath it.
  // Cleared during render rather than from an effect, which is React's own shape for resetting
  // state that a changing input has invalidated — no second commit, and nothing renders in between.
  const [picked, setPicked] = useState<{ id: Area; at: string } | null>(null)
  if (picked !== null && picked.at !== pathname) setPicked(null)

  const activeId = picked !== null && picked.at === pathname ? picked.id : areaForPathname(pathname)
  const area = AREAS.find((entry) => entry.id === activeId) ?? AREAS[0]

  return (
    <CommandPaletteProvider>
      <div className="flex min-h-svh flex-col bg-background text-foreground">
        {/* The banner slot. Above the header and in flow, so a failure pushes the console down
            rather than covering it — `components/error-surface.tsx` carries what that fixed. */}
        <ErrorSurface />

        <header
          role="banner"
          // Sticky, because the whole reason this exists is that the breadcrumb left the screen on
          // the first scroll. The two tiers below therefore start under it rather than at 0.
          className="sticky top-0 z-30 flex h-12 shrink-0 items-center justify-between gap-section border-b border-line bg-background px-section"
        >
          {/* `min-w-0` so the trail truncates inside its own box. Studio's header is
              `overflow-x-auto` and lets the current subject scroll off the side; ours holds it. */}
          <div className="flex min-w-0 flex-1 items-center">
            <ScopeTrail />
          </div>
          <CommandPaletteTrigger />
        </header>

        <SidebarProvider className="min-h-0 flex-1 items-start">
          <AreaRail activeId={activeId} onSelect={(id) => setPicked({ id, at: pathname })} />
          <ContextualSidebar area={area} pathname={pathname} />

          {/* `min-w-0` is what lets a nine-column table shrink instead of pushing the chassis off
              the viewport: a flex child defaults to its content's minimum width, and a table's is
              the sum of its columns. */}
          <div className="flex min-w-0 flex-1 flex-col">
            {/* No error boundary here. `App.tsx` puts one inside each routed screen instead, keyed
                by pathname — one out here survives navigation and turns a single crash into a
                console that stays crashed. */}
            <main className="flex flex-1 flex-col gap-8 p-frame">
              <Outlet />
            </main>
          </div>
        </SidebarProvider>
      </div>
    </CommandPaletteProvider>
  )
}
