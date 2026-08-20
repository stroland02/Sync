/**
 * Which page answers which pipeline stage, for every page a selected workspace can reach.
 *
 * `WORKFLOW_STAGES` is the vocabulary and the rail already groups its rows by it; this adds the
 * pages that are not rail rows, so the Overview can draw the whole pipeline rather than the nine
 * doors the rail happens to carry. `stage-pages.test.ts` holds the invariant that every
 * workspace-reachable route lands in exactly one stage.
 */

import { ROUTES, WORKFLOW_STAGES, destinationHref, type RouteEntry, type WorkflowStage } from "@/lib/routes"

// Re-exported so the Overview's components take the registry through this module alone.
// `features/` may not import `lib/routes` directly (B120: routes.ts imports every feature page
// to build its element, so the reverse import closes a module-init cycle); everything here
// reads the registry inside function bodies, which is what keeps the indirection init-safe.
export { destinationHref, type RouteEntry, type WorkflowStage }

/** What each stage does to the graph, in the owner's own words for the stage vocabulary. */
export const STAGE_DOES: Record<WorkflowStage, string> = {
  Index: "reads the code",
  Signal: "downloads vendor specs and diffs them",
  Observe: "records the traffic a deployment shows it",
  Detect: "turns evidence into findings",
  Remediate: "patches, verifies and opens the pull request",
}

/** The Overview itself: the screen the pipeline is drawn on, and the one page no stage lists. */
export const PIPELINE_HOME = "/repositories/:repoId"

/**
 * The stage of a page the rail does not carry.
 *
 * A rail row declares its own `stage` and this must not repeat it — two spellings of one fact
 * disagree the day one of them moves. `stageOf` reads the route first and falls back here.
 */
const OFF_RAIL_STAGE: Record<string, WorkflowStage> = {
  "/repositories/:repoId/file-tree": "Index",
  "/repositories/:repoId/graph": "Index",
  "/repositories/:repoId/integration-changes": "Signal",
  "/repositories/:repoId/metrics": "Detect",
  "/repositories/:repoId/corpus": "Remediate",
}

export function stageOf(route: RouteEntry): WorkflowStage | null {
  return route.stage ?? OFF_RAIL_STAGE[route.path] ?? null
}

/**
 * Every page a workspace reaches from the switcher alone, the Overview excluded.
 *
 * The parameter list is the test rather than `nav`: a route needing a vendor, an operation or a
 * finding cannot be opened from the Overview at all, so it is not a door this screen can draw.
 */
export function workspacePages(): RouteEntry[] {
  return ROUTES.filter(
    (route) =>
      route.path !== PIPELINE_HOME &&
      route.params.length === 1 &&
      route.params[0] === "repoId"
  )
}

/** The stages in pipeline order, each with its pages in the rail's reading order. */
export function pagesByStage(): { stage: WorkflowStage; pages: RouteEntry[] }[] {
  return WORKFLOW_STAGES.map((stage) => ({
    stage,
    pages: workspacePages()
      .filter((route) => stageOf(route) === stage)
      .sort((a, b) => (a.navOrder ?? Number.MAX_SAFE_INTEGER) - (b.navOrder ?? Number.MAX_SAFE_INTEGER)),
  }))
}
