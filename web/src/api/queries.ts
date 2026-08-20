/**
 * One hook per route, so a component names the question and never the URL.
 *
 * Query keys mirror the graph hierarchy, which means invalidating a vendor invalidates
 * everything read under it.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

import {
  DEFAULT_LIMIT,
  fetchAdapters,
  fetchBindingSurface,
  fetchChangeUnits,
  fetchCorpus,
  fetchDetectors,
  fetchDismissal,
  fetchFinding,
  fetchOverview,
  fetchRepositories,
  fetchRepositoryCoverage,
  fetchRepositoryObserved,
  fetchRuns,
  fetchAbandonment,
  fetchFindingsOverTime,
  fetchVendorChangeVolume,
  fetchVendorChanges,
  fetchVendorOperations,
  fetchVendorFindings,
  fetchWorkspaceFindings,
  fetchPatch,
  fetchRunActivity,
  fetchWorkflow,
  fetchRepositoryGraph,
} from "@/api/client"
import { createTicket, fetchTickets } from "@/features/tickets/api"
import type {
  BindingSurfaceParams,
  ChangeUnitsParams,
  ObservedTelemetryParams,
  PageParams,
  VendorFindingsParams,
} from "@/api/client"
import type { RunsPage, WorkflowState } from "@/api/types"

/**
 * Open findings by vendor and by severity, for one repository or for the fleet.
 *
 * `repoId` is part of the query key rather than only of the request. Two scopes are two
 * answers, and a shared key would serve one repository's figures from the other's cache — the
 * false claim this scoping exists to remove, arriving through the cache instead of the wire.
 */
export function useOverview(repoId?: string) {
  return useQuery({
    queryKey: ["overview", repoId ?? null],
    queryFn: ({ signal }) => fetchOverview({ repoId }, signal),
  })
}

/**
 * Open findings for one vendor, in the scope and under the filters the URL asks for.
 *
 * All four narrowings are in the query key, so each is a new question rather than a re-render of
 * the old answer — leaving any of them out would let the cache serve a wider page under a
 * narrower URL, which is the one failure a scope or a filter must never have.
 */
export function useVendorFindings(vendorId: string, params: VendorFindingsParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  const severity = params.severity
  const path = params.path
  // The ordering is part of the key for the same reason `repoId` is: two orderings of one set are
  // two different pages, and a shared key would serve the severity-ordered page's rows under the
  // default ordering's name straight out of the cache.
  const order = params.order
  return useQuery({
    queryKey: [
      "vendors",
      vendorId,
      "findings",
      params.repoId ?? null,
      limit,
      offset,
      severity ?? null,
      path ?? null,
      order ?? null,
    ],
    queryFn: ({ signal }) =>
      fetchVendorFindings(
        vendorId,
        { limit, offset, repoId: params.repoId, severity, path, order },
        signal,
      ),
  })
}

/**
 * Every open finding in one workspace.
 *
 * The key carries the workspace and all three narrowings for the reason `useVendorFindings`'s
 * does: two orderings of one set are two different pages, and a shared key would serve one
 * ordering's rows under the other's name straight out of the cache.
 */
export function useWorkspaceFindings(repoId: string, params: VendorFindingsParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: [
      "repositories",
      repoId,
      "findings",
      limit,
      offset,
      params.severity ?? null,
      params.path ?? null,
      params.order ?? null,
    ],
    queryFn: ({ signal }) =>
      fetchWorkspaceFindings(
        repoId,
        { limit, offset, severity: params.severity, path: params.path, order: params.order },
        signal,
      ),
  })
}

export function useFindingsOverTime(repoId: string | null) {
  return useQuery({
    queryKey: ["findings", "over-time", repoId],
    queryFn: ({ signal }) => fetchFindingsOverTime(repoId, signal),
  })
}

export function useAbandonment() {
  return useQuery({
    queryKey: ["corpus", "abandonment"],
    queryFn: ({ signal }) => fetchAbandonment(signal),
  })
}

