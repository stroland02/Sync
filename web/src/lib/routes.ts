/**
 * The route registry: the single source of truth for every destination this console
 * declares. `App.tsx` builds its `<Route>` elements from this array, the persistent
 * navigation renders from it, and the command palette searches it. A route that is not an
 * entry here does not exist — delete an entry and the destination stops resolving in the
 * router, the navigation and the palette at once, because all three read the same array
 * rather than three copies of the same thirteen-file habit.
 *
 * `level` is the route's position in the API Dependency Graph, and `GRAPH_LEVELS` is not this
 * file's invention: `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:429-443`
 * is the authority, and `.claude/rules/console-hierarchy.md` is the rule that a level with no
 * line in that document does not belong in the array below. Reconciled 2026-08-05 after the
 * console shipped eleven routes against a hierarchy nobody had opened — three matched, four
 * were invented, two were reparented, three specified levels had never been built. The count
 * is nine now because the specification gained three levels that day (Fleet, Binding surface,
 * and the Signals/Errors & Incidents split already implied one more), not because this file
 * decided it needed more screens.
 *
 * Two placements worth recording here, because neither is settled by a single page's own
 * docstring:
 *
 * - `Binding surface` is its own level, a sibling of `Signals` under `API Services` — the
 *   specification's amended block draws it that way (`:437-438`), not as a sub-case of
 *   `API Services` the way this file used to file it.
 * - `Detector attribution` (`/detectors`) is deliberately *not* a level. It aggregates over
 *   `Errors & Incidents` the same way the old `/codebase` aggregated over `API Services` —
 *   the specification says so explicitly at `:445` — so it carries the `Errors & Incidents`
 *   level rather than one invented for it.
 *
 * `Signals` gained its third panel on 2026-08-06: `/repositories/:repoId/observed` now renders
 * all three M5 roles (vendor, signal source, human surface) instead of the signal-source-only
 * screen that used to sit under a stale "Observed telemetry" label — `features/signals/signals-page.tsx`
 * carries the level's own docstring. `Pull Request` gained its route the same day: the evidence
 * bundle a reviewer can now open at its own address, bounded by what `sync.dashboard.queries`
 * exposes rather than by what the design document's evidence bundle describes —
 * `features/pullrequests/pull-request-page.tsx` names the gap. A level with no route at all would
 * still belong in `GRAPH_LEVELS` regardless — `AppFrame` and the command palette already drop a level
 * group with nothing under it, so an unbuilt level costs nothing here.
 */

import type { ComponentType } from "react"
import { matchPath } from "react-router"

import { BindingSurfacePage } from "@/features/bindings/binding-surface-page"
import { CodebasePage } from "@/features/repositories/codebase-page"
import { DetectorsPage } from "@/features/detectors/detectors-page"
import { FindingPage } from "@/features/findings/finding-page"
import { FleetPage } from "@/features/fleet/fleet-page"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"
import { SettingsPage } from "@/features/settings/settings-page"
import { SignalsPage } from "@/features/signals/signals-page"
import { VendorPage } from "@/features/vendors/vendor-page"
import { WorkflowPage } from "@/features/workflows/workflow-page"

/**
 * The specification's levels, in the specification's order. Each comment is the line in
 * `2026-07-25-sync-self-maintaining-apis-design.md` that defines that level — the citation
 * `.claude/rules/console-hierarchy.md` requires before a value may land here.
 */
export const GRAPH_LEVELS = [
  "Fleet", // :430
  "Codebase", // :433
  "API Services", // :434
  "Signals", // :435
  "Binding surface", // :437
  "Errors & Incidents", // :439
  "Finding", // :440
  "Solution Workflow", // :441
  "Pull Request", // :442
] as const

export type GraphLevel = (typeof GRAPH_LEVELS)[number]

/**
 * The rail's vocabulary: six areas, each holding a contiguous run of `GRAPH_LEVELS`.
 *
 * **An area is a navigation grouping, not a graph level, and the distinction is load-bearing.**
 * `.claude/rules/console-hierarchy.md` binds `GRAPH_LEVELS` to the specification: a level with no
 * line in the design document does not go in that array. It says nothing about how a rail groups
 * them, and it must not be read as licence to invent one either — so every area below is a *run of
 * consecutive levels in the specification's own order*, which is why the `levels` arrays are
 * contiguous slices and not curated sets, and why `routes.test.tsx` asserts the six of them cover
 * `GRAPH_LEVELS` exactly once each.
 *
 * `Settings` is deliberately absent. The rail renders it last, and it is not a member of this
 * union: no route declares it, the specification declares no level for it, and putting it here
 * would be the fourth invented level rather than the first honest one.
 */
