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
  ScanSearch,
  ScrollText,
  Settings,
  Workflow,
  Wrench,
  PanelLeft,
  type LucideIcon,
} from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { Link, NavLink, Outlet, useLocation } from "react-router"

import { useRepositories } from "@/api/queries"
import { ErrorSurface } from "@/components/error-surface"
import { fetchSetup } from "@/features/settings/api"
import { CommandPaletteProvider, CommandPaletteTrigger } from "@/layouts/command-palette"
import { StatusTargetProvider, useStatusTarget } from "@/layouts/screen-frame"
import { ScopeTrail } from "@/layouts/scope-switchers"
import { STAGE_DOES } from "@/lib/stage-pages"
import { TopbarStatsProvider, TopbarStatsSlot } from "@/layouts/topbar-stats"
import {
  SIDEBAR_WIDTH,
  readPinned,
  writePinned,
} from "@/layouts/sidebar-collapse"
import {
  DESTINATIONS,
  ROUTES,
  WORKFLOW_STAGES,
  boundParams,
  destinationHref,
  isActiveMenuItem,
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
  "/repositories/:repoId/detectors": ScanSearch,
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
      {/* The current destination is marked twice over, which the design system asks for in as
          many words: *every status mark must include an icon and a label, colour is never the sole
          channel*. The emerald edge is the mark; `aria-current` below is the one a screen reader
          reads; and the row keeps its label. At rail width the edge still lands, so the current
          destination is legible with every name hidden. */}
      <SidebarMenuButton
        asChild
        isActive={current}
        className="h-9 rounded-control text-body data-[active=true]:bg-primary data-[active=true]:font-medium data-[active=true]:text-primary-foreground"
      >
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
  // The pin has a control again -- owner ruling 2026-08-25, from the Superlog reference: a
  // deliberate toggle on the wordmark row, so the rail is a state a reader chooses and stays in
  // rather than one a stray pointer keeps undoing. Hover-reveal survives underneath it for the
  // collapsed state, which is what makes the rail navigable without expanding it.
  const [pinned, setPinned] = useState(readPinned)
  const togglePinned = () => {
    setPinned((was) => {
      writePinned(!was)
      return !was
    })
  }
  const reserve = useRef<HTMLDivElement>(null)

  const state = pinned ? "expanded" : "minimised"
  const rail = state
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
      className="relative z-40 h-full shrink-0"
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
              className={cn(
                "flex h-12 shrink-0 items-center border-b border-line",
                minimised ? "justify-center px-0" : "gap-row px-section"
              )}
              title={workspace ?? undefined}
            >
              {/* At rail width the toggle is the whole row and centres in it; the wordmark is
                  absent rather than `sr-only`, because an invisible element still took the
                  width and pushed the button off centre -- which is the overlap the owner
                  reported on 2026-08-25. */}
              {!minimised && (
                <Link to="/" aria-label="Fleet" className="flex min-w-0 items-center gap-row">
                  <SyncMark className="size-5 shrink-0 text-foreground" />
                  <span className="font-semibold text-emphasis tracking-tight text-foreground">
                    Sync
                  </span>
                </Link>
              )}
              {/* The toggle the Superlog reference puts here. At rail width it is the only
                  control on the row, so it centres; expanded it sits at the far end. */}
              <button
                type="button"
                onClick={togglePinned}
                aria-label={pinned ? "Collapse the sidebar" : "Expand the sidebar"}
                aria-pressed={!pinned}
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-control text-graphics transition-colors hover:bg-surface-subtle hover:text-foreground focus:outline-none focus:ring-1 focus:ring-ring",
                  minimised ? "" : "ml-auto"
                )}
              >
                <PanelLeft aria-hidden="true" className="size-4" />
              </button>
            </div>
          </SidebarHeader>
          {/* No scrollbar — owner review item 3, and the compaction above is what makes it honest
              rather than a concealment. The list measures under the viewport at the console's
              1440×900 reference size, so at that size there is nothing to scroll and the chrome is
              absent because it is not needed. Below it the region still scrolls, silently: a clipped
              destination is unreachable and no route test would catch it, which is a worse fault
              than a scrollbar the owner did not want. */}
          <SidebarContent className="gap-0 pt-row overflow-y-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {/* One group per pipeline stage, in pipeline order — the owner's restructure of
              2026-08-19, superseding the flat list of 2026-08-18 and, before that, the ruling
              against headings altogether. What killed level headings was thirteen of them over
              eleven rows, several duplicating the row beneath; five stage words over nine
              differently-named rows is a different design, and `routes.test.tsx` holds the
              wording apart. The heading row stays in the DOM at the rail width with its text
              `sr-only`, exactly as the row labels do, so no icon moves across the reveal. */}
          {WORKFLOW_STAGES.map((stage, stageIndex) => {
            const rows = navRoutes().filter((route) => route.stage === stage)
            if (rows.length === 0) return null
            return (
              <SidebarGroup key={stage} className="px-row py-0">
                {/* The heading keeps its height at the rail width so no icon moves across the
                    reveal — but an invisible word left a 28px blank the owner read as broken
                    spacing, so the rail shows a centred hairline instead: the same group
                    boundary, drawn in the only channel a 48px column has. The first group
                    skips it, or it doubles the wordmark row's own hairline. */}
                <div
                  data-stage-heading={stage}
                  title={STAGE_DOES[stage]}
                  className="flex h-7 items-center px-row"
                >
                  <span className={minimised ? "sr-only" : "font-furniture text-ink-secondary"}>
                    {stage}
                  </span>
                  <span
                    aria-hidden="true"
                    className={
                      minimised && stageIndex > 0 ? "mx-auto h-px w-4 bg-line" : "hidden"
                    }
                  />
                </div>
                {/* `CI-W612` rendered `STAGE_DOES` as a sentence under every heading; the owner
                    ruled it back out on 2026-08-25 -- too much text for the rail, and the Stitch
                    references draw bare labelled items. The sentence survives as the heading's
                    `title`, so the vocabulary is one hover away rather than deleted. */}
                <SidebarGroupContent>
                  <SidebarMenu className="gap-0">
                    {rows.map((route) => (
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
          })}

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
    <div data-chassis-qualifications className="flex flex-col gap-field px-frame py-section">
      <p className="text-meta text-ink-muted leading-snug">
        Nine graph levels, five pipeline stages. A stage groups the pages that answer it — it is
        not a level itself.
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
    </div>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
  const { target, footerRef } = useStatusTarget()
  const [statsTarget, setStatsTarget] = useState<HTMLElement | null>(null)
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
        className="flex h-full overflow-hidden bg-background text-foreground"
      >
        <AppSidebar pathname={pathname} />

        <StatusTargetProvider target={target}>
        <TopbarStatsProvider target={statsTarget}>
        <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden">
          <ErrorSurface />

          {/* The identity band. The trail was pulled in 2026-08 because it and the sidebar were two
              navigation systems that could disagree about what "Overview" meant; it returns because
              it derives every segment from `useLocation()`, so it restates the address rather than
              holding an opinion about it. It renders before any query resolves -- a bar that waits
              on `/api/overview` to say where you are says nothing on the slowest navigation, which
              is when a reader needs it most. */}
          <header
            role="banner"
            className="z-30 flex h-12 shrink-0 items-center justify-between gap-section border-b border-line bg-secondary px-section"
          >
            <div className="flex min-w-0 flex-1 items-center gap-section">
              <ScopeTrail />
            </div>
            <CommandPaletteTrigger />
          </header>

          {/* The page's own figures, published here by every screen's KPI strip and the
              pipeline (owner rulings 2026-08-25): a second chrome row at the top bar's own
              height, not a shared corner -- and gone entirely (`empty:hidden`) on a screen
              that publishes nothing, because an empty bar is dead chrome. The workspace
              identity that used to hold this ground is Settings work now. */}
          <TopbarStatsSlot onTarget={setStatsTarget} />

          {/* The routed screen renders inside a centred column capped at 1400px — a page-layout
              number, argued here and spelled in layouts/ per DESIGN.md's own rule for those. At
              the 1440×900 reference size the cap never engages (1440 − 240 sidebar − 80 frame
              = 1120), so nothing measured changes; on a wide monitor it stops every page hugging
              the sidebar with dead space to the right, which reads as a misaligned screen rather
              than a large one. `w-full` keeps narrow viewports exactly as they were. */}
          <main
            ref={contentRef}
            tabIndex={-1}
            data-scrollport
            className="flex min-h-0 flex-1 flex-col overflow-auto outline-none has-[[data-screen=locked]]:overflow-hidden"
          >
            {/* The cap keeps a prose line readable, which is right for a screen of panels and
                wrong for one whose subject is fifteen recorded fields per row -- a table-first
                route declares itself wide in the registry and gets the window (M15 Task 1). A
                flag read here rather than a full-bleed hack in the page: negative margins fight
                the scrollbar and land differently per browser. */}
            <div
              className={cn(
                // `min-h-0` ONLY for a bounded screen. On a flowing one it clamps this box to
                // the viewport, so content past the fold is clipped rather than scrolled -- the
                // regression the owner reported: 986px of content held at 869px, 117px of scroll,
                // the rest unreachable. `flex-1` stays either way so a short page still pushes
                // the footer down.
                "mx-auto flex w-full flex-1 flex-col gap-8 p-frame",
                "has-[[data-screen=locked]]:min-h-0 has-[[data-screen=fill]]:min-h-0",
                // Full width, every route. Owner ruling 2026-08-25: 1920 is the standard this
                // console is operated at, and a 1400px column left 520px of dead page beside a
                // table that wanted it. `isWideRoute` is now the whole set.
                "max-w-none",
              )}
            >
              <Outlet />
            </div>
          </main>

          {/* The status band is a sibling of `main`, not a child: `app-frame.test.tsx` pins
              `banner.parentElement` to be the element that also holds `main`, and the sidebar has
              to stay outside that column. A screen therefore cannot render its own status inline
              -- `ScreenFrame` portals into the target below. An unmigrated screen portals nothing
              and the footer is the chassis sentences alone, exactly as before. */}
          <footer className="flex shrink-0 flex-col border-t border-line">
            <div ref={footerRef} />
            <ChassisQualifications />
          </footer>
        </div>
        </TopbarStatsProvider>
        </StatusTargetProvider>
      </SidebarProvider>
    </CommandPaletteProvider>
  )
}