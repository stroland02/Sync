/**
 * The shapes `src/sync/api/app.py` returns, written from the Python responses.
 *
 * The provenance envelope is declared once and the item type is a parameter. Restating
 * four provenance fields per response is four places to edit when the envelope moves.
 */

/**
 * Which rung of evidence produced a binding.
 *
 * Mirrors `FindingRung` in `sync.core.models`: `static` is read out of source, `resolved`
 * is a static read plus a resolution step, `observed` is correlated from watched traffic,
 * `unresolved` is the named absence of a binding, and `unattributed` is a row written
 * before the column existed.
 */
export type BindingSource =
  | "static"
  | "resolved"
  | "observed"
  | "unresolved"
  | "unattributed"

/**
 * On every payload the API returns.
 *
 * `binding_source` is null when the answer rests on no single binding — either the payload
 * holds no binding at all, or the page mixes rungs. Null is a fact, not a missing value,
 * and every render site is required to say which fact it means.
 *
 * `context_savings` is required. `/api/overview` used to compose its payload by hand and drop
 * the field; it now forwards the figure from the `whats_at_risk` page it already reads, so
 * every route carries it the same way the other four always have.
 */
export interface Provenance {
  indexed_at: string | null
  feed_fetched_at: string | null
  binding_source: BindingSource | null
  context_savings: number
}

/** A paginated answer. `next_offset` is null on the last page — an offset that always exists is a loop. */
export interface Page<T> extends Provenance {
  items: T[]
  total: number
  next_offset: number | null
}

/** `GET /api/overview` — one entry per vendor the open findings name. */
export interface VendorSummary {
  vendor_id: string
  open_finding_count: number
}

/**
 * `GET /api/overview`.
 *
 * Not a `Page`: the route reports its own `total_findings` and carries no `items`,
 * `total` or `next_offset`.
 */
export interface OverviewResponse extends Provenance {
  vendors: VendorSummary[]
  total_findings: number
}

/**
 * One item of `GET /api/vendors/{vendor_id}`: a call site an open finding touches.
 *
 * `binding_source` here is per row and is never null — it is the rung of this finding,
 * and it is the one to weigh the row by. The envelope's field describes the page.
 */
export interface RiskRow {
  file: string
  line: number
  symbol: string | null
  operation: string | null
  vendor: string
  change_kind: string | null
  severity: string
  finding_id: string
  binding_source: BindingSource
}

/** One item of `GET /api/vendors/{vendor_id}/changes`: something the vendor changed. */
export interface VendorChangeRow {
  operation: string | null
  change_kind: string
  path_ptr: string | null
  severity: string
  from_version: string | null
  to_version: string | null
  published_at: string
}

/** A change naming a call site, returned shallow — the full record is fetched by id. */
export interface KnownChange {
  change_id: string
  kind: string
  severity: string
}

/**
 * The finding the URL names, carried beside the call site it points at.
 *
 * `binding_source` here is that one finding's rung and is never null — it is a column on
 * the row. The envelope's field on the same payload describes the answer as a whole and
 * goes null when two detectors name this call site by different rungs, which is exactly
 * when this one still has something definite to say.
 */
export interface FindingIdentity {
  finding_id: string
  binding_source: BindingSource
}

/** `GET /api/findings/{finding_id}` — one binding in full. */
export interface FindingDetail extends Provenance {
  finding: FindingIdentity
  symbol: string | null
  operation: string | null
  vendor: string
  args_keys: string[]
  response_fields_read: string[]
  sdk_version: string | null
  known_changes: KnownChange[]
}

/** The 404 body. A finding that is not open is an answer, so the API names the identifier. */
export interface NotFoundBody {
  error: string
  identifier: string
}

/**
 * Where a node stands the last time the checkpointer wrote.
 *
 * `current` is the node the graph owes a visit, which is not the same as "has never run":
 * a `patch` that failed verification and looped back is due again and reads as `current`
 * even though it already ran once. Preferring the later status would render a retry as
 * progress.
 */
export type WorkflowNodeStatus = "done" | "current" | "pending"