export type Area = "fleet" | "codebase" | "api-services" | "signals" | "observe" | "remediation"

/**
 * `landing` is the route the rail item links to, and `null` means every route inside this area needs
 * a subject the registry does not hold. That is not a gap to paper over: a Solution Workflow exists
 * for a finding, so it is reached from one, and the rail says so instead of offering a link that
 * would resolve to `/findings//workflow`. An area with no landing selects its sidebar without
 * navigating, which is what makes its levels discoverable before an operator has picked a subject.
 */
export interface AreaEntry {
  id: Area
  label: string
  /** What this area is for, one line, in the sidebar under its heading. */
  purpose: string
  levels: readonly GraphLevel[]
  landing: string | null
}

export const AREAS: readonly AreaEntry[] = [
  {
    id: "fleet",
    label: "Codebases",
    purpose: "All repositories watched by Sync, their attached vendors, and active migrations.",
    levels: ["Fleet"],
    landing: "/",
  },
  {
    id: "codebase",
    label: "Codebase",
    purpose: "What the index found in one repository, and what it cannot see.",
    levels: ["Codebase"],
    landing: null,
  },
  {
    id: "api-services",
    label: "API services",
    purpose: "What a vendor changed, and what those changes put at risk.",
    levels: ["API Services"],
    landing: null,
  },
  {
    id: "signals",
    label: "Signals",
    purpose: "What a repository has attached, and what each source has reported.",
    levels: ["Signals"],
    landing: null,
  },
  {
    id: "observe",
    label: "Observe",
    purpose: "Where a vendor change lands in the code, and which detector said so.",
    levels: ["Binding surface", "Errors & Incidents"],
    landing: "/detectors",
  },
  {
    id: "remediation",
    label: "Remediation",
    purpose: "What Sync did about a finding, node by node, including what it abandoned.",
    levels: ["Finding", "Solution Workflow", "Pull Request"],
    landing: null,
  },
] as const

export interface RouteEntry {
  /** Absolute path. Dynamic segments use react-router's `:name` syntax. */
  path: string
  label: string
  level: GraphLevel
  /**
   * The rail item this destination sits under. Derivable from `level` through `AREAS`, and
   * declared anyway: the grouping is a product decision a reviewer checks route by route, and a
   * derivation would put it in a `filter` nobody reads. `routes.test.tsx` holds the two against
   * each other so the declaration cannot drift from the run of levels its area claims.
   */
  area: Area
  /**
   * Which of the two sidebar regions this destination sits in.
   *
   * `repository` is scoped to one repository -- the independent variable the console is organised
   * around. `root` is what a reader reaches without having chosen one. Two regions replace six
   * areas because that is the only distinction the sidebar actually needs to draw.
   *
   * Three finding addresses sit in `repository` while declaring `findingId` rather than `repoId`.
   * That is deliberate and checked as a literal allow-list in `routes.test.tsx`: a fleet-wide
   * findings row has no repository to build a nested href from, because `RiskRow` carries none
   * (`api/types.ts:135-145`). It retires when that payload gains a `repo_id`.
   */
  region: "root" | "repository"
  /** What an operator opens this screen to find out, in one sentence. */
  question: string
  /**
   * Which subject supplies this route's parameters, in the operator's words — `null` on a route
   * that needs none. The sidebar renders it beside an unlinkable destination so a reader learns
   * where to go instead of meeting a dead label. Seven of nine routes need a subject.
   */
  reachedFrom: string | null
  /**
   * Names of the dynamic segments in `path`, in order. A non-empty list means this
   * destination needs a subject the registry does not hold — the navigation and the palette
   * render it as a place to look one up rather than as a direct link, so neither ever
   * renders an href with an empty parameter in it.
   */
  params: readonly string[]
  element: ComponentType
}

