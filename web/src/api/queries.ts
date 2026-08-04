/**
 * One hook per route, so a component names the question and never the URL.
 *
 * Query keys mirror the graph hierarchy, which means invalidating a vendor invalidates
 * everything read under it.
 */

import { useQuery } from "@tanstack/react-query"

import {
  DEFAULT_LIMIT,
  fetchFinding,
  fetchOverview,
  fetchVendorChanges,
  fetchVendorFindings,
  fetchWorkflow,
} from "@/api/client"
import type { ChangeParams, PageParams } from "@/api/client"
import type { WorkflowState } from "@/api/types"

export function useOverview() {
  return useQuery({
    queryKey: ["overview"],
    queryFn: ({ signal }) => fetchOverview(signal),
  })
}

export function useVendorFindings(vendorId: string, params: PageParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: ["vendors", vendorId, "findings", limit, offset],
    queryFn: ({ signal }) => fetchVendorFindings(vendorId, { limit, offset }, signal),
  })
}

export function useVendorChanges(vendorId: string, params: ChangeParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  const since = params.since
  return useQuery({
    queryKey: ["vendors", vendorId, "changes", limit, offset, since ?? null],
    queryFn: ({ signal }) => fetchVendorChanges(vendorId, { limit, offset, since }, signal),
  })
}

export function useFinding(findingId: string) {
  return useQuery({
    queryKey: ["findings", findingId],
    queryFn: ({ signal }) => fetchFinding(findingId, signal),
  })
}

/**
 * How often a live run is re-read, in milliseconds.
 *
 * The critical path through this graph is the customer's own CI run, measured in minutes,
 * so nothing here changes faster than a person can read it. Five seconds is twelve requests
 * a minute against a single-row checkpoint read — cheap enough to leave open on a second
 * monitor, and short enough that a node changing state is visible before a reader wonders
 * whether the screen is stuck.
 */
export const WORKFLOW_POLL_MS = 5_000

/**
 * A run that will not change again. The only terminal signal is a non-null `outcome`.
 *
 * Reading terminality off the nodes instead would be wrong twice: `open_pr` reads `done` on
 * a run that went on to be abandoned, and a run can finish through `report` or `abandon`,
 * neither of which is a node this view renders.
 */
export function isRunTerminal(state: WorkflowState | undefined): boolean {
  return state !== undefined && state.outcome !== null
}

/**
 * The run behind a finding, polled while it is live.
 *
 * `staleTime` is zero because a run in flight is stale the moment it arrives; the default
 * thirty seconds is right for the graph, which only moves when INDEX runs, and wrong here.
 *
 * Polling stops on a terminal outcome and never starts without data, so a 404 costs one
 * request rather than one every interval forever. The consequence is that a finding whose
 * run begins after the page opens is not discovered on its own — the view offers an
 * explicit re-ask for that case rather than paying for it continuously.
 */
export function useWorkflow(findingId: string) {
  return useQuery({
    queryKey: ["findings", findingId, "workflow"],
    queryFn: ({ signal }) => fetchWorkflow(findingId, signal),
    staleTime: 0,
    refetchInterval: (query) =>
      isRunTerminal(query.state.data) || query.state.data === undefined
        ? false
        : WORKFLOW_POLL_MS,
  })
}
