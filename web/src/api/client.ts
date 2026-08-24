/**
 * The console's only data source: sixteen GET routes over the Python transport.
 *
 * Paths are relative so one origin in development is one origin in production — the Vite
 * proxy in `vite.config.ts` exists so that nothing here depends on a cross-origin
 * permission the deployed app will not have.
 */

import {
  ApiStatusError,
  MalformedResponseError,
  NotFoundError,
  UnreachableApiError,
} from "@/api/errors"
import type {
  AdapterInventoryResponse,
  BindingSurfaceResponse,
  ChangeUnitsPage,
  PrecedentSummary,
  DetectorAccountabilityResponse,
  DismissalState,
  DismissalTally,
  FindingDetail,
  IndexCoverageResponse,
  NotFoundBody,
  ObservedTelemetryResponse,
  OverviewResponse,
  Page,
  RepositoriesResponse,
  RunsPage,
  AbandonmentResponse,
  FindingsOverTimeResponse,
  VendorChangeRow,
  VendorChangeVolumeResponse,
  VendorOperationsResponse,
  FindingOrder,
  VendorFindingsPage,
  PatchResponse,
  WorkflowState,
  RepositoryGraphResponse,
} from "@/api/types"

/** Matches `DEFAULT_LIMIT` in `sync.mcp.tools`, so a page here is a page there. */
export const DEFAULT_LIMIT = 50

export interface PageParams {
  limit?: number
  offset?: number
}

/**
 * The repository a question is asked about.
 *
 * Repository scope is what every level below Codebase inherits, so the routes those levels read
 * take it as a query parameter. Omitting it is the fleet — a real question, and the one the
 * Fleet screen asks — never a default standing in for "whichever repository the reader had in
 * mind".
 */
export interface ScopeParams {
  repoId?: string
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, { headers: { Accept: "application/json" }, signal })
  } catch (cause) {
    // An abort is the caller withdrawing the question, not the server failing to answer.
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause
    throw new UnreachableApiError(path, { cause })
  }

  if (response.status === 404) {
    const body = await readNotFoundBody(response, path)
    throw new NotFoundError(body.error, body.identifier, path)
  }
  if (!response.ok) {
    throw new ApiStatusError(response.status, path)
  }

  try {
    return (await response.json()) as T
  } catch (cause) {
    throw new MalformedResponseError(path, { cause })
  }
}

async function readNotFoundBody(response: Response, path: string): Promise<NotFoundBody> {
  try {
    return (await response.json()) as NotFoundBody
  } catch {
    // A 404 from something other than the API — a stray proxy, a static server. The
    // identifier is unknown, and claiming one would invent it.
    return { error: "not found", identifier: path }
  }
}

/**
 * A path with whatever query parameters the caller has, and none it does not.
 *
 * `undefined` drops the parameter rather than sending an empty value, because absent is what
 * every route on the Python side reads as "unfiltered" — an empty string would be a filter
 * matching nothing.
 */
function withQueryParams(path: string, params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value))
  }
  const rendered = query.toString()
  return rendered ? `${path}?${rendered}` : path
}

function withPageParams(path: string, params: PageParams): string {
  return withQueryParams(path, { limit: params.limit, offset: params.offset })
}

/**
 * Open findings by vendor and by severity.
 *
 * `repoId` narrows every figure in the answer to one repository; omitted, the answer spans the
 * fleet and the payload's own `repo_id` comes back null. The two are different questions and
 * the transport answers whichever it was asked — a screen below the Codebase level that fetches
 * this without a repository is claiming the fleet's numbers describe one codebase.
 */
export function fetchOverview(
  params: ScopeParams = {},
  signal?: AbortSignal,
): Promise<OverviewResponse> {
  return getJson<OverviewResponse>(withQueryParams("/api/overview", { repo_id: params.repoId }), signal)
}

export interface VendorFindingsParams extends PageParams, ScopeParams {
  /** One value out of the severities this scope actually holds; absent means every severity. */
  severity?: string
  /** A path prefix matched against the call site, never a substring; absent means every path. */
  path?: string
  /**
   * Which ordering to apply. Absent means the API's own default, which the payload names back —
   * so the screen states the ordering whether or not one was chosen. An ordering is not a filter
   * and narrows nothing: `total` is the same number under either.
   */
  order?: FindingOrder
}