export const ROUTES: readonly RouteEntry[] = [
  {
    path: "/",
    region: "root",
    reachedFrom: null,
    label: "Codebases",
    area: "fleet",
    level: "Fleet",
    question: "All code repositories monitored by Sync, their attached API vendors, and active migrations.",
    params: [],
    element: FleetPage,
  },
  {
    path: "/repositories/:repoId",
    region: "repository",
    reachedFrom: "a repository on the codebases screen",
    label: "Codebase",
    area: "codebase",
    level: "Codebase",
    question: "Is this repository actually covered, and what does Sync not see in it?",
    params: ["repoId"],
    element: CodebasePage,
  },
  {
    path: "/vendors/:vendorId",
    region: "root",
    reachedFrom: "a vendor on the codebases screen",
    label: "Vendor",
    area: "api-services",
    level: "API Services",
    question: "What is at risk from this vendor, and what did it change?",
    params: ["vendorId"],
    element: VendorPage,
  },
  {
    path: "/repositories/:repoId/observed",
    region: "repository",
    reachedFrom: "a repository on the codebases screen",
    label: "Signals",
    area: "signals",
    level: "Signals",
    question:
      "What vendor, signal source and human surface does this repository have attached, and what has each reported?",
    params: ["repoId"],
    element: SignalsPage,
  },
  {
    path: "/bindings/vendors/:vendorId/operations/:operationId",
    region: "root",
    reachedFrom: "an operation on a vendor's findings table",
    label: "Binding surface",
    area: "observe",
    level: "Binding surface",
    question: "A vendor shipped a breaking change — what call sites does it hit?",
    params: ["vendorId", "operationId"],
    element: BindingSurfacePage,
  },
  {
    path: "/detectors",
    region: "root",
    reachedFrom: null,
    label: "Detectors",
    area: "observe",
    level: "Errors & Incidents",
    question: "Which detector is producing my false positives?",
    params: [],
    element: DetectorsPage,
  },
  {
    path: "/findings/:findingId",
    region: "repository",
    reachedFrom: "a call site on a vendor or binding surface",
    label: "Finding",
    area: "remediation",
    level: "Finding",
    question: "What is this finding, and what binding does it rest on?",
    params: ["findingId"],
    element: FindingPage,
  },
  {
    path: "/findings/:findingId/workflow",
    region: "repository",
    reachedFrom: "the finding it remediates",
    label: "Solution workflow",
    area: "remediation",
    level: "Solution Workflow",
    question: "What did Sync's remediation graph do about this finding, node by node?",
    params: ["findingId"],
    element: WorkflowPage,
  },
  {
    path: "/findings/:findingId/workflow/pull-request",
    region: "repository",
    reachedFrom: "the solution workflow that opened it",
    label: "Pull request",
    area: "remediation",
    level: "Pull Request",
    question: "Did Sync open a pull request for this finding, and what proof backs it?",
    params: ["findingId"],
    element: PullRequestPage,
  },
] as const

/**
 * The sentence `layouts/page-header.tsx` renders for a route, read out of the registry.
 *
 * `PageHeader` takes the question as a prop rather than looking it up — its own docstring carries
 * why, and it is so a header rendered outside the router still has one. This is how a screen
 * supplies it without writing a second copy: the registry's sentence is what the sidebar's tooltip
 * and the command palette already show, and a screen that restated it would eventually disagree
 * with both.
 *
 * It throws rather than falling back to an empty string. A path this does not know is a typo in a
 * screen, and a header quietly rendering nothing at the display step is precisely the flatness the
 * step was added to fix — it would look like a styling problem for as long as it took somebody to
 * open the registry.
 */
export function routeQuestion(path: string): string {
  const entry = ROUTES.find((route) => route.path === path)
  if (entry === undefined) {
    throw new Error(`no route is declared at ${path}, so it has no question to render`)
  }
  return entry.question
}

/**
 * Whether a navigation item is the one the current address is inside.
 *
 * `pages` is how an item that owns more than one address says so — in data, rather than through a
 * regex over the path that quietly stops matching the day a route is added beneath it. The rail
 * supplies it: an area owns a run of levels, so `Observe` stays current on a binding surface as
 * well as on `/detectors`. A sidebar row owns exactly one address today and passes none, which is
 * why the default is the item's own path rather than an empty set.
 *
 * The two branches are not interchangeable. A parameterised pattern goes through `matchPath`, which
 * matches to the end of the path — without it `/findings/:findingId/workflow` would claim the pull
 * request nested under it and two rows would render as current. A literal path takes the prefix
 * test instead, and `p + "/"` rather than `p` is what stops `/` claiming the whole console.
 */
export function isActiveMenuItem(
  entry: { path: string; pages?: readonly string[] },
  pathname: string
): boolean {
  const owned = entry.pages ?? [entry.path]
  return owned.some((p) =>
    p.includes(":")
      ? matchPath(p, pathname) !== null
      : pathname === p || pathname.startsWith(p + "/")
  )
}

