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
 * A level with no route below still belongs in `GRAPH_LEVELS`: `Signals` and `Pull Request`
 * are both stored, specified, and only partly built. `SiteNav` and `CommandPalette` already
 * drop a level group with nothing under it, so an unbuilt level costs nothing here — leaving
 * it out would cost the next reconciliation the same afternoon this one took.
 */

import type { ComponentType } from "react"

import { BindingSurfacePage } from "@/features/bindings/binding-surface-page"
import { CodebasePage } from "@/features/repositories/codebase-page"
import { DetectorsPage } from "@/features/detectors/detectors-page"
import { FindingPage } from "@/features/findings/finding-page"
import { FleetPage } from "@/features/fleet/fleet-page"
import { ObservedTelemetryPage } from "@/features/telemetry/observed-telemetry-page"
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
    path: "/repositories/:repoId",
    label: "Codebase",
    level: "Codebase",
    question: "Is this repository actually covered, and what does Sync not see in it?",
    params: ["repoId"],
    element: CodebasePage,
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
    path: "/repositories/:repoId/observed",
    label: "Observed telemetry",
    level: "Signals",
    question:
      "What traffic did Sync observe for this repository, and where did error rates move?",
    params: ["repoId"],
    element: ObservedTelemetryPage,
  },
  {
    path: "/bindings/vendors/:vendorId/operations/:operationId",
    label: "Binding surface",
    level: "Binding surface",
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