/**
 * How a run ended, or `running` while it has not.
 *
 * The transport reports null for a run in flight, and null is the signal to poll. `running`
 * is carried here because it is a value of `sync.remediate.state.Outcome` that a checkpoint
 * genuinely holds — `locate` writes it on the first hop of every run — so a transport that
 * stopped filtering it would send a value this type had no branch for. Only the three
 * terminal values end a run.
 *
 * `abandon_reason` is meaningful under `abandoned` alone, and `report_reason` under `reported`
 * alone; on any other outcome each is whatever the channel happened to hold and means nothing.
 */
export type WorkflowOutcome = "opened" | "abandoned" | "reported" | "running"

/**
 * One node of the remediation graph.
 *
 * `evidence` carries only the keys the run actually produced, so a missing key is "not
 * produced" and a present key holding null is "produced, and null". The two render
 * differently and must not be collapsed.
 */
export interface WorkflowNode {
  name: string
  status: WorkflowNodeStatus
  evidence: Record<string, unknown>
}

/**
 * `GET /api/workflows/{finding_id}`.
 *
 * Deliberately not a `Provenance`: this route reads the LangGraph checkpointer tables and
 * every other route reads the graph. They are two databases, so there is no `indexed_at`
 * or `binding_source` to report, and inheriting the envelope would invent four fields the
 * transport never sends.
 *
 * `nodes` always arrives in the remediation graph's own order, named below by
 * `WORKFLOW_NODE_ORDER`, and the view renders that order rather than sorting it.
 *
 * `thread_id` names the one run this payload describes — `{finding_id}:{run_id or
 * head_sha[:12]}:{generation}`, the convention `sync.dashboard.queries`'s module docstring
 * records. `generation_count` is how many threads the checkpointer holds for this finding;
 * this route always answers with the newest, so a finding retried across generations has
 * `generation_count` threads and this payload is only one of them. `sync.dashboard.fleet.runs`
 * is the query that lists every generation as its own row, which is why a reader who wants
 * the others goes there rather than to a link this route cannot serve.
 */
export interface WorkflowState {
  nodes: WorkflowNode[]
  outcome: WorkflowOutcome | null
  abandon_reason: string | null
  report_reason: string | null
  thread_id: string
  generation_count: number
}

/**
 * The remediation graph's node order, mirroring `WORKFLOW_NODES` in `sync.dashboard.queries`.
 *
 * `nodes` on `WorkflowState` already arrives in this order — the transport does not sort —
 * so this array is not needed to render the sequence. It exists so a file that names every
 * node, such as `PURPOSE` in `node-sequence.tsx`, has a real set to be checked against
 * rather than retyping eight strings a second time.
 */
export const WORKFLOW_NODE_ORDER = [
  "locate",
  "prepare",
  "patch",
  "static_verify",
  "replay",
  "push_branch",
  "await_ci",
  "open_pr",
] as const

/** One of the remediation graph's known node names. */
export type WorkflowNodeName = (typeof WORKFLOW_NODE_ORDER)[number]

/**
 * A run's outcome, once it has one.
 *
 * Mirrors `_FINISHED` in `sync.dashboard.queries`, the tuple `/api/runs` filters a
 * checkpoint's `outcome` channel through before it reaches the transport. Unlike
 * `WorkflowOutcome` above, this type carries no `"running"` member: the fleet route never
 * forwards that value, so there is nothing here for a branch on it to handle. A value added
 * to `_FINISHED` and not here is a real outcome the console cannot express — held together
 * by `tests/test_api_routes.py::test_the_consoles_run_disposition_matches_the_finished_outcomes`,
 * since nothing else keeps the two languages agreeing.
 */
export type RunDisposition = "opened" | "abandoned" | "reported"