/**
 * The subjects the current address holds, keyed by the parameter name that captured them.
 *
 * The registry deliberately holds no vendor id and no finding id, which is why seven of the nine
 * destinations used to render as text everywhere. The *address* holds them — and on a detail route
 * it holds precisely the ones that route's siblings need, because an area is a run of consecutive
 * levels over one subject. `/findings/f-1/workflow` binds `findingId`, and all three Remediation
 * destinations declare that parameter and no other.
 *
 * The first matching route wins and the loop stops. `matchPath` anchors to the end of the path, so
 * at most one entry can match: `/findings/:findingId` does not match `/findings/f-1/workflow`.
 * An address no route declares binds nothing, which is the honest answer for `UnknownRoute`.
 */
export function boundParams(pathname: string): Record<string, string> {
  for (const route of ROUTES) {
    const match = matchPath(route.path, pathname)
    if (match === null) continue
    const bound: Record<string, string> = {}
    for (const [name, value] of Object.entries(match.params)) {
      if (typeof value === "string" && value.length > 0) bound[name] = value
    }
    return bound
  }
  return {}
}

/**
 * Where a destination points from here, or `null` when this address cannot say.
 *
 * All-or-nothing by parameter, and that is the whole rule: a route with one of its two subjects
 * bound is not a destination, because the href would read `/bindings/vendors/stripe/operations/`
 * and resolve to a screen with half a subject. `null` is what makes the navigation render the row
 * as text carrying `reachedFrom` instead.
 *
 * `matchPath` decodes what it captures, so the value is re-encoded on the way back out. Without
 * that a subject containing a slash would generate an href pointing at a different, shorter path.
 */
export function destinationHref(
  route: RouteEntry,
  bound: Record<string, string>
): string | null {
  if (!route.params.every((name) => name in bound)) return null
  return route.params.reduce(
    (path, name) => path.replace(`:${name}`, encodeURIComponent(bound[name])),
    route.path
  )
}

/**
 * A destination that is not a level.
 *
 * `.claude/rules/console-hierarchy.md` binds `GRAPH_LEVELS` to the design document: a level with
 * no line in that document does not go in the array, and three plans invented four levels between
 * them before the rule was written. Settings is drawn in the mock, specified nowhere, and is not a
 * rung on the graph — it configures the system the graph describes.
 *
 * Rather than widen `RouteEntry.level` to accept `null` and weaken the guard on nine real levels,
 * a destination is its own kind of entry. `App.tsx` serves both arrays, the rail renders this one
 * in the slot it already reserved, and the palette lists it in a group of its own — so a screen
 * that is not a level is still reachable three ways, which is the reachability guarantee
 * `routes.test.tsx` exists to hold.
 */
export interface DestinationEntry {
  path: string
  label: string
  /** What an operator opens this screen to find out, in one sentence. The header renders it. */
  question: string
  element: ComponentType
}

export const DESTINATIONS: readonly DestinationEntry[] = [
  {
    path: "/settings",
    label: "Settings",
    question:
      "What does this deployment watch, what has each adapter actually delivered, and what " +
      "policy is in force when a patch is ready?",
    element: SettingsPage,
  },
] as const

/** Every destination inside an area, in the specification's order. */
function routesInArea(area: Area): readonly RouteEntry[] {
  return ROUTES.filter((route) => route.area === area)
}

/**
 * Whether the rail should render this area as the one being looked at.
 *
 * This is the `pages` branch above with a real caller behind it: an area owns every address inside
 * its run of levels, so `Observe` is current on a binding surface as much as on `/detectors`, and it
 * says which addresses those are by listing them rather than by matching a prefix.
 */
function isActiveArea(area: AreaEntry, pathname: string): boolean {
  const owned = routesInArea(area.id)
  return isActiveMenuItem(
    { path: area.landing ?? owned[0].path, pages: owned.map((route) => route.path) },
    pathname
  )
}

/**
 * Which rail item an address sits under.
 *
 * Falls back to the first area rather than throwing: `App.tsx` serves `UnknownRoute` at an address
 * no route declares, and that screen renders inside this chassis like any other. A rail with no
 * item selected there would be a fourth state nothing else in the shell has.
 */
export function areaForPathname(pathname: string): Area {
  return AREAS.find((area) => isActiveArea(area, pathname))?.id ?? AREAS[0].id
}
