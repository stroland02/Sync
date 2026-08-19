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
import { DetectorsPage } from "@/features/detectors/detectors-page"
import { FindingPage } from "@/features/findings/finding-page"
import { FindingsPage } from "@/features/findings/findings-page"
import { CallSitesPage } from "@/features/bindings/call-sites-page"
import { MetricsPage } from "@/features/dashboards/metrics-page"
import { SolutionsPage } from "@/features/workflows/solutions-page"
import { IndexGraphPage } from "@/features/index-graph/index-graph-page"
import { CodebasePage } from "@/features/repositories/codebase-page"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"
import { SettingsPage } from "@/features/settings/settings-page"
import { SignalsPage } from "@/features/signals/signals-page"
import { RunsPage } from "@/features/runs/runs-page"
import { RepositoryServicesPage } from "@/features/vendors/repository-services-page"
import { RepositoryVendorsPage } from "@/features/vendors/repository-vendors-page"
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


export interface RouteEntry {
  /** Absolute path. Dynamic segments use react-router's `:name` syntax. */
  path: string
  label: string
  level: GraphLevel
  /**
   * Whether this destination is a row in the navigation.
   *
   * **Not every route is a destination.** A workspace supplies `:repoId` and nothing else, so a
   * route needing a vendor, an operation or a finding cannot be built from the selected workspace
   * alone. Those are reached from the page that holds the subject, and they are absent from the
   * rail rather than present and inert -- the owner's rule, and the correct half of it: a control
   * that vanishes is honest about being unavailable, one that absorbs the press reads as broken.
   */
  nav: boolean
  /**
   * The rail's own ordering, owner-ruled 2026-08-18: Overview, Findings, Integrations,
   * Connections, Logs, Metrics, Solutions, then the rest. Explicit because the rail no longer
   * groups by level — the reading order is a product decision, not an accident of registry
   * position — and an entry without one sorts after every entry that has one.
   */
  navOrder?: number
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
    path: "/repositories/:repoId",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 1,
    label: "Overview",
    level: "Codebase",
    question: "What does Sync see in this workspace, and what does it not?",
    params: ["repoId"],
    element: CodebasePage,
  },
  {
    // Call sites: the graph's raw material, browsable. An aggregate over the Binding surface
    // -- it lists the sites a binding is made of -- so `GRAPH_LEVELS` is untouched, the same
    // reasoning the findings list and detector attribution already carry.
    path: "/repositories/:repoId/call-sites",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 3,
    label: "Call sites",
    level: "Binding surface",
    question: "Where does this codebase call an integration's API, and what did each call bind to?",
    params: ["repoId"],
    element: CallSitesPage,
  },
  {
    // Metrics: the workspace's charts, its own rail entry by the owner's naming scheme. An
    // aggregate over levels the console already has, not a rung -- `GRAPH_LEVELS` untouched.
    path: "/repositories/:repoId/metrics",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 7,
    label: "Metrics",
    level: "Codebase",
    question: "What are this workspace's measured trends -- findings over time, observed volume?",
    params: ["repoId"],
    element: MetricsPage,
  },
  {
    // Solutions: every run that reached a pull request, the owner's page of 2026-08-18. An
    // aggregate over Solution Workflow and Pull Request, not a rung.
    path: "/repositories/:repoId/solutions",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 8,
    label: "Solutions",
    level: "Solution Workflow",
    question: "Which remediations reached the forge, and where is each one's evidence?",
    params: ["repoId"],
    element: SolutionsPage,
  },
  {
    path: "/repositories/:repoId/graph",
    reachedFrom: "the Overview's dependency-graph panel",
    // Out of the rail on the owner's direction, 2026-08-18: the Overview draws the graph
    // panel itself, so a rail button for the full canvas was a second door to a screen one
    // click away. The route stays — the panel links here and the palette still finds it.
    nav: false,
    label: "Dependency graph",
    level: "Codebase",
    question: "What does this workspace's whole indexed call graph look like, file by file?",
    params: ["repoId"],
    element: IndexGraphPage,
  },
  {
    // Second in the rail by the owner's ruling: what is in flight and what gave up is the thing an
    // operator checks most often, so it earns the slot next to the Overview rather than closing the
    // list. Its `level` is `Solution Workflow` and that is not a promotion -- this screen aggregates
    // over that level the way detector attribution aggregates over Errors & Incidents, and
    // `.claude/rules/console-hierarchy.md` is explicit that an aggregate is not a rung. `GRAPH_LEVELS`
    // is untouched, so no specification amendment was owed before this landed.
    // Owner naming ruling, 2026-08-18 (amended the same evening): Runs presents as "Logs" —
    // one row per attempt is the pipeline's own log — with its own rail entry. The LEVEL is
    // untouched: presentation vocabulary renames freely, the specification's words do not,
    // which is the fleet screen's own precedent.
    path: "/repositories/:repoId/runs",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 6,
    label: "Logs",
    level: "Solution Workflow",
    question:
      "What did the remediation pipeline attempt, what did it abandon, and which change kinds does it not handle mechanically?",
    params: ["repoId"],
    element: RunsPage,
  },
  {
    // Immediately after Runs by the owner's ruling: the things an operator acts on lead, the
    // things they investigate follow. This is the question the product exists to answer and the
    // rail did not have it -- a finding was reachable only by drilling through a vendor, a signal
    // or a detector first.
    //
    // `Finding` is the specification's own level, not a promotion: a list of findings aggregates
    // over findings, and an aggregate is not a rung. `GRAPH_LEVELS` is untouched.
    path: "/repositories/:repoId/findings",
    reachedFrom: "a workspace in the switcher",
    // Findings keeps its name and sits above Integrations by the owner's ordering; Metrics is
    // its own charts page below.
    nav: true,
    navOrder: 2,
    label: "Findings",
    level: "Finding",
    question: "What is broken in this workspace, and what is each finding bound to?",
    params: ["repoId"],
    element: FindingsPage,
  },
  {
    path: "/repositories/:repoId/services",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 5,
    // "Connections" by the owner's naming ruling, 2026-08-18. The LEVEL keeps the
    // specification's words -- presentation vocabulary renames freely, levels do not.
    label: "Connections",
    level: "API Services",
    question:
      "Which services is this workspace connected to, and what does the index know about each?",
    params: ["repoId"],
    element: RepositoryServicesPage,
  },
  {
    path: "/repositories/:repoId/vendors",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 4,
    // "Integrations" by the owner's naming ruling, 2026-08-18. Same split as above.
    label: "Integrations",
    level: "API Services",
    question: "Which integrations does this workspace use, and how much is open against each?",
    params: ["repoId"],
    element: RepositoryVendorsPage,
  },
  {
    path: "/repositories/:repoId/observed",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 9,
    label: "Signals",
    level: "Signals",
    question:
      "What vendor, signal source and human surface does this workspace have attached, and what has each reported?",
    params: ["repoId"],
    element: SignalsPage,
  },
  {
    path: "/repositories/:repoId/detectors",
    reachedFrom: "a workspace in the switcher",
    nav: true,
    navOrder: 10,
    label: "Detectors",
    level: "Errors & Incidents",
    question: "Which detector is producing this workspace's false positives?",
    params: ["repoId"],
    element: DetectorsPage,
  },
  {
    path: "/repositories/:repoId/vendors/:vendorId",
    reachedFrom: "a vendor on the Vendors page",
    nav: false,
    label: "Vendor",
    level: "API Services",
    question: "What is at risk from this vendor in this workspace, and what did it change?",
    params: ["repoId", "vendorId"],
    element: VendorPage,
  },
  {
    path: "/repositories/:repoId/bindings/vendors/:vendorId/operations/:operationId",
    reachedFrom: "an operation on a vendor page",
    nav: false,
    label: "Binding surface",
    level: "Binding surface",
    question: "Which call sites bind this operation, and what rung established each?",
    params: ["repoId", "vendorId", "operationId"],
    element: BindingSurfacePage,
  },
  {
    path: "/repositories/:repoId/findings/:findingId",
    reachedFrom: "a finding on a vendor or detector page",
    nav: false,
    label: "Finding",
    level: "Finding",
    question: "What is this finding, and what binding does it rest on?",
    params: ["repoId", "findingId"],
    element: FindingPage,
  },
  {
    path: "/repositories/:repoId/findings/:findingId/workflow",
    reachedFrom: "a finding",
    nav: false,
    label: "Solution workflow",
    level: "Solution Workflow",
    question: "What did Sync's remediation graph do about this finding, node by node?",
    params: ["repoId", "findingId"],
    element: WorkflowPage,
  },
  {
    path: "/repositories/:repoId/findings/:findingId/workflow/pull-request",
    reachedFrom: "a solution workflow that opened one",
    nav: false,
    label: "Pull request",
    level: "Pull Request",
    question: "Did Sync open a pull request for this finding, and what evidence went with it?",
    params: ["repoId", "findingId"],
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



