/**
 * One hook per route, so a component names the question and never the URL.
 *
 * Query keys mirror the graph hierarchy, which means invalidating a vendor invalidates
 * everything read under it.
 */

import { useQuery } from "@tanstack/react-query"

import {
  DEFAULT_LIMIT,
  fetchBindingSurface,
  fetchCorpus,
  fetchDetectors,
  fetchFinding,
  fetchOverview,
  fetchRepositories,
  fetchRepositoryCoverage,
  fetchRepositoryObserved,
  fetchRuns,
  fetchVendorChanges,
  fetchVendorFindings,
  fetchWorkflow,
} from "@/api/client"
import type { PageParams } from "@/api/client"
import type { RunsPage, WorkflowState } from "@/api/types"

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

export function useVendorChanges(vendorId: string, params: PageParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: ["vendors", vendorId, "changes", limit, offset],
    queryFn: ({ signal }) => fetchVendorChanges(vendorId, { limit, offset }, signal),
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
 * A run that will not change again.
 *
 * Terminality is read off the outcome and not off the nodes, which would be wrong twice:
 * `open_pr` reads `done` on a run that went on to be abandoned, and a run can finish through
 * `report` or `abandon`, neither of which is a node this view renders.
 *
 * `running` is not terminal. The transport reports null for a run in flight, so this test is
 * belt and braces against a checkpoint value reaching the client: reading it as terminal
 * stops the poll on a live run, which freezes the screen on a stale answer.
 */
export function isRunTerminal(state: WorkflowState | undefined): boolean {
  return state !== undefined && state.outcome !== null && state.outcome !== "running"
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

/**
 * Whether a page of runs still has one in flight.
 *
 * `outcome` is null on a run exactly while it has not reached `opened`, `abandoned` or
 * `reported` — the same test `isRunTerminal` runs against one workflow, applied across a
 * page of them so the fleet stops polling only once every row it can see is done.
 */
function hasLiveRun(page: RunsPage | undefined): boolean {
  return page !== undefined && page.items.some((run) => run.outcome === null)
}

/**
 * Every run the checkpointer holds, one row per thread, newest first.
 *
 * Polls at `WORKFLOW_POLL_MS` while the page holds a run in flight, and stops the moment it
 * does not — the same interval as a single workflow, for the same reason: nothing on this
 * screen changes faster than the customer's own CI run.
 */
export function useRuns(params: PageParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: ["runs", limit, offset],
    queryFn: ({ signal }) => fetchRuns({ limit, offset }, signal),
    refetchInterval: (query) => (hasLiveRun(query.state.data) ? WORKFLOW_POLL_MS : false),
  })
}

/**
 * The repair record, aggregated. Not polled: `migration_outcome` only gains a row when a
 * run finishes an attempt, and the runs poll above already surfaces that a run finished.
 */
export function useCorpus() {
  return useQuery({
    queryKey: ["corpus"],
    queryFn: ({ signal }) => fetchCorpus(signal),
  })
}

/**
 * The `repo_id` roll-up from the index. Not polled, for the same reason as `useCorpus`: it
 * moves only when INDEX runs, which nothing on this screen would tell you had happened
 * sooner than a manual refresh would.
 */
export function useRepositories() {
  return useQuery({
    queryKey: ["repositories"],
    queryFn: ({ signal }) => fetchRepositories(signal),
  })
}

/**
 * Every call site the index holds against one vendor operation, and what the vendor has
 * changed about it. Not polled: this view moves only when INDEX or SIGNAL runs, neither of
 * which this screen would learn about sooner than a manual refresh.
 */
export function useBindingSurface(
  vendorId: string,
  operationId: string,
  params: { repoId?: string } = {},
) {
  return useQuery({
    queryKey: ["bindings", vendorId, operationId, params.repoId ?? null],
    queryFn: ({ signal }) => fetchBindingSurface(vendorId, operationId, params, signal),
  })
}

/**
 * How many indexed call sites one repository has, per vendor. Not polled, for the same reason
 * as `useRepositories`.
 */
export function useRepositoryCoverage(repoId: string) {
  return useQuery({
    queryKey: ["repositories", repoId, "coverage"],
    queryFn: ({ signal }) => fetchRepositoryCoverage(repoId, signal),
  })
}

/** What traffic this repository has shown, what shape it had, and how often it failed. */
export function useRepositoryObserved(repoId: string) {
  return useQuery({
    queryKey: ["repositories", repoId, "observed"],
    queryFn: ({ signal }) => fetchRepositoryObserved(repoId, signal),
  })
}

/** Every open finding, aggregated by the detector that raised it. */
export function useDetectors() {
  return useQuery({
    queryKey: ["detectors"],
    queryFn: ({ signal }) => fetchDetectors(signal),
  })
}
