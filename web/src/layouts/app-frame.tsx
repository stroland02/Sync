/**
 * The frame every level renders inside: one full-height sidebar, and the content column beside it.
 */

import { useEffect, useRef, useState } from "react"
import {
  ChartLine,
  CircleUserRound,
  Code2,
  FileWarning,
  FolderTree,
  GitPullRequest,
  Layers,
  Plug,
  Radar,
  Radio,
  ScrollText,
  Settings,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Link, NavLink, Outlet, useLocation } from "react-router"

import { useRepositories } from "@/api/queries"
import { WorkspaceSwitcher } from "@/layouts/workspace-switcher"
import { ErrorSurface } from "@/components/error-surface"
import { fetchSetup } from "@/features/settings/api"
import { CommandPaletteProvider, CommandPaletteTrigger } from "@/layouts/command-palette"
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
  isWideRoute,
  type RouteEntry,
} from "@/lib/routes"
import {
  activeWorkspace,
  rememberWorkspace,
  rememberedWorkspace,
} from "@/layouts/active-workspace"
import { cn } from "@/lib/utils"
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
  "/repositories/:repoId": Radar,
  "/repositories/:repoId/call-sites": Code2,
  "/repositories/:repoId/runs": ScrollText,
  "/repositories/:repoId/metrics": ChartLine,
  "/repositories/:repoId/solutions": GitPullRequest,
  "/repositories/:repoId/findings": FileWarning,
  "/repositories/:repoId/services": Plug,
  "/repositories/:repoId/vendors": FolderTree,
  "/repositories/:repoId/observed": Radio,
  "/repositories/:repoId/detectors": FileWarning,
  "/repositories/:repoId/vendors/:vendorId": Plug,
  "/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId": Layers,
  "/repositories/:repoId/findings/:findingId": Wrench,
  "/repositories/:repoId/findings/:findingId/workflow": Workflow,
  "/repositories/:repoId/findings/:findingId/workflow/pull-request": GitPullRequest,
}

/**
 * The rail slot was a disabled button reading "Settings arrives with the write path" for as
 * long as no screen existed, then a note calling the screen read-only for as long as that was
 * true. The write path landed 2026-08-18 — merge policy, merge method and base branch store
 * and save — so the note says what is editable and names the one thing that never will be.
 */
export const SETTINGS_NOTE =
  "Settings — automation policy is editable; the codebase's own context file is shown, never written"

/** Where a row goes when its own subject is not bound: the screen a codebase is selected on. */
const SUBJECT_PICKER = "/"

/**
 * The Sync logomark: two arcs closing a loop between two terminal nodes — the product in one
 * shape, a graph kept in sync. Drawn here rather than shipped as an asset: it is ours
 * (`interface-originality.md`), it is one path set, and `currentColor` keeps it on the
 * palette's own ink at every size.
 */
function SyncMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className={className}>
      <g fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
        <path d="M19.5 8.5A8.2 8.2 0 0 0 5.2 7.1" />
        <path d="M4.5 15.5a8.2 8.2 0 0 0 14.3 1.4" />
      </g>
      <circle cx="12" cy="12" r="2.2" fill="currentColor" />
      <circle cx="4.6" cy="7.4" r="1.6" fill="currentColor" />
      <circle cx="19.4" cy="16.6" r="1.6" fill="currentColor" />
    </svg>
  )
}

/**
 * The identity facts both sides of the chassis render: which workspace, and who the forge
 * credential speaks as. One hook so the sidebar's account row and the top bar's environment
 * badge cannot disagree — the query key is shared and cached well past the navigation rate,
 * because the server side shells out to `gh` for it.
 */