/**
 * One run the checkpointer holds: the newest checkpoint on one thread.
 *
 * `thread_id` is `{finding_id}:{run_id or head_sha}:{generation}`, so a finding retried
 * across generations is two rows here, one per generation — this row is per-run, not
 * per-finding, and does not collapse the way `WorkflowState` does for a single finding.
 *
 * `current_node` is non-null exactly when `outcome` is null: it names the node the graph
 * owes a visit, which only means something while the run has not yet finished. It is typed
 * as a plain string rather than `WorkflowNodeName` because a pending run can also be due at
 * `report` or `abandon`, which end a run rather than advance it and are not in
 * `WORKFLOW_NODE_ORDER`.
 *
 * `last_checkpoint_at` is the checkpoint's own `ts` — staleness, not liveness. See the
 * fleet screen's legend for why silence here does not mean the run has died.
 */
export interface RunRow {
  thread_id: string
  finding_id: string
  current_node: string | null
  outcome: RunDisposition | null
  abandon_reason: string | null
  last_checkpoint_at: string | null
}

/**
 * `GET /api/runs`.
 *
 * Deliberately not a `Page<T>`: `Page` extends `Provenance`, and this route reads the
 * LangGraph checkpointer, not the graph — there is no `indexed_at`, no `feed_fetched_at`,
 * no binding rung and no context-savings figure to report for it. Inheriting the envelope
 * would invent four fields the transport never sends, the same reasoning that keeps
 * `WorkflowState` off `Provenance`. `items`, `total` and `next_offset` are the whole shape.
 */
export interface RunsPage {
  items: RunRow[]
  total: number
  next_offset: number | null
}

/**
 * One count per distinct value of a `migration_outcome` column.
 *
 * The key `"null"` is not the string form of an empty bucket — `sync.dashboard.fleet`
 * writes it for a row whose column genuinely holds `NULL`, so dropping it would understate
 * the denominator by exactly the attempts that column was never recorded for.
 */
export type Tally = Record<string, number>

/**
 * `GET /api/corpus` — the repair record, aggregated.
 *
 * `attempts` and `distinct_findings` are separate fields on purpose: `sync.remediate.corpus`
 * writes one `migration_outcome` row per attempt, so a finding retried three times is three
 * attempts and one finding. A payload that reported one number for both would be the grain
 * defect `CLAUDE.md` names for this table.
 *
 * The count behind every field here excludes three abandonment classes `corpus._record`
 * never writes a row for: a run abandoned before any attempt (at `locate` or `prepare`), a
 * run for which no tier applied, and a run whose state was missing its finding, site or
 * change. Those runs are real — `/api/runs` still names them through `abandon_reason` — but
 * a row for them here would be a fabrication, not a measurement.
 */
export interface CorpusSummary {
  attempts: number
  distinct_findings: number
  by_terminal_status: Tally
  by_strategy: Tally
  by_tier: Tally
}

/**
 * `GET /api/repositories`.
 *
 * `repo_ids` names every repository the index has seen at least one call site from. A
 * repository that was configured but never indexed writes no `call_site` row and has no
 * entry here — indistinguishable from one that was never configured at all.
 */
export interface RepositoriesResponse {
  repo_ids: string[]
}

/**
 * One call site `GET /api/vendors/{vendor_id}/operations/{operation_id}/bindings` reports.
 *
 * `binding_rung` is always `"static"` here — a call site is what the static index found, and
 * nothing about this row rests on a resolution or a correlation step. A stronger rung for the
 * same operation, when traffic has been observed calling it, is a fact about the repository's
 * telemetry (`ObservedCallRow.binding_rung`), never blended into this row.
 */
export interface BindingCallSite {
  repo_id: string
  path: string
  line: number
  col: number
  symbol: string | null
  sdk_version: string | null
  args_keys: string[]
  response_fields_read: string[]
  loop_depth: number
  binding_rung: BindingSource
  indexed_at: string
  retracted_at: string | null
}

/** One vendor change `GET .../bindings` reports, already filtered to the operation the URL names. */
export interface BindingChange {
  change_id: string
  kind: string
  severity: string
  from_version: string | null
  to_version: string | null
  path_ptr: string | null
  detected_at: string
}