/**
 * Open findings for one vendor, in one repository or across the fleet, optionally narrowed.
 *
 * `repoId` is the scope every level below Codebase inherits and the other two are filters the
 * operator sets, and they compose: a severity chosen inside a selected repository narrows that
 * repository's findings rather than replacing the scope with a fleet-wide answer.
 *
 * All three are query parameters rather than a filter over the returned rows, and that is
 * load-bearing: `sync.dashboard.graph_views.vendor_findings` applies them as SQL predicates
 * ahead of its own `LIMIT`, so a filtered page's `total` is the filtered total. Filtering here
 * instead would leave `total` describing a set the rows on screen were not drawn from.
 */
export function fetchVendorFindings(
  vendorId: string,
  params: VendorFindingsParams,
  signal?: AbortSignal,
): Promise<VendorFindingsPage> {
  const path = withQueryParams(`/api/vendors/${encodeURIComponent(vendorId)}`, {
    limit: params.limit,
    offset: params.offset,
    repo_id: params.repoId,
    severity: params.severity ?? undefined,
    path: params.path,
    order: params.order,
  })
  return getJson<VendorFindingsPage>(path, signal)
}

/**
 * `GET /api/vendors/{vendor_id}/change-volume` -- the vendor's whole change history, aggregated.
 *
 * Deliberately unpaged. The console used to derive this from a page of `fetchVendorChanges` and
 * print the result as the vendor's total, which moved when a reader paginated.
 */
/**
 * `GET /api/repositories/{repo_id}/findings` -- every open finding in one workspace.
 *
 * The same page shape the vendor level reads, narrowed by workspace instead of by vendor. The
 * route has existed since the transport was written; nothing called it, because the only hook
 * for this payload required a vendor id, so the console had no way to ask *what is broken here*.
 *
 * The workspace is a path segment rather than a query parameter, matching the route registry:
 * scope stated twice is scope free to disagree with itself.
 */
export function fetchWorkspaceFindings(
  repoId: string,
  params: VendorFindingsParams,
  signal?: AbortSignal,
): Promise<VendorFindingsPage> {
  const path = withQueryParams(
    `/api/repositories/${encodeURIComponent(repoId)}/findings`,
    {
      limit: params.limit,
      offset: params.offset,
      severity: params.severity,
      path: params.path,
      order: params.order,
    },
  )
  return getJson<VendorFindingsPage>(path, signal)
}

export function fetchVendorChangeVolume(
  vendorId: string,
  signal?: AbortSignal,
): Promise<VendorChangeVolumeResponse> {
  return getJson<VendorChangeVolumeResponse>(
    `/api/vendors/${encodeURIComponent(vendorId)}/change-volume`,
    signal,
  )
}

export function fetchVendorChanges(
  vendorId: string,
  params: PageParams,
  signal?: AbortSignal,
): Promise<Page<VendorChangeRow>> {
  const path = withPageParams(
    `/api/vendors/${encodeURIComponent(vendorId)}/changes`,
    params,
  )
  return getJson<Page<VendorChangeRow>>(path, signal)
}