function useChassisIdentity(pathname: string) {
  const routeBound = boundParams(pathname)
  const repositories = useRepositories()
  const repoIds = repositories.data?.repo_ids ?? []
  // The chassis stays attached on screens that name no workspace -- Settings is a destination
  // rather than a level, so it binds no `repoId`, and reading the route alone blanked the badge
  // and made every repository-scoped rail row unlinkable there (owner report, 2026-08-19).
  // `active-workspace.ts` owns the rule and its test; the address always wins.
  const active = activeWorkspace(routeBound.repoId, rememberedWorkspace(), repoIds)
  const bound = active !== null ? { ...routeBound, repoId: active } : routeBound

  // Remember only what the address itself named. Persisting the inherited value would let a
  // fallback promote itself into a choice the reader never made.
  useEffect(() => {
    if (routeBound.repoId !== undefined) rememberWorkspace(routeBound.repoId)
  }, [routeBound.repoId])
  const setupQuery = useQuery({
    queryKey: ["setup", "chassis"],
    queryFn: ({ signal }) => fetchSetup(null, signal),
    staleTime: 5 * 60_000,
  })
  return {
    bound,
    workspace: bound.repoId ?? null,
    forgeLogin: setupQuery.data?.operator.forge_login ?? null,
    pending: setupQuery.isPending,
  }
}

/**
 * The environment, in the cross's top-right quadrant by the owner's direction: the workspace's
 * git name, the deployment, and the forge credential, as one truncating link into Connections.
 */
function EnvironmentBadge() {
  const { pathname } = useLocation()
  const { workspace, forgeLogin, pending } = useChassisIdentity(pathname)
  return (
    // No longer a link into Settings. Pressing the text a reader takes for the codebase name
    // navigated them to a different screen entirely (owner report, 2026-08-19); the badge is the
    // switcher now, and Settings is reachable from the rail where it always was.
    <WorkspaceSwitcher current={workspace}>
      {workspace !== null && (
        <>
          <span className="min-w-0 truncate font-mono text-ink" title={workspace}>
            {workspace}
          </span>
          <span aria-hidden="true">·</span>
        </>
      )}
      <span className="shrink-0">local dev</span>
      <span aria-hidden="true">·</span>
      <span className="shrink-0">
        {pending ? "git: asking…" : forgeLogin !== null ? `git: ${forgeLogin}` : "git: not connected"}
      </span>
    </WorkspaceSwitcher>
  )
}



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
 * The destinations a selected workspace can reach, in registry order.
 *
 * **One region, because one region is what the data supports.** The rail used to draw `root` and
 * `repository` groups, and they overlapped by name -- Codebases against Codebase, Vendor against
 * Vendors -- which is the duplication the owner saw. Every page is a workspace's page now.
 *
 * `nav` decides membership rather than a parameter count: a route needing a vendor, an operation or
 * a finding cannot be built from the selected workspace alone, so it is reached from the page that
 * holds its subject and is absent here. Absent is honest; present and inert reads as broken.
 */
