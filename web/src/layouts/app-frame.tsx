/**
 * The frame every level renders inside: one sidebar at two widths, and the content beside it.
 *
 * **Corrected 2026-08-06 by the owner, and the correction is the reason this file reads the way it
 * does.** The first version of this chassis built a fixed 56px icon rail of four product areas plus a
 * separate 240px contextual panel holding that area's destinations, and collapsing removed the panel.
 * That is Supabase's arrangement — two components — and it is the specific shape the owner ruled
 * against: *"the sidebar is not two different components it should be the sidebar expanding to that
 * width of that extra information and then minimizing to that thin width."*
 * `references/direction/NOTES.md` entry 6 carries both states side by side.
 *
 * Two things made it the wrong shape rather than merely a different one. Collapsed, the console lost
 * its destinations: four area icons remained and the nine specification levels were unreachable
 * without expanding, so the collapse traded navigation for width instead of changing density. And
 * expanding produced two columns of chrome, 56 + 240px, which is what made the content cost fixed
 * rather than tunable.
 *
 * **So: one sidebar, one list, two widths.** Every destination is a row at both widths, in the same
 * order, with the same icon. Expanded the row carries its label; collapsed the label goes and the
 * icon does not move. The four areas are no longer a navigation level — they are the group headings
 * that divide the one list, which is also the right shape for us rather than only the owner's
 * preference: Sync has nine levels in one hierarchy, not a set of independent products each owning a
 * sub-navigation, so a contextual second panel would have had nothing distinct to hold.
 *
 * **How the icons are kept in place, which is the whole test.** A group heading occupies a row of its
 * own when expanded. If nothing occupied it when collapsed, every icon below would move up and this
 * would be two layouts rather than one at two widths. The heading's row is therefore **reserved**: the
 * `<li>` keeps its height in both states and only its text becomes `sr-only`, which is
 * absolutely-positioned and so contributes no layout. That is the option NOTES entry 6's collapsed
 * reference also takes — "the same gap between clusters where a heading used to be" — and it is the
 * one that keeps the group announced to a screen reader at both widths. The alternative, making the
 * heading occupy no vertical space in either state, would have meant no visible grouping expanded,
 * which is the thing the grouping is for.
 *
 * **Where the two sentences went, and this is a real change rather than a tidy-up.** `area.purpose`
 * and `reachedFrom` were rows of prose in the panel. Prose cannot be a row here: a sentence that
 * renders expanded and not collapsed changes the height of the row above every icon beneath it, which
 * is exactly the failure this shape exists to prevent. Both survive as the row's `title` and
 * accessible name, identical at both widths — the same mechanism `provenance.tsx` already uses to
 * carry `describeRung` on a badge that is monochrome on screen. Neither is one of the twenty-four
 * protected sentences; both were added by this item's first dispatch.
 */

