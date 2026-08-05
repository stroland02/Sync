/**
 * The route registry: the single source of truth for every destination this console
 * declares. `App.tsx` builds its `<Route>` elements from this array, the persistent
 * navigation renders from it, and the command palette searches it. A route that is not an
 * entry here does not exist — delete an entry and the destination stops resolving in the
 * router, the navigation and the palette at once, because all three read the same array
 * rather than three copies of the same thirteen-file habit.
 *
 * `level` is the route's position in the API Dependency Graph, in the order the app shell's
 * header used to render as a static caption: Fleet -> Codebase -> API Services ->
 * Errors & Incidents -> Finding -> Solution Workflow. Two rulings this file makes concrete,
 * recorded here because neither is settled by a single page's own docstring:
 *
 * - `/bindings` sits at API Services rather than Codebase, because its own docstring leads
 *   with "which call sites bind to a vendor operation" before "what the index holds per
 *   repository" — the vendor-operation question is primary.
 * - `/detectors` sits at Errors & Incidents rather than Finding. `/codebase` (Codebase)
 *   aggregates over the API Services entities one level below it; by the same pattern, an
 *   aggregate over every open finding sits one level above Finding, which is
 *   Errors & Incidents.
 */

import type { ComponentType } from "react"

import { BindingSurfacePage } from "@/features/bindings/binding-surface-page"
import { BindingsPage } from "@/features/bindings/bindings-page"
import { RepositoryCoveragePage } from "@/features/bindings/repository-coverage-page"
import { DetectorsPage } from "@/features/detectors/detectors-page"
import { FindingPage } from "@/features/findings/finding-page"
import { FleetPage } from "@/features/fleet/fleet-page"
import { OverviewPage } from "@/features/repositories/overview-page"
import { ObservedTelemetryHubPage } from "@/features/telemetry/observed-telemetry-hub-page"
import { ObservedTelemetryPage } from "@/features/telemetry/observed-telemetry-page"
import { VendorPage } from "@/features/vendors/vendor-page"
import { WorkflowPage } from "@/features/workflows/workflow-page"

/** The six levels, in graph order. Every grouping and every ordering reads from this. */
export const GRAPH_LEVELS = [
  "Fleet",
  "Codebase",
  "API Services",
  "Errors & Incidents",
  "Finding",
  "Solution Workflow",
] as const

export type GraphLevel = (typeof GRAPH_LEVELS)[number]

export interface RouteEntry {
  /** Absolute path. Dynamic segments use react-router's `:name` syntax. */
  path: string
  label: string
  level: GraphLevel
  /** What an operator opens this screen to find out, in one sentence. */
  question: string
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
    label: "Fleet",
    level: "Fleet",
    question: "What has Sync been doing across every run, and is one stuck right now?",
    params: [],
    element: FleetPage,
  },
  {
    path: "/codebase",
    label: "Codebase",
    level: "Codebase",
    question: "Which vendors have open findings against this codebase right now?",
    params: [],
    element: OverviewPage,
  },
  {
    path: "/bindings/repositories/:repoId",
    label: "Repository coverage",
    level: "Codebase",
    question: "Is this repository actually covered, and what does Sync not see in it?",
    params: ["repoId"],
    element: RepositoryCoveragePage,
  },
  {
    path: "/bindings",
    label: "Bindings",
    level: "API Services",
    question: "Which call sites bind to a vendor operation, and what changed about it?",
    params: [],
    element: BindingsPage,
  },
  {
    path: "/vendors/:vendorId",
    label: "Vendor",
    level: "API Services",
    question: "What is at risk from this vendor, and what did it change?",
    params: ["vendorId"],
    element: VendorPage,
  },
  {
    path: "/bindings/vendors/:vendorId/operations/:operationId",
    label: "Binding surface",
    level: "API Services",
    question: "A vendor shipped a breaking change — what call sites does it hit?",
    params: ["vendorId", "operationId"],
    element: BindingSurfacePage,
  },
  {
    path: "/detectors",
    label: "Detectors",
    level: "Errors & Incidents",
    question: "Which detector is producing my false positives?",
    params: [],
    element: DetectorsPage,
  },
  {
    path: "/observed-telemetry",
    label: "Observed telemetry",
    level: "Errors & Incidents",
    question: "Which repository's observed traffic do I want to see?",
    params: [],
    element: ObservedTelemetryHubPage,
  },
  {
    path: "/repositories/:repoId/observed",
    label: "Observed telemetry",
    level: "Errors & Incidents",
    question:
      "What traffic did Sync observe for this repository, and where did error rates move?",
    params: ["repoId"],
    element: ObservedTelemetryPage,
  },
  {
    path: "/findings/:findingId",
    label: "Finding",
    level: "Finding",
    question: "What is this finding, and what binding does it rest on?",
    params: ["findingId"],
    element: FindingPage,
  },
  {
    path: "/findings/:findingId/workflow",
    label: "Solution workflow",
    level: "Solution Workflow",
    question: "Sync opened this pull request — should I merge it?",
    params: ["findingId"],
    element: WorkflowPage,
  },
] as const
