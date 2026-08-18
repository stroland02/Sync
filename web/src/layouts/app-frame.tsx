/**
 * The frame every level renders inside: one full-height sidebar, and the content column beside it.
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
  SIDEBAR_WIDTH,
  railState,
  readPinned,
  sidebarState,
} from "@/layouts/sidebar-collapse"
import {
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

/** Where a row goes when its own subject is not bound: the screen a codebase is selected on. */
const SUBJECT_PICKER = "/"



function DestinationRow({
  route,
  pathname,
  bound,
  minimised,
}: {
  route: RouteEntry
  pathname: string
  bound: Record<string, string>
  minimised: boolean
}) {
  const Icon = DESTINATION_ICON[route.path] ?? Layers
  const current = isActiveMenuItem(route, pathname)
  const bound_href = destinationHref(route, bound)
  // **Never null, and never a span.** Nine of twelve routes need a bound parameter, so
  // `destinationHref` answers null for most of the sidebar most of the time. That used to render a
  // <span> styled as a row: it looked pressable, absorbed the click and did nothing, which is the
  // worse half of the failure the owner named -- a control that vanishes is honest, one that eats
  // the press reads as broken.
  //
  // Where the subject is missing, the row goes to where a subject is chosen. The codebase is the
  // independent variable, so that is the Overview; the row's accessible name still says what it is
  // reached from, so the reader learns why they were taken there rather than being dropped.
  const href = bound_href ?? SUBJECT_PICKER
  const described =
    bound_href === null && route.reachedFrom !== null
      ? `${route.label} — reached from ${route.reachedFrom}`
      : route.label
  const body = (
    <>
      <Icon aria-hidden="true" />
      <span className={minimised ? "sr-only" : undefined}>{route.label}</span>
    </>
  )

  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={current} className="h-7 text-body">
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

/**
 * The two regions the sidebar draws, in the order it draws them.
 *
 * Six areas became two because the repository is the independent variable: a screen is either
 * scoped to one repository or it is not. The labels say which, plainly, and they are honest while
 * no repository is selected — nothing here claims a repository has been chosen.
 */
const REGIONS = [
  { id: "root", label: "Across all repositories" },
  { id: "repository", label: "Within a repository" },
] as const

/** The graph levels present in one region, in registry order, without repeats. */
function levelsIn(region: RouteEntry["region"]): GraphLevel[] {
  const seen: GraphLevel[] = []
  for (const route of ROUTES) {
    if (route.region === region && !seen.includes(route.level)) seen.push(route.level)
  }
  return seen
}

function LevelGroup({
  level,
  region,
  pathname,
  bound,
  minimised,
}: {
  level: GraphLevel
  region: RouteEntry["region"]
  pathname: string
  bound: Record<string, string>
  minimised: boolean
}) {
  const routes = ROUTES.filter((route) => route.level === level && route.region === region)
  if (routes.length === 0) return null

  return (
    <SidebarGroup className="px-row py-0">
      <SidebarGroupContent>
        <SidebarMenu className="gap-0">
          {routes.map((route) => (
            <DestinationRow
              key={route.path}
              route={route}
              pathname={pathname}
              bound={bound}
              minimised={minimised}
            />
          ))}
        </SidebarMenu>
      </SidebarGroupContent>
    </SidebarGroup>
  )
}

/**
 * A group heading that keeps its row when the sidebar is minimised.
 *
 * **This is what stops every icon beneath it moving.** A heading removed at the narrow width
 * shortens the column and drags each row below it upward, which is the defect `M7-W160` named and
 * the reason its predecessor was deleted. The row keeps its height and only the text stops being
 * visible — `sr-only` rather than `hidden`, so a screen reader still hears the grouping it needs
 * most when the labels are gone.
 */
function GroupHeading({ label, minimised }: { label: string; minimised: boolean }) {
  return (
    <p className="furniture flex h-5 items-center px-row text-meta text-ink-muted">
      <span className={minimised ? "sr-only" : undefined}>{label}</span>
    </p>
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
 *
 * **It loads as a rail and reveals itself under a pointer or a focus**, which the owner asked for
 * by name. The width is derived from three inputs rather than stored as one, and the stored one is
 * the pin: a reader who wants it held open says so and it stays. Reachability is unchanged at
 * either width — minimising changes density, not navigation — and the reveal is an overlay, so the
 * content column never moves under a pointer that was only passing through.
 */
function AppSidebar({ pathname }: { pathname: string }) {
  const bound = boundParams(pathname)
  // The pin is a stored preference with no control any more: the owner removed the button because
  // hovering is the mechanism, and two ways to open one panel is what made this hard to reason
  // about. It is still read, so a reader who set it before this change is not overruled by it, and
  // nothing in the frame can set it. If it is still unset by anything a week from now it should go.
  const pinned = readPinned()
  const [pointerInside, setPointerInside] = useState(false)
  const [focusInside, setFocusInside] = useState(false)
  const reserve = useRef<HTMLDivElement>(null)

  /**
   * The reveal, wired to native events rather than to React's synthetic ones.
   *
   * `pointerenter`/`pointerleave` and `focusin`/`focusout` are the four the browser actually fires
   * for "the pointer is over this box" and "something inside it holds focus". React reconstructs
   * the first pair from `pointerover`/`pointerout` and the second pair is what its `onFocus` is
   * already built on, so going to the DOM costs one effect and removes a layer of simulation from
   * the one interaction a reader performs on every pointer move.
   *
   * **`focusout` carries `relatedTarget`, and ignoring it is a bug rather than a simplification.**
   * Focus moving from one row to the next fires `focusout` before `focusin`, so an unconditional
   * collapse would shut the panel and reopen it on every arrow key.
   */
  useEffect(() => {
    const node = reserve.current
    if (node === null) return

    const enter = () => setPointerInside(true)
    const leave = () => setPointerInside(false)
    const focusIn = () => setFocusInside(true)
    const focusOut = (event: FocusEvent) => {
      if (event.relatedTarget instanceof Node && node.contains(event.relatedTarget)) return
      setFocusInside(false)
    }

    node.addEventListener("pointerenter", enter)
    node.addEventListener("pointerleave", leave)
    node.addEventListener("focusin", focusIn)
    node.addEventListener("focusout", focusOut)
    return () => {
      node.removeEventListener("pointerenter", enter)
      node.removeEventListener("pointerleave", leave)
      node.removeEventListener("focusin", focusIn)
      node.removeEventListener("focusout", focusOut)
    }
  }, [])

  const state = sidebarState({ pinned, pointerInside, focusInside })
  const rail = railState({ pinned, pointerInside, focusInside })
  const minimised = state === "minimised"


  return (
    // The box the content column gives up, and it is exactly the width the panel draws.
    //
    // **The panel does not overlay.** It did until the owner looked at the running console and
    // ruled against it: revealing over the page hid the heading, the leading column of every table
    // and the repository names under an opaque 240px panel laid over a page that had reserved 48px.
    // The argument for the overlay was that reflowing the column under a reader is worse than
    // covering it. Having seen both, the owner's answer is that it is not -- the sidebar pushes the
    // page and nothing is ever obscured.
    <div
      ref={reserve}
      data-sidebar-reserve={rail}
      style={{ width: SIDEBAR_WIDTH[rail] }}
      className="sticky top-0 z-40 h-svh shrink-0"
    >
      <Sidebar
        collapsible="none"
        style={{ width: SIDEBAR_WIDTH[state] }}
        data-state={state}
        className="absolute inset-y-0 left-0 overflow-hidden border-r border-line bg-sidebar"
      >
        <nav aria-label="Destinations" className="flex min-h-0 flex-1 flex-col">
          <SidebarHeader className="gap-0 px-row py-row">
            {/* One top row carrying the wordmark and the panel control together — owner review item
                4. It used to float below the header as its own row, which cost a row of height and
                put a chassis control inside the destination list. */}
            <div className="flex h-6 items-center gap-field border-b border-line pb-field">
              <span
                className={
                  minimised
                    ? "sr-only"
                    : "font-semibold text-emphasis tracking-tight text-foreground"
                }
              >
                sync
              </span>
              <span
                className={
                  minimised
                    ? "sr-only"
                    : "font-mono text-meta uppercase tracking-wider text-muted-foreground"
                }
              >
                console
              </span>
            </div>
          </SidebarHeader>
          {/* No scrollbar — owner review item 3, and the compaction above is what makes it honest
              rather than a concealment. The list measures under the viewport at the console's
              1440×900 reference size, so at that size there is nothing to scroll and the chrome is
              absent because it is not needed. Below it the region still scrolls, silently: a clipped
              destination is unreachable and no route test would catch it, which is a worse fault
              than a scrollbar the owner did not want. */}
          <SidebarContent className="gap-0 overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {REGIONS.map((region) => (
              <div key={region.id} className="flex flex-col">
                <GroupHeading label={region.label} minimised={minimised} />
                {levelsIn(region.id).map((level) => (
                  <LevelGroup
                    key={level}
                    level={level}
                    region={region.id}
                    pathname={pathname}
                    bound={bound}
                    minimised={minimised}
                  />
                ))}
              </div>
            ))}

            {/* `DESTINATIONS` is a separate registry from `ROUTES` and its entries sit at no graph
                level, so `LevelGroup` — which filters `ROUTES` by level — renders none of them. The
                rail carried Settings in a hard-coded slot; deleting the rail without this group would
                have removed the only way to reach it, while every routing test stayed green because
                the route still exists. */}
            <div className="flex flex-col">
              <GroupHeading label="Deployment" minimised={minimised} />
              <SidebarGroup className="px-row py-0">
                <SidebarGroupContent>
                  <SidebarMenu className="gap-0">
                    {DESTINATIONS.map((entry) => (
                      <SidebarMenuItem key={entry.path}>
                        <SidebarMenuButton
                          asChild
                          isActive={pathname === entry.path}
                          className="h-7 text-body"
                        >
                          <NavLink to={entry.path} title={SETTINGS_NOTE} aria-label={entry.label}>
                            <Settings aria-hidden="true" className="size-4 text-graphics" />
                            <span className={minimised ? "sr-only" : "text-body"}>{entry.label}</span>
                          </NavLink>
                        </SidebarMenuButton>
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            </div>
          </SidebarContent>
        </nav>
      </Sidebar>
    </div>
  )
}

/**
 * The two qualifications the chassis carries, and why they are no longer in the sidebar.
 *
 * Both are protected sentences (`.claude/rules/console-surface.md`), and they sat in the sidebar
 * footer under an argument that said so explicitly: hiding them at the narrow width was defensible
 * *because the sidebar defaulted to expanded*, so a reader who had chosen nothing saw them.
 * **Hover-expand takes that premise away.** An unpinned rail is the default now, and a sentence
 * that appears only when a pointer enters a 48px column is behind a disclosure whatever it is
 * called — which is the one thing that rule forbids doing to these.
 *
 * So they moved out rather than being restyled again. Nothing gates them here: no state, no
 * pointer, no control. Word for word as they were.
 */
function ChassisQualifications() {
  return (
    <footer className="mt-auto flex flex-col gap-field border-t border-line px-frame py-section">
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
        repository you do not recognise is one this deployment was configured to watch, not another
        customer's.
      </p>
    </footer>
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

          <ChassisQualifications />
        </div>
      </SidebarProvider>
    </CommandPaletteProvider>
  )
}
