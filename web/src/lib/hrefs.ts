/**
 * One place that knows what a destination's address looks like.
 *
 * **Why this module exists, measured rather than asserted.** `M14-W386` moved all ten routes under
 * `/repositories/:repoId/`. Nineteen call sites across eleven files went on building the old
 * unscoped `/findings/{id}`, `/vendors/{id}` and `/bindings/vendors/{id}/operations/{id}` paths, so
 * every finding and vendor link in the console rendered *No screen at this address*. Four separate
 * files each carried their own private copy of a `bindingSurfaceHref` helper — the same function,
 * written four times, and the route move had to find all four.
 *
 * That is `CLAUDE.md`'s *a fact written twice will disagree with itself*, at four copies, and it
 * disagreed silently: the build was clean, the lint was clean, and 771 console tests passed.
 * Nothing typechecks a string against a route table.
 *
 * So the fix is not nineteen corrected strings. It is one module, tested against `ROUTES` itself
 * with react-router's matcher, so the next route move breaks a test in one file instead of leaving
 * a reader clicking into a 404.
 *
 * **The scope is in the path now, not in a query parameter.** These used to pass `?repo_id=` beside
 * an unscoped path, which stated the scope twice and let the two disagree. The path is the single
 * statement, which is also what `M14-W386` made the route registry say.
 *
 * **Everything is escaped, because every repository id in this product contains a slash.**
 * `org/one` unescaped matches a different route or none.
 */

const repo = (repoId: string) => `/repositories/${encodeURIComponent(repoId)}`

/** The workspace's Overview — what the index, the vendors and the detectors say about it. */
export function overviewHref(repoId: string): string {
  return repo(repoId)
}

/** What the remediation pipeline attempted, and what it abandoned. */
export function runsHref(repoId: string): string {
  return `${repo(repoId)}/runs`
}

/** This workspace's call sites drawn out to its vendors. */
export function graphHref(repoId: string): string {
  return `${repo(repoId)}/graph`
}

/** Which API services this workspace calls. */
export function servicesHref(repoId: string): string {
  return `${repo(repoId)}/services`
}

/** The vendors attached to this workspace. */
export function vendorsHref(repoId: string): string {
  return `${repo(repoId)}/vendors`
}

/**
 * The Signals level.
 *
 * The path segment is `observed` and the destination is labelled "Signals". That mismatch is the
 * registry's and predates this module; naming the function for the label rather than the segment is
 * deliberate, so a caller reaches for the word the interface uses.
 */
export function signalsHref(repoId: string): string {
  return `${repo(repoId)}/observed`
}

/** Detector attribution — an aggregate over Errors & Incidents, not a level of its own. */
export function detectorsHref(repoId: string): string {
  return `${repo(repoId)}/detectors`
}

/** One vendor, within one workspace. */
export function vendorHref(repoId: string, vendorId: string): string {
  return `${repo(repoId)}/vendors/${encodeURIComponent(vendorId)}`
}

/** Where one operation binds to this workspace's call sites, and at which rung. */
export function bindingSurfaceHref(
  repoId: string,
  vendorId: string,
  operationId: string,
): string {
  return `${repo(repoId)}/bindings/vendors/${encodeURIComponent(
    vendorId,
  )}/operations/${encodeURIComponent(operationId)}`
}

/**
 * Every open finding in the workspace.
 *
 * One letter from `findingHref`, which is the detail. That is the same pairing `vendorsHref` and
 * `vendorHref` already use, so the convention is consistent rather than a trap unique to findings —
 * plural is the list, singular takes a subject.
 */
export function findingsHref(repoId: string): string {
  return `${repo(repoId)}/findings`
}

/** One finding. */
export function findingHref(repoId: string, findingId: string): string {
  return `${repo(repoId)}/findings/${encodeURIComponent(findingId)}`
}

/** The solution workflow for one finding. */
export function workflowHref(repoId: string, findingId: string): string {
  return `${findingHref(repoId, findingId)}/workflow`
}

/** The pull request a workflow opened. */
export function pullRequestHref(repoId: string, findingId: string): string {
  return `${workflowHref(repoId, findingId)}/pull-request`
}

/**
 * The six destinations added between `CI-W486` and `CI-W501`.
 *
 * They shipped with their addresses written inline at each call site, which is exactly the drift
 * this module exists to stop — `hrefs.test.ts` caught all six by asserting every declared route
 * has a builder, which is the guard doing its job rather than a test to relax.
 */

/** The file tree, full screen, with this codebase's technical census. */
export function fileTreeHref(repoId: string): string {
  return `${repo(repoId)}/file-tree`
}

/** What the watched integrations have published, newest first. */
export function integrationChangesHref(repoId: string): string {
  return `${repo(repoId)}/integration-changes`
}

/** The graph's raw material: where this codebase calls an integration. */
export function callSitesHref(repoId: string): string {
  return `${repo(repoId)}/call-sites`
}

/** The workspace's measured trends over time. */
export function trendsHref(repoId: string): string {
  return `${repo(repoId)}/metrics`
}

/** What the remediation loop has produced, and which axes have no sample yet. */
export function precedentHref(repoId: string): string {
  return `${repo(repoId)}/precedent`
}

/** Every remediation that reached the forge. */
export function solutionsHref(repoId: string): string {
  return `${repo(repoId)}/solutions`
}
