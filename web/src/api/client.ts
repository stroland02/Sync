/**
 * The console's only data source: eight GET routes over the Python transport.
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
  CorpusSummary,
  FindingDetail,
  NotFoundBody,
  OverviewResponse,
  Page,
  RepositoriesResponse,
  RiskRow,
  RunsPage,
  VendorChangeRow,
  WorkflowState,
} from "@/api/types"

/** Matches `DEFAULT_LIMIT` in `sync.mcp.tools`, so a page here is a page there. */
export const DEFAULT_LIMIT = 50

export interface PageParams {
  limit?: number
  offset?: number
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

function withPageParams(path: string, params: PageParams): string {
  const query = new URLSearchParams()
  if (params.limit !== undefined) query.set("limit", String(params.limit))
  if (params.offset !== undefined) query.set("offset", String(params.offset))
  const rendered = query.toString()
  return rendered ? `${path}?${rendered}` : path
}

export function fetchOverview(signal?: AbortSignal): Promise<OverviewResponse> {
  return getJson<OverviewResponse>("/api/overview", signal)
}

export function fetchVendorFindings(
  vendorId: string,
  params: PageParams,
  signal?: AbortSignal,
): Promise<Page<RiskRow>> {
  const path = withPageParams(`/api/vendors/${encodeURIComponent(vendorId)}`, params)
  return getJson<Page<RiskRow>>(path, signal)
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

/** Every run the checkpointer holds, newest first — one row per thread, not per finding. */
export function fetchRuns(params: PageParams, signal?: AbortSignal): Promise<RunsPage> {
  const path = withPageParams("/api/runs", params)
  return getJson<RunsPage>(path, signal)
}

/** The repair record, aggregated: every `migration_outcome` row, by disposition, strategy and tier. */
export function fetchCorpus(signal?: AbortSignal): Promise<CorpusSummary> {
  return getJson<CorpusSummary>("/api/corpus", signal)
}

/** The `repo_id` roll-up from the index. */
export function fetchRepositories(signal?: AbortSignal): Promise<RepositoriesResponse> {
  return getJson<RepositoriesResponse>("/api/repositories", signal)
}