export function fetchFindingsOverTime(
  repoId: string | null,
  signal?: AbortSignal,
): Promise<FindingsOverTimeResponse> {
  const path = "/api/findings/over-time"
  return getJson<FindingsOverTimeResponse>(
    repoId === null ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`,
    signal,
  )
}

export function fetchAbandonment(signal?: AbortSignal): Promise<AbandonmentResponse> {
  return getJson<AbandonmentResponse>("/api/precedent/abandonment", signal)
}

export function fetchVendorOperations(
  vendorId: string,
  repoId: string | null,
  signal?: AbortSignal,
): Promise<VendorOperationsResponse> {
  const path = `/api/vendors/${encodeURIComponent(vendorId)}/operations`
  return getJson<VendorOperationsResponse>(
    repoId === null ? path : `${path}?repo_id=${encodeURIComponent(repoId)}`,
    signal,
  )
}

export function fetchFinding(
  findingId: string,
  signal?: AbortSignal,
): Promise<FindingDetail> {
  return getJson<FindingDetail>(`/api/findings/${encodeURIComponent(findingId)}`, signal)
}

/**
 * The remediation run for a finding.
 *
 * 404 here means the checkpointer holds no run for this finding — a true answer, and a
 * different sentence from the finding route's 404. It arrives as `NotFoundError` like
 * every other 404, and the view decides which sentence to print.
 */
export function fetchWorkflow(
  findingId: string,
  signal?: AbortSignal,
): Promise<WorkflowState> {
  return getJson<WorkflowState>(`/api/workflows/${encodeURIComponent(findingId)}`, signal)
}

/**
 * Whether a human has dismissed this finding, and how often that has flipped.
 *
 * Read-only from the console, on the owner's ruling of 2026-08-19: the route accepts a POST and
 * this client does not send one, so dismissing stays a CLI action. What the console owes is the
 * standing, because a finding somebody dismissed and a finding nobody has looked at render
 * identically without it.
 *
 * `finding_dismissal` is durable and `finding` is re-derived, so this answers for a finding the
 * finding route 404s on. That is the same independence `fetchWorkflow` has from the graph, and
 * the view must not gate this query on the finding query succeeding.
 */
export function fetchDismissal(
  findingId: string,
  signal?: AbortSignal,
): Promise<DismissalState> {
  return getJson<DismissalState>(
    `/api/findings/${encodeURIComponent(findingId)}/dismissal`,
    signal,
  )
}

/**
 * Dismissed findings across the graph, tallied by the reason standing against each.
 *
 * Unscoped by repository, and that is the route rather than an omission here: `finding_dismissal`
 * carries a finding id and no `repo_id`. The screen must say so rather than let a figure on a
 * workspace-scoped page read as that workspace's.
 */
export function fetchDismissalTally(signal?: AbortSignal): Promise<DismissalTally> {
  return getJson<DismissalTally>("/api/findings/dismissals", signal)
}

/**
 * The patch a run produced, with the branch and repository it was pushed to.
 *
 * A 404 here means no run exists for the finding at all. A run that produced no patch is a
 * 200 carrying the reason, because deciding against a patch is an answer rather than a
 * missing page -- and the reason is what a reviewer opened the screen to read.
 */
export function fetchPatch(findingId: string, signal?: AbortSignal): Promise<PatchResponse> {
  return getJson<PatchResponse>(
    `/api/findings/${encodeURIComponent(findingId)}/patch`,
    signal,
  )
}

export interface RunsParams extends PageParams {
  /** A disposition value, `"in-flight"` for runs without one, or null for every run. */
  outcome?: string | null
}

/** Every run the checkpointer holds, newest first — one row per thread, not per finding. */
export function fetchRuns(params: RunsParams, signal?: AbortSignal): Promise<RunsPage> {
  const paged = withPageParams("/api/runs", params)
  const path =
    params.outcome == null
      ? paged
      : `${paged}${paged.includes("?") ? "&" : "?"}outcome=${encodeURIComponent(params.outcome)}`
  return getJson<RunsPage>(path, signal)
}

/** The repair record, aggregated: every `migration_outcome` row, by disposition, strategy and tier. */
export function fetchCorpus(signal?: AbortSignal): Promise<PrecedentSummary> {
  return getJson<PrecedentSummary>("/api/precedent", signal)
}

export interface ChangeUnitsParams extends PageParams, ScopeParams {
  /**
   * Narrow to one severity before grouping.
   *
   * Before rather than after is the whole reconciliation: a unit then reports the findings of
   * this severity it holds, and the sum still equals the flat total for the same tab.
   */
  severity?: string | null
}

/**
 * Open findings grouped by the vendor change and operation that produced them —
 * `sync.dashboard.fleet.change_units`'s own grain, computed once so the console never derives
 * it a second way from `/api/overview` and `/api/runs`.
 *
 * `repoId` narrows the grouping itself, not just the rows shown afterward: the reader filters
 * the underlying open findings to one repository before folding them into change units, so a
 * scoped page's `repository_count` and `call_site_count` describe that repository alone.
 */
export function fetchChangeUnits(
  params: ChangeUnitsParams = {},
  signal?: AbortSignal,
): Promise<ChangeUnitsPage> {
  const path = withQueryParams("/api/change-units", {
    repo_id: params.repoId,
    // The severity narrows findings *before* they are grouped, so the grouped totals reconcile
    // with the flat ones on every tab. A tab that stopped applying once the view changed would
    // look active over numbers true of something else.
    severity: params.severity ?? undefined,
    limit: params.limit,
    offset: params.offset,
  })
  return getJson<ChangeUnitsPage>(path, signal)
}

/** The `repo_id` roll-up from the index. */
export function fetchRepositories(signal?: AbortSignal): Promise<RepositoriesResponse> {
  return getJson<RepositoriesResponse>("/api/repositories", signal)
}

export interface BindingSurfaceParams {
  repoId?: string
  /** A path prefix matched against the call site, never a substring; absent means every path. */
  pathPrefix?: string
  callSitesLimit?: number
  callSitesOffset?: number
  changesLimit?: number
  changesOffset?: number
}

/**
 * Every call site the index holds against one vendor operation, and what the vendor has
 * changed about it. `repoId` narrows to one repository; omitted, the answer spans every
 * repository the index has seen calling this operation.
 *
 * Call sites and changes page independently, matching `binding_surface`'s own contract: a
 * customer with a long feed history but few call sites (or the reverse) can page one set
 * without the other's size leaking in.
 *
 * `pathPrefix` narrows the call sites and their total together, and leaves the changes alone: a
 * vendor change has no position in the customer's codebase, so narrowing it by a source path
 * would answer nobody's question with whichever rows happened to share a prefix.
 */
export function fetchBindingSurface(
  vendorId: string,
  operationId: string,
  params: BindingSurfaceParams = {},
  signal?: AbortSignal,
): Promise<BindingSurfaceResponse> {
  const path = withQueryParams(
    `/api/vendors/${encodeURIComponent(vendorId)}/operations/${encodeURIComponent(operationId)}/bindings`,
    {
      repo_id: params.repoId,
      path_prefix: params.pathPrefix,
      call_sites_limit: params.callSitesLimit,
      call_sites_offset: params.callSitesOffset,
      changes_limit: params.changesLimit,
      changes_offset: params.changesOffset,
    },
  )
  return getJson<BindingSurfaceResponse>(path, signal)
}

/** How many indexed call sites one repository has, per vendor. */
export function fetchRepositoryCoverage(
  repoId: string,
  signal?: AbortSignal,
): Promise<IndexCoverageResponse> {
  return getJson<IndexCoverageResponse>(
    `/api/repositories/${encodeURIComponent(repoId)}/coverage`,
    signal,
  )
}

/** This repository's call sites and the vendors they reach -- the Overview's dependency graph. */
export function fetchRepositoryGraph(
  repoId: string,
  signal?: AbortSignal,
): Promise<RepositoryGraphResponse> {
  return getJson<RepositoryGraphResponse>(
    `/api/repositories/${encodeURIComponent(repoId)}/graph`,
    signal,
  )
}

export interface ObservedTelemetryParams {
  callsLimit?: number
  callsOffset?: number
  shapesLimit?: number
  shapesOffset?: number
  errorWindowsLimit?: number
  errorWindowsOffset?: number
}

/**
 * What traffic showed up for one repository, what shape it had, and how often it failed.
 *
 * The three sets page independently, matching `observed_telemetry`'s own contract: they are
 * three questions of different cardinality stacked on one screen.
 */
export function fetchRepositoryObserved(
  repoId: string,
  params: ObservedTelemetryParams = {},
  signal?: AbortSignal,
): Promise<ObservedTelemetryResponse> {
  const path = withQueryParams(`/api/repositories/${encodeURIComponent(repoId)}/observed`, {
    calls_limit: params.callsLimit,
    calls_offset: params.callsOffset,
    shapes_limit: params.shapesLimit,
    shapes_offset: params.shapesOffset,
    error_windows_limit: params.errorWindowsLimit,
    error_windows_offset: params.errorWindowsOffset,
  })
  return getJson<ObservedTelemetryResponse>(path, signal)
}

/**
 * Every open finding, aggregated by the detector that raised it.
 *
 * `repoId` narrows the roll-up to one repository — "which detector is producing *my* false
 * positives" rather than the fleet's. The answer echoes the scope back in `repo_id`.
 */
export function fetchDetectors(
  params: ScopeParams = {},
  signal?: AbortSignal,
): Promise<DetectorAccountabilityResponse> {
  return getJson<DetectorAccountabilityResponse>(
    withQueryParams("/api/detectors", { repo_id: params.repoId }),
    signal,
  )
}


/**
 * Every adapter this deployment registers, and what each has ever delivered.
 *
 * Takes no scope. An adapter is a property of the deployment rather than of a repository, and
 * narrowing by one would answer a different question — which vendors a repository calls — that
 * `fetchObservedTelemetry` already answers better.
 */
export function fetchAdapters(signal?: AbortSignal): Promise<AdapterInventoryResponse> {
  return getJson<AdapterInventoryResponse>("/api/adapters", signal)
}
