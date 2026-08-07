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
 * still belong in `GRAPH_LEVELS` regardless — `AppFrame` and `CommandPalette` already drop a level
 * group with nothing under it, so an unbuilt level costs nothing here.
 */

import type { ComponentType } from "react"

import { BindingSurfacePage } from "@/features/bindings/binding-surface-page"
import { CodebasePage } from "@/features/repositories/codebase-page"
import { DetectorsPage } from "@/features/detectors/detectors-page"
import { FindingPage } from "@/features/findings/finding-page"
import { FleetPage } from "@/features/fleet/fleet-page"
import { PullRequestPage } from "@/features/pullrequests/pull-request-page"
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
 * The rail's items, each holding a contiguous run of `GRAPH_LEVELS`.
 *
 * **An area is a navigation grouping, not a graph level, and the distinction is load-bearing.**
 * `.claude/rules/console-hierarchy.md` binds `GRAPH_LEVELS` to the specification: a level with no
 * line in the design document does not go in that array. It says nothing about how a rail groups
 * them, and it must not be read as licence to invent one either — so every area below is a *run of
 * consecutive levels in the specification's own order*, which is why the `levels` arrays are
 * contiguous slices and not curated sets. Nine levels in one rail is the graph rendered as a
 * to-do list; four runs is the graph rendered as somewhere to stand.
 *
 * `landing` is the route the rail item links to, and `null` means every route inside this area needs
 * a subject the registry does not hold. That is not a gap to paper over: a Solution Workflow exists
 * for a finding, so it is reached from one, and the rail says so instead of offering a link that
 * would resolve to `/findings//workflow`. An area with no landing selects its sidebar without
 * navigating, which is what makes its levels discoverable before an operator has picked a subject.
 */
export interface AreaEntry {
  id: string
  label: string
  /** What this area is for, one line, in the sidebar under its heading. */
  purpose: string
  levels: readonly GraphLevel[]
  landing: string | null
}

export const AREAS: readonly AreaEntry[] = [
  {
    id: "fleet",
    label: "Fleet",
    purpose: "Every run across every repository, and whether one is stuck.",
    levels: ["Fleet"],
    landing: "/",
  },
  {
    id: "graph",
    label: "Graph",
    purpose: "What the index found in a codebase, and what it binds to at the vendor.",
    levels: ["Codebase", "API Services", "Signals", "Binding surface"],
    landing: null,
  },
  {
    id: "findings",
    label: "Findings",
    purpose: "What broke or drifted, which detector said so, and on which rung.",
    levels: ["Errors & Incidents", "Finding"],
    landing: "/detectors",
  },
  {
    id: "remediation",
    label: "Remediation",
    purpose: "What Sync did about a finding, node by node, including what it abandoned.",
    levels: ["Solution Workflow", "Pull Request"],
    landing: null,
  },
] as const

export interface RouteEntry {
  /** Absolute path. Dynamic segments use react-router's `:name` syntax. */
  path: string
  label: string
  level: GraphLevel
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
    reachedFrom: null,
    label: "Fleet",
    level: "Fleet",
    question: "What has Sync been doing across every run, and is one stuck right now?",
    params: [],
    element: FleetPage,
  },
  {
    path: "/repositories/:repoId",
    reachedFrom: "a repository on the fleet screen",
    label: "Codebase",
    level: "Codebase",
    question: "Is this repository actually covered, and what does Sync not see in it?",
    params: ["repoId"],
    element: CodebasePage,
  },
  {
    path: "/vendors/:vendorId",
    reachedFrom: "a vendor on the fleet screen",
    label: "Vendor",
    level: "API Services",
    question: "What is at risk from this vendor, and what did it change?",
    params: ["vendorId"],
    element: VendorPage,
  },
  {
    path: "/repositories/:repoId/observed",
    reachedFrom: "a repository on the fleet screen",
    label: "Signals",
    level: "Signals",
    question:
      "What vendor, signal source and human surface does this repository have attached, and what has each reported?",
    params: ["repoId"],
    element: SignalsPage,
  },
  {
    path: "/bindings/vendors/:vendorId/operations/:operationId",
    reachedFrom: "an operation on a vendor's findings table",
    label: "Binding surface",
    level: "Binding surface",
    question: "A vendor shipped a breaking change — what call sites does it hit?",
    params: ["vendorId", "operationId"],
    element: BindingSurfacePage,
  },
  {
    path: "/detectors",
    reachedFrom: null,
    label: "Detectors",
    level: "Errors & Incidents",
    question: "Which detector is producing my false positives?",
    params: [],
    element: DetectorsPage,
  },
  {
    path: "/findings/:findingId",
    reachedFrom: "a call site on a vendor or binding surface",
    label: "Finding",
    level: "Finding",
    question: "What is this finding, and what binding does it rest on?",
    params: ["findingId"],
    element: FindingPage,
  },
  {
    path: "/findings/:findingId/workflow",
    reachedFrom: "the finding it remediates",
    label: "Solution workflow",
    level: "Solution Workflow",
    question: "What did Sync's remediation graph do about this finding, node by node?",
    params: ["findingId"],
    element: WorkflowPage,
  },
  {
    path: "/findings/:findingId/workflow/pull-request",
    reachedFrom: "the solution workflow that opened it",
    label: "Pull request",
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