import { useState } from "react"
import {
  FileWarning,
  FolderTree,
  GitPullRequest,
  Layers,
  PanelLeftClose,
  PanelLeftOpen,
  Plug,
  Radar,
  Radio,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react"
import { Link, Outlet, matchPath, useLocation } from "react-router"

import { ErrorSurface } from "@/components/error-surface"
import { CommandPalette } from "@/layouts/command-palette"
import { AREAS, ROUTES, type AreaEntry, type RouteEntry } from "@/lib/routes"
import { cn } from "@/lib/utils"

/**
 * One icon per destination, keyed by route path.
 *
 * Kept here rather than in `routes.ts` because that registry is pinned by two Python tests and a
 * vitest file and has no business importing a React component. `lucide-react` is already the
 * console's icon source — `DESIGN.md` names it in the rule that a status colour never travels without
 * an icon and a word — and a generic icon set is not somebody else's iconography.
 *
 * Keyed by path rather than by level so a second route at one level gets its own mark: the sidebar
 * renders destinations, and two destinations sharing an icon would be two rows a collapsed reader
 * cannot tell apart, which is the one thing the collapsed state must not do.
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

/** Every row is this tall at both widths, which is what keeps an icon where it was. */
const ROW = "flex h-9 items-center gap-row rounded-control px-row"

function DestinationRow({
  route,
  collapsed,
  current,
}: {
  route: RouteEntry
  collapsed: boolean
  current: boolean
}) {
  const Icon = DESTINATION_ICON[route.path] ?? Layers
  const needsSubject = route.params.length > 0
  // The accessible name and the tooltip are identical at both widths. Collapsed, they are the only
  // thing carrying the label; expanded, they carry the sentence the row has no room to print.
  const described = needsSubject
    ? `${route.label} — reached from ${route.reachedFrom}`
    : route.label

  const body = (
    <>
      <Icon aria-hidden="true" className="size-5 shrink-0" />
      {/* `sr-only` rather than conditional rendering: it is absolutely positioned, so the label
          leaves the layout without the row changing height and without the name leaving the
          accessibility tree. The text disappears visually, never semantically. */}
      <span className={cn("min-w-0 truncate text-body", collapsed && "sr-only")}>
        {route.label}
      </span>
    </>
  )

  if (needsSubject) {
    // Not a link, and deliberately not a disabled control either: there is nothing to activate, so
    // the row is text that says what it is. `reachedFrom` is how a reader learns where to go, which
    // the previous horizontal strip solved by omitting these seven routes entirely.
    return (
      <li>
        <span
          data-destination={route.path}
          title={described}
          aria-label={described}
          className={cn(ROW, "text-ink-muted")}
        >
          {body}
        </span>
      </li>
    )
  }

  return (
    <li>
      <Link
        to={route.path}
        data-destination={route.path}
        title={described}
        aria-label={described}
        aria-current={current ? "page" : undefined}
        className={cn(
          ROW,
          current
            ? "bg-surface-emphasis font-medium text-foreground"
            : "text-foreground hover:bg-surface-subtle"
        )}
      >
        {body}
      </Link>
    </li>
  )
}

function AreaGroup({
  area,
  collapsed,
  pathname,
}: {
  area: AreaEntry
  collapsed: boolean
  pathname: string
}) {
  const routes = ROUTES.filter((route) => area.levels.includes(route.level))

  return (
    <>
      {/* The reserved row. `h-9` in both states, matching a destination row, so collapsing takes
          nothing out of the flow above the icons beneath it. `area.purpose` rides the title because a
          second line of prose here would be a row that exists expanded and not collapsed. */}
      <li className="flex h-9 items-end px-row" title={area.purpose}>
        <span className={cn("furniture text-meta text-ink-muted", collapsed && "sr-only")}>
          {area.label}
        </span>
      </li>
      {routes.map((route) => (
        <DestinationRow
          key={route.path}
          route={route}
          collapsed={collapsed}
          current={matchPath({ path: route.path, end: true }, pathname) !== null}
        />
      ))}
    </>
  )
}

export function AppFrame() {
  const { pathname } = useLocation()
  // Expanded only where expanding costs nothing, and 1473 is that width rather than a round number.
  // Measured on the binding surface — nine columns, the console's densest screen — at `--scale 10000`:
  // its rows are 77px until the content box reaches 1170px and 57px from there on, and the frame plus
  // an expanded sidebar plus a scrollbar take 303px, so 1473 is the narrowest viewport at which the
  // labels do not cost 20px on every row. B115 in `docs/superpowers/BACKLOG.md` carries the
  // measurement and the four configurations behind it. An earlier `< 1440` expanded at exactly 1440,
  // where expanding does cost that 20px.
  //
  // Read once at mount rather than through a resize listener: an operator who has collapsed the
  // sidebar has said what they want, and a window drag must not overrule them.
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 1473
  )

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <ErrorSurface />
      <CommandPalette />

      <nav
        aria-label="Console navigation"
        className={cn(
          // `sticky` with `h-screen`, not a full-height static column. Measured on `/detectors` at
          // 1440×900: the document is 2730px tall, and a static sidebar is 2730px tall with it — a
          // persistent navigation that leaves the screen after one scroll is not persistent.
          // `overflow-y-auto` is for the viewport short enough that nine rows plus four headings do
          // not fit, where the alternative is destinations that cannot be reached at all.
          "sticky top-0 flex h-screen shrink-0 flex-col gap-row overflow-y-auto border-r border-line bg-surface py-section",
          collapsed ? "w-12 px-field" : "w-52 px-row"
        )}
      >
        <button
          type="button"
          aria-expanded={!collapsed}
          title={collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
          onClick={() => setCollapsed((shut) => !shut)}
          className={cn(ROW, "text-ink-muted hover:bg-surface-subtle hover:text-foreground")}
        >
          {collapsed ? (
            <PanelLeftOpen aria-hidden="true" className="size-5 shrink-0" />
          ) : (
            <PanelLeftClose aria-hidden="true" className="size-5 shrink-0" />
          )}
          <span className="sr-only">
            {collapsed ? "Expand the sidebar" : "Collapse the sidebar"}
          </span>
        </button>

        <ul className="flex flex-col">
          {AREAS.map((area) => (
            <AreaGroup key={area.id} area={area} collapsed={collapsed} pathname={pathname} />
          ))}
        </ul>
      </nav>

      {/* `min-w-0` is what lets a nine-column table shrink instead of pushing the sidebar off the
          viewport: a flex child defaults to its content's minimum width, and a table's is the sum of
          its columns. Without it, collapsing would be the only way to read the binding surface, which
          is the opposite of what the collapse is for. */}
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
