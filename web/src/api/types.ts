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
 */
export interface WorkflowState {
  nodes: WorkflowNode[]
  outcome: WorkflowOutcome | null
  abandon_reason: string | null
  report_reason: string | null
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