/**
 * `GET /api/vendors/{vendor_id}/operations/{operation_id}/bindings`.
 *
 * Not a `Provenance`: this route reads `sync.dashboard.graph_views`, never `GraphSurface`, and
 * carries no feed-fetch timestamp and no context-savings figure — inheriting the envelope would
 * invent two fields the transport never sends, the reasoning that already keeps `WorkflowState`
 * and `RunsPage` off it. `repo_id` here is the filter the request was made with, not a fact
 * about the answer: null when the caller asked for every repository.
 */
export interface BindingSurfaceResponse {
  vendor_id: string
  operation_id: string
  repo_id: string | null
  call_sites: BindingCallSite[]
  changes: BindingChange[]
}

/**
 * `GET /api/repositories/{repo_id}/coverage`.
 *
 * `by_vendor` names only a vendor with at least one indexed call site — a vendor absent from
 * this object is not "zero", it is a question this route cannot answer: whether the indexer
 * looked and found nothing, or nothing declares which package to look for. `last_indexed`
 * shares that same key set by construction (`sync.dashboard.graph_views.index_coverage` builds
 * both from one `GraphStore.call_site_coverage` read) and is the newest `indexed_at` among that
 * vendor's call sites — staleness, not a promise the index is current: a repository re-scanned
 * weeks ago reports the same value every day after, until another re-index moves it.
 */
export interface IndexCoverageResponse {
  repo_id: string
  by_vendor: Tally
  last_indexed: Record<string, string>
  total_call_sites: number
}

/**
 * One row of `GET /api/repositories/{repo_id}/observed`'s `calls`: one unit of work's use of
 * one vendor operation. Every derived count — `call_count`, `distinct_targets`,
 * `repeated_calls`, `max_resend_count`, `error_count` — is `ObservedCall`'s own property on the
 * Python side, not recomputed here.
 *
 * `operation_id` is `""` and `binding_rung` is `"unresolved"` for a request nothing could
 * attribute to an operation — a named absence, not a missing value.
 */
export interface ObservedCallRow {
  repo_id: string
  vendor_id: string
  operation_id: string
  binding_rung: BindingSource
  server_address: string
  http_method: string
  trace_id: string
  url_template: string
  call_count: number
  distinct_targets: number
  repeated_calls: number
  max_resend_count: number
  error_count: number
  first_seen: string
  last_seen: string
}

/** One row of `.../observed`'s `shapes`: what one vendor operation's traffic has looked like. */
export interface ObservedShapeRow {
  vendor_id: string
  operation_id: string
  field_path: string
  json_type: string
  nullable_seen: boolean
  spec_enum_values: string[]
  source: string
  sample_count: number
  first_seen: string
  last_seen: string
}

/**
 * One row of `.../observed`'s `error_windows`. `error_count` has no denominator in this table —
 * the schema's own grain note — and this row does not invent one.
 */
export interface ObservedErrorWindowRow {
  repo_id: string
  vendor_id: string
  operation_id: string
  binding_rung: BindingSource
  source: string
  status_class: string
  window_start: string
  window_end: string
  error_count: number
  issue_count: number
}

/**
 * `GET /api/repositories/{repo_id}/observed`.
 *
 * Not a `Provenance`, for the same reason `BindingSurfaceResponse` is not: this route reads
 * `sync.dashboard.graph_views` and carries no feed-fetch timestamp or context-savings figure.
 */
export interface ObservedTelemetryResponse {
  repo_id: string
  calls: ObservedCallRow[]
  shapes: ObservedShapeRow[]
  error_windows: ObservedErrorWindowRow[]
}

/**
 * One detector's roll-up in `GET /api/detectors`: how many open findings, at which rungs, with
 * what claims and severities.
 */
export interface DetectorRow {
  detector: string
  total: number
  by_rung: Tally
  by_claim: Tally
  by_severity: Tally
}

/**
 * `GET /api/detectors`.
 *
 * Scoped to open findings, the only findings read `GraphStore` offers: a closed finding is
 * invisible here exactly as it is everywhere else in the console today. Not a `Provenance`,
 * for the same reason as the other two graph views above.
 */
export interface DetectorAccountabilityResponse {
  detectors: DetectorRow[]
  total_open_findings: number
}