export function useVendorOperations(vendorId: string, repoId: string | null) {
  return useQuery({
    queryKey: ["vendors", vendorId, "operations", repoId],
    queryFn: ({ signal }) => fetchVendorOperations(vendorId, repoId, signal),
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
/**
 * The patch for one finding.
 *
 * No polling. A diff does not change while a reader looks at it: the patch node writes once
 * per generation, and a run that produces a second one is a second generation with its own
 * page. The workflow beside it polls because its verdicts do move.
 */
export function usePatch(findingId: string) {
  return useQuery({
    queryKey: ["findings", findingId, "patch"],
    queryFn: ({ signal }) => fetchPatch(findingId, signal),
  })
}

/**
 * A finding's dismissal standing.
 *
 * Not gated on `useFinding`, deliberately: `finding_dismissal` outlives the re-derived `finding`
 * row, so this answers for a finding whose own route 404s. It does not poll -- nothing in the
 * console writes a dismissal, so there is no change for a poll to catch.
 */
export function useDismissal(findingId: string) {
  return useQuery({
    queryKey: ["findings", findingId, "dismissal"],
    queryFn: ({ signal }) => fetchDismissal(findingId, signal),
  })
}

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
 * The agent-activity feed for one finding's run. `staleTime` is zero for the reason
 * `useWorkflow`'s is; the caller owns the cadence through `refetchIntervalMs` because this
 * hook cannot see the run's outcome and must not invent a liveness rule of its own.
 */
export function useRunActivity(
  repoId: string,
  findingId: string,
  options: { refetchIntervalMs?: number | false } = {},
) {
  return useQuery({
    queryKey: ["findings", findingId, "activity"],
    queryFn: ({ signal }) => fetchRunActivity(repoId, findingId, signal),
    staleTime: 0,
    refetchInterval: options.refetchIntervalMs ?? false,
  })
}

/**
 * Whether a page of runs still has one in flight.
 *
 * `outcome` is null on a run exactly while it has not reached `opened`, `abandoned` or
 * `reported` — the same test `isRunTerminal` runs against one workflow, applied across a
 * page of them so the fleet stops polling only once every row it can see is done.
 */
export function hasLiveRun(page: RunsPage | undefined): boolean {
  return page !== undefined && page.items.some((run) => run.outcome === null)
}

/**
 * Every run the checkpointer holds, one row per thread, newest first.
 *
 * Polls at `WORKFLOW_POLL_MS` while the page holds a run in flight, and stops the moment it
 * does not — the same interval as a single workflow, for the same reason: nothing on this
 * screen changes faster than the customer's own CI run.
 */
export function useRuns(params: PageParams & { outcome?: string | null } = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  const outcome = params.outcome ?? null
  return useQuery({
    queryKey: ["runs", limit, offset, outcome],
    queryFn: ({ signal }) => fetchRuns({ limit, offset, outcome }, signal),
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
 * Open findings grouped by the vendor change and operation that produced them, fleet-wide or
 * for one repository. `repoId` is part of the query key for the same reason `useOverview`'s
 * is: two scopes are two groupings, and a shared key would serve one repository's units from
 * the other's cache.
 *
 * Not polled: this grouping moves when SIGNAL runs or a remediation run reaches a new
 * checkpoint, neither of which this screen would learn about sooner than a manual refresh —
 * the same call `useRepositories` and `useCorpus` make.
 */
export function useChangeUnits(params: ChangeUnitsParams = {}) {
  const limit = params.limit ?? DEFAULT_LIMIT
  const offset = params.offset ?? 0
  return useQuery({
    queryKey: ["change-units", params.repoId ?? null, params.severity ?? null, limit, offset],
    queryFn: ({ signal }) =>
      fetchChangeUnits(
        { repoId: params.repoId, severity: params.severity, limit, offset },
        signal,
      ),
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
  params: BindingSurfaceParams = {},
) {
  return useQuery({
    queryKey: [
      "bindings",
      vendorId,
      operationId,
      params.repoId ?? null,
      params.pathPrefix ?? null,
      params.callSitesOffset ?? 0,
      params.changesOffset ?? 0,
    ],
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

/**
 * This repository's call sites and the vendors they reach. Not polled, for the same reason
 * `useRepositoryCoverage` is not: the index moves when a pass runs, not on a timer.
 */
export function useRepositoryGraph(repoId: string) {
  return useQuery({
    queryKey: ["repositories", repoId, "graph"],
    queryFn: ({ signal }) => fetchRepositoryGraph(repoId, signal),
  })
}

/** What traffic this repository has shown, what shape it had, and how often it failed. */
export function useRepositoryObserved(repoId: string, params: ObservedTelemetryParams = {}) {
  return useQuery({
    queryKey: [
      "repositories",
      repoId,
      "observed",
      params.callsOffset ?? 0,
      params.shapesOffset ?? 0,
      params.errorWindowsOffset ?? 0,
    ],
    queryFn: ({ signal }) => fetchRepositoryObserved(repoId, params, signal),
  })
}

/**
 * Every open finding, aggregated by the detector that raised it — for one repository, or for
 * the fleet when `repoId` is absent. Keyed by scope for the reason `useOverview` is.
 */
export function useDetectors(repoId?: string) {
  return useQuery({
    queryKey: ["detectors", repoId ?? null],
    queryFn: ({ signal }) => fetchDetectors({ repoId }, signal),
  })
}

/**
 * Every adapter this deployment registers, and what each has ever delivered.
 *
 * Not polled. This view moves when a scan writes a `vendor_change` row or when somebody edits the
 * deployment's vendor configuration, and neither is something this screen would learn about sooner
 * than a manual refresh would — the same call `useRepositories` and `useCorpus` make.
 */
export function useAdapters() {
  return useQuery({
    queryKey: ["adapters"],
    queryFn: ({ signal }) => fetchAdapters(signal),
  })
}

/** One vendor's whole change history, aggregated by the API rather than by whichever page loaded. */
export function useVendorChangeVolume(vendorId: string) {
  return useQuery({
    queryKey: ["vendor-change-volume", vendorId],
    queryFn: ({ signal }) => fetchVendorChangeVolume(vendorId, signal),
  })
}

/**
 * One repository's remediation tickets, newest first. Polls while mounted for the same reason
 * the Telemetry page does: a ticket's whole point is that its status moves while a reader
 * watches, and the stamp of when the console last asked is the honest form of "live".
 */
export function useTickets(
  repoId: string,
  source: "operator" | "watch" | null = null,
  options: { refetchIntervalMs?: number } = {},
) {
  return useQuery({
    queryKey: ["repositories", repoId, "tickets", source ?? "all"],
    queryFn: ({ signal }) => fetchTickets(repoId, source, signal),
    refetchInterval: options.refetchIntervalMs ?? false,
  })
}

/**
 * The console's one write into remediation. Invalidates every ticket read for the repository
 * on success, so the row the POST returned is also the row every open screen shows.
 */
export function useCreateTicket(repoId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (findingId: string) => createTicket(findingId),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["repositories", repoId, "tickets"] })
    },
  })
}