export function navRoutes(): RouteEntry[] {
  // The owner's reading order, 2026-08-18, held by `navOrder` rather than by registry
  // position — the rail stopped grouping by level, so its order is a declared product
  // decision and an entry without one sorts last, loudly at the bottom rather than lost.
  return ROUTES.filter((route) => route.nav).sort(
    (a, b) => (a.navOrder ?? Number.MAX_SAFE_INTEGER) - (b.navOrder ?? Number.MAX_SAFE_INTEGER),
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
  // The install story: this console is set up beside one codebase, so when the graph holds
  // exactly one repository the sidebar binds every destination through it rather than sending
  // unbound rows to the picker — a reader is never asked to choose among one. Several
  // repositories keep the picker, because choosing among several is the operator's act, and
  // an unanswered repositories query binds nothing rather than guessing.
  const { bound, workspace, forgeLogin, pending: identityPending } = useChassisIdentity(pathname)
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
          {/* The top-left cell of the cross: the logomark alone, at exactly the top bar's 48px,
              closed by the shared hairline. The environment moved to the cross's top-right (the
              top bar) on the owner's direction, so nothing here ever shifts the rows below. */}
          <SidebarHeader className="gap-0 p-0">
            <div
              className="flex h-12 shrink-0 items-center gap-row border-b border-line px-section"
              title={workspace ?? undefined}
            >
              <SyncMark className="size-5 shrink-0 text-foreground" />
              <span
                className={
                  minimised
                    ? "sr-only"
                    : "font-semibold text-emphasis tracking-tight text-foreground"
                }
              >
                Sync
              </span>
            </div>
          </SidebarHeader>
          {/* No scrollbar — owner review item 3, and the compaction above is what makes it honest
              rather than a concealment. The list measures under the viewport at the console's
              1440×900 reference size, so at that size there is nothing to scroll and the chrome is
              absent because it is not needed. Below it the region still scrolls, silently: a clipped
              destination is unreachable and no route test would catch it, which is a worse fault
              than a scrollbar the owner did not want. */}
          <SidebarContent className="gap-0 pt-row overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {/* One flat set in the owner's declared order. The workspace is chosen above;
              everything here is that workspace's. */}
          <SidebarGroup className="px-row py-0">
            <SidebarGroupContent>
              <SidebarMenu className="gap-0">
                {navRoutes().map((route) => (
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

          </SidebarContent>

          {/* The pinned bottom utility bar the sidebar brief named and nothing had built: the
              account bottom-left by the owner's direction, and Settings beside it — `DESTINATIONS`
              sits at no graph level, so the level groups above never render it, and removing it
              here would remove the only way to reach it while every routing test stayed green.
              The account is the forge login, because that is the only identity a single-operator
              local deployment honestly holds; a deployment without one says so rather than
              inventing a name. */}
          <div className="flex flex-col gap-0 border-t border-line px-row py-row">
            <SidebarMenu className="gap-0">
              {/* Identity, not navigation: there is no account page, so this row does not
                  pretend to open one — the owner caught it landing on the same screen as
                  Settings. It states who the forge credential speaks as, at the exact metrics
                  of the rows around it so the column stays one grid. */}
              <div
                className="flex h-7 items-center gap-row px-row"
                title={
                  forgeLogin !== null
                    ? `Signed in to the forge as ${forgeLogin}`
                    : "No forge account connected"
                }
              >
                <CircleUserRound aria-hidden="true" className="size-4 shrink-0 text-graphics" />
                <span
                  className={
                    minimised ? "sr-only" : "min-w-0 truncate font-mono text-meta text-ink-muted"
                  }
                >
                  {identityPending ? "asking…" : (forgeLogin ?? "no forge account")}
                </span>
              </div>
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
          </div>
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

          {/* The scope trail is removed for now on the owner's direction — it and the sidebar
              were two navigation systems disagreeing about what "Overview" meant, and the
              redesign that replaces it starts from the new workflows rather than patching the
              old trail. The bar keeps its height and hairline so the chassis line stays
              continuous with the sidebar's wordmark row. */}
          <header
            role="banner"
            className="sticky top-0 z-30 flex h-12 shrink-0 items-center justify-between gap-section border-b border-line bg-background px-section"
          >
            <div className="flex min-w-0 flex-1 items-center">
              <EnvironmentBadge />
            </div>
            <CommandPaletteTrigger />
          </header>

          {/* The routed screen renders inside a centred column capped at 1400px — a page-layout
              number, argued here and spelled in layouts/ per DESIGN.md's own rule for those. At
              the 1440×900 reference size the cap never engages (1440 − 240 sidebar − 80 frame
              = 1120), so nothing measured changes; on a wide monitor it stops every page hugging
              the sidebar with dead space to the right, which reads as a misaligned screen rather
              than a large one. `w-full` keeps narrow viewports exactly as they were. */}
          <main ref={contentRef} tabIndex={-1} className="flex flex-1 flex-col outline-none">
            {/* The cap keeps a prose line readable, which is right for a screen of panels and
                wrong for one whose subject is fifteen recorded fields per row -- a table-first
                route declares itself wide in the registry and gets the window (M15 Task 1). A
                flag read here rather than a full-bleed hack in the page: negative margins fight
                the scrollbar and land differently per browser. */}
            <div
              className={cn(
                "mx-auto flex w-full flex-1 flex-col gap-8 p-frame",
                isWideRoute(pathname) ? "max-w-none" : "max-w-[1400px]",
              )}
            >
              <Outlet />
            </div>
          </main>

          <ChassisQualifications />
        </div>
      </SidebarProvider>
    </CommandPaletteProvider>
  )
}