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
 *
 * An array rather than a bare union because the order is load-bearing: the rung composition
 * chart assigns one categorical series slot per member by position, so a member added in the
 * middle repaints every existing bar's colours without changing a count.
 * `tests/test_api_routes.py::test_the_consoles_rung_vocabulary_matches_the_models_in_order`
 * holds it against `sync.core.models`, which is the only thing that can — the console cannot
 * import Python, and nothing in TypeScript knows this list is a restatement.
 */
export const BINDING_SOURCES = [
  "static",
  "resolved",
  "observed",
  "unresolved",
  "unattributed",
] as const

export type BindingSource = (typeof BINDING_SOURCES)[number]

/**
 * On every payload the API returns.
 *
 * `binding_source` is null when the answer rests on no single binding — either the payload
 * holds no binding at all, or the page mixes rungs. Null is a fact, not a missing value,
 * and every render site is required to say which fact it means.
 *
 * `context_savings` is required. It is read straight from `sync.dashboard` on every route now
 * — `/api/overview` no longer composes its payload from the `whats_at_risk` page `app.py`'s own
 * history describes; `overview_summary`'s docstring carries what replaced it.
 *
 * `context_savings_bound_reached` is optional and false-shaped absent: only a route whose
 * `context_savings` can be derived from a bounded scan sets it, `/api/overview` today
 * (`sync.dashboard.graph_views.overview_summary`). Every other route's `context_savings` is an
 * exact figure over the page it actually read, so leaving the field `undefined` there is not a
 * gap in the payload — a render site that has never heard of the flag renders the number
 * unqualified and is not wrong, because it never lies for a route this flag was not written
 * for. A render site that does check it must never show `context_savings` as an exact number
 * once this is `true`.
 */
export interface Provenance {
  indexed_at: string | null
  feed_fetched_at: string | null
  binding_source: BindingSource | null
  context_savings: number
  context_savings_bound_reached?: boolean
}

/** A paginated answer. `next_offset` is null on the last page — an offset that always exists is a loop. */
export interface Page<T> extends Provenance {
  items: T[]
  total: number
  next_offset: number | null
}

/**
 * A paginated set with no page-level provenance of its own.
 *
 * `sync.dashboard.graph_views._page` builds this shape for every set `binding_surface` and
 * `observed_telemetry` page: `{items, total, next_offset}`, nothing else. Those two routes
 * carry no feed-fetch timestamp or context-savings figure to fill `Page<T>`'s `Provenance`
 * half with — `BindingSurfaceResponse` and `ObservedTelemetryResponse` say why in their own
 * docstrings — so this is the bare envelope rather than `Page<T>` with fields invented to
 * satisfy the type.
 */
export interface ItemPage<T> {
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
 *
 * `total_findings` is a `count(*)` over a subquery Postgres stops scanning at
 * `total_findings_bound` (`sync.dashboard.graph_views.overview_summary`, mirroring Sentry's
 * `count_hits`/`MAX_HITS_LIMIT`) — past the bound it is a floor, not the population, and
 * `total_findings_bound_reached` is the fact that says so. A render site that shows
 * `total_findings` without checking `total_findings_bound_reached` is claiming an exact count
 * the transport did not produce.
 *
 * `vendors` and `severity_counts` are each their own unbounded `GROUP BY` over every open
 * finding — never derived from the bounded total above, and never truncated at
 * `total_findings_bound`. That is deliberate: a distribution truncated at the same ceiling as
 * the count would be the distribution of whichever rows the ordering reached, not of the
 * population, so past the bound their sum legitimately exceeds `total_findings`.
 *
 * This route always sets `context_savings_bound_reached` (never leaves it `undefined`):
 * `context_savings` here is `total_findings * a constant`, so it inherits the same truncation
 * `total_findings_bound_reached` names. A render site that shows this card's `context_savings`
 * without checking the flag is the exact defect `total_findings_bound_reached` exists to catch,
 * one field over.
 */
export interface OverviewResponse extends Provenance {
  /**
   * The repository this answer was computed for, or `null` for the whole fleet. The transport
   * echoes the scope back rather than leaving a screen to remember which one it asked for: a
   * fleet-wide figure rendered under a repository's name is a false claim about that
   * repository, and a payload that names its own scope cannot make it silently.
   */
  repo_id: string | null
  vendors: VendorSummary[]
  total_findings: number
  total_findings_bound: number
  total_findings_bound_reached: boolean
  severity_counts: Tally
  /**
   * Open findings tallied by the rung their binding was established at — dashboard 2's source.
   *
   * **Every rung in `BINDING_SOURCES` is present, including at nought.** A rung missing from the
   * object and a rung at zero are different claims, and a stacked bar cannot tell them apart, so
   * the whole closed vocabulary is always reported.
   *
   * **Unbounded, unlike `total_findings` beside it.** A distribution derived from a bounded page
   * is the distribution of whichever rows the ordering reached rather than of the population, so
   * this is never truncated even when `total_findings_bound_reached` is true.
   *
   * Not derived from `binding_source`, and it does not derive it: that field is the one rung
   * every open finding shares, or `null` when they disagree, which is a different fact.
   */
  bindings_by_rung: Record<BindingSource, number>
  /**
   * The last index pass over this repository, or `null` when it has never been indexed.
   *
   * **`null` is never-indexed, and it is not a pass that found nothing** — that is a `completed`
   * row with `call_sites` of 0. Decision 41 needs this on the Overview because a toast may
   * announce "Index finished, 1,204 call sites" but must never be the only place the fact lives.
   *
   * `null` on the fleet scope too: a pass belongs to one repository, and promoting one
   * repository's pass to stand for all of them is the attribution this console refuses.
   */
  last_index_run: IndexRunSummary | null
}

/** One index pass, as the Overview reads it. */
export interface IndexRunSummary {
  started_at: string | null
  /** `null` while the pass is still going. Not the same as a pass that failed. */
  finished_at: string | null
  /**
   * `null` while in flight — the fourth state beside completed, failed and absent. A reader
   * meeting a stale `null` here knows the pass never reached a terminal state, which is
   * different from one that reached `failed`.
   */
  outcome: "completed" | "failed" | "abandoned" | null
  /**
   * What the pass wrote. `null` unless it completed: a partial count is not a smaller count, and
   * a number here would be read as the size of the codebase.
   */
  call_sites: number | null
}

/**
 * One item of `GET /api/vendors/{vendor_id}`: a call site an open finding touches.
 *
 * `binding_source` here is per row and is never null — it is the rung of this finding,
 * and it is the one to weigh the row by. The envelope's field describes the page.
 */
export interface RiskRow {
  /**
   * The finding's display name — `stripe-postcharges-4b1c9e`.
   *
   * Derived in the payload by `sync.core.naming.finding_name`, never here: this table, the CLI
   * and a pull-request body must call one finding by one name, and three derivations is where
   * they would start to differ. `finding_id` stays the addressable thing.
   */
  name: string
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

/**
 * `GET /api/vendors/{vendor_id}`: the API Services level's page of open findings, the scope it
 * was computed in, and the severities that scope holds.
 *
 * A `Page<RiskRow>` that also names the scope it was computed in. `repo_id` is `null` when the
 * page spans every repository the index has seen, and the repository's own id when the caller
 * narrowed it — `sync.dashboard.graph_views.vendor_findings` carries why the transport echoes
 * it back rather than trusting a screen to remember what it asked for.
 *
 * `GET /api/vendors/{vendor_id}/changes` deliberately has no counterpart field: what a vendor
 * published is a fact about the vendor, true whether or not any repository calls it, so there
 * is no repository scope for it to be in.
 *
 * `severity_counts` is the option list the severity filter is built from. It is scoped to that
 * same repository and to the vendor, and to nothing else: `sync.api.app.vendor_detail` reads it
 * without the severity or path currently selected, because an option list narrowed by the
 * filter it sets collapses to that one value and leaves no way back to the others. So it does
 * not agree with `total` above whenever a filter is on, and it is not supposed to — `total` is
 * the filtered page's denominator and this is the unfiltered breakdown of the same scope. A
 * screen rendering both says which is which.
 *
 * `severity_total` is that scope's own count, read as a second SQL aggregate rather than summed
 * from `severity_counts`: two numbers that cannot contradict each other are two numbers that can
 * never reveal one of them is wrong.
 */
/**
 * How a page of findings is ordered. Named orderings rather than column names, because a control
 * that sorts by whatever a header holds would offer to rank the provenance rung — an evidence
 * class with no good end — and to sort a codebase alphabetically and call it a priority.
 *
 * `sync.graph.store.FINDING_ORDERS` is the authority and
 * `test_the_consoles_finding_order_matches_the_orderings_the_store_offers` holds this list to it,
 * the same way `RunDisposition` is held to `_FINISHED`: the console cannot import Python, so a
 * value added on one side and forgotten here would reach the console as a string the compiler
 * never checked.
 */
export type FindingOrder = "first-seen" | "severity"

export interface VendorFindingsPage extends Page<RiskRow> {
  repo_id: string | null
  severity_counts: Tally
  severity_total: number
  /**
   * The ordering the query actually applied — not the one the URL asked for. An unrecognised
   * `order` resolves server-side and comes back as what was used, so the screen can never name an
   * ordering the rows are not in.
   */
  order: FindingOrder
  /**
   * The severity rank the `severity` ordering uses, most severe first, sent rather than restated
   * here. It is a declared judgement rather than something the graph stores, so the screen states
   * it — and stating a copy would eventually state the wrong one.
   */
  severity_order: string[]
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
  severity: string | null
  file: string
  line: number
  repo_id: string | null
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
  /** Whether this deployment serves index-captured source windows (SYNC_SERVE_SOURCE). */
  source_served: boolean
  /**
   * The captured window around the finding's call site, or `null`: under `source_served: false`
   * it is withheld by policy; under `true` it means no index pass has captured this row yet.
   */
  call_site_source: { snippet: string; snippet_start_line: number; line: number } | null
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
 * Where a node stands, mirroring `NODE_STANDINGS` in `sync.dashboard.queries`.
 *
 * `status` alone means different things depending on two facts outside the node: a `current`
 * node that has already produced evidence is a retry rather than a first visit, and a
 * `pending` node on a finished run will never be reached rather than not yet. Both joins used
 * to be made in the console, separately, by two components that then disagreed about the same
 * payload. The transport makes them once — `tests/test_dashboard_queries.py` holds the answer,
 * which nothing in `web/` can — and this console renders one label per value.
 *
 * Nothing here is a liveness claim. `due` says the graph owes the node a visit; a run parked
 * on the customer's CI and a run that has died write the same nothing into a checkpoint.
 */
export const NODE_STANDINGS = [
  "ran",
  "due",
  "due_again",
  "not_reached_yet",
  "never_reached",
] as const

export type NodeStanding = (typeof NODE_STANDINGS)[number]

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
  standing: NodeStanding
  evidence: Record<string, unknown>
  first_seen_at?: string | null
  last_seen_at?: string | null
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
/** One generation of a finding's remediation runs. */
export interface GenerationSummary {
  thread_id: string
  generation: number
  outcome: WorkflowOutcome | null
  abandon_reason: string | null
  report_reason: string | null
}

/**
 * The patch a run wrote, and the place it went.
 *
 * Owner decision 47: the two travel together. A diff on its own is the shape a reader
 * mistakes for a change that has already landed in their repository, and `target` is the
 * only thing on this payload that says otherwise.
 *
 * `diff` is null when the run produced no patch, and `absent_because` then carries which
 * kind of nothing it is -- a run that decided against a patch, one that gave up, and one
 * still working are three different facts and the console must not print one sentence for
 * all three. Exactly one of `diff` and `absent_because` is non-null.
 */
export interface PatchTarget {
  repo_id: string | null
  /** Written by `push_branch`. Null means the patch was never pushed, which is a different
   *  fact from a patch that does not exist -- and both can be true at once. */
  branch: string | null
  pr_url: string | null
  pr_number: number | null
}

export interface PatchStat {
  files_changed: number
  lines_added: number
  lines_removed: number
}

export interface PatchResponse {
  diff: string | null
  strategy: string | null
  rationale: string | null
  stat: PatchStat | null
  target: PatchTarget
  absent_because: string | null
}

/**
 * `GET /api/findings/{finding_id}/dismissal`.
 *
 * `dismissed: false` with a null reason is the same payload for a finding nobody has ever
 * touched and for one that was dismissed and then restored -- the store's own docstring says
 * so, and `history_count` is what tells them apart. A screen that renders the flag without the
 * count states a true fact misleadingly, which is why the reader returns both.
 */
export interface DismissalState {
  dismissed: boolean
  reason: string | null
  actor: string | null
  history_count: number
}

/**
 * `GET /api/findings/dismissals`.
 *
 * `counts` holds only reasons that occur. A reason absent and a reason at nought are different
 * claims and the query makes only the first, so a view must not render a missing key as a zero.
 */
export interface DismissalTally {
  counts: Record<string, number>
  total: number
}

/**
 * One recorded event of a patch run. `tool` is null on a note — prose names no tool. `seq` is
 * the recorder's own counter and the only order; `summary` is untrusted evidence and renders
 * as text, never as markup.
 */
export interface RunActivityEvent {
  seq: number
  at: string
  kind: "tool" | "note" | "refusal"
  tool: string | null
  summary: string
}

/**
 * The feed for one finding's run, oldest first. An empty list folds two nothings the payload
 * cannot separate — a run predating activity capture and one not started — and the view says so.
 */
export interface RunActivityResponse {
  events: RunActivityEvent[]
}

export interface WorkflowState {
  nodes: WorkflowNode[]
  outcome: WorkflowOutcome | null
  abandon_reason: string | null
  report_reason: string | null
  thread_id: string
  generation_count: number
  repo_id: string | null
  generations: GenerationSummary[]
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
export type RunDisposition = "opened" | "abandoned" | "reported" | "parked"

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
  /**
   * The finding as something a reviewer can say — `stripe-postcharges-4b1c9e`.
   *
   * Derived in the payload (`sync.core.naming.finding_name`), never in the console: the CLI and
   * a pull-request body name the same finding, and a third derivation is where they diverge.
   * The id above stays the addressable thing and every link is still built from it.
   *
   * `null` when the graph no longer holds the finding this thread names. The checkpointer
   * outlives `finding`, which a scan truncates and rebuilds, so a run whose finding was patched
   * or retracted has no call site to take a vendor and operation from — and a name invented for
   * it would claim an integration nothing recorded.
   */
  finding_name: string | null
  /**
   * What the heartbeat table knows about an in-flight run (B194): `alive` — the runner's
   * process ticked inside its window; `expired` — the sweep recorded that heartbeats stopped
   * with no clean exit, a stored transition rather than a per-read guess; `unmonitored` — no
   * heartbeat row, the run predates the table. `null` on a terminal run, where liveness is
   * not a question.
   */
  liveness: "alive" | "expired" | "unmonitored" | null
  /** When the runner's process last said "still here", or null when never monitored. */
  last_heartbeat_at: string | null
  /**
   * The repository this run's finding belongs to, or `null` when the checkpoint does not name
   * one. The transport has always carried it (`sync.dashboard.fleet._run_row`); this type omitted
   * it, so every screen built links without it and sent readers to an address the router does not
   * serve. `null` is a run whose repository is genuinely unknown — a scoped link cannot be built
   * for it, and guessing would point at another workspace's finding.
   */
  repo_id: string | null
  run_id?: string | null
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
 * `WorkflowState` off `Provenance`.
 */
export interface RunsPage {
  items: RunRow[]
  /** How many runs the current filters admit — what the pager walks, not the whole fleet. */
  total: number
  next_offset: number | null
  /**
   * One count per disposition, computed across every run the scope holds and never narrowed
   * by the `outcome` filter — a rail's counts say what each selection would return, and
   * counts narrowed by the filter they set collapse to whatever is already selected. The
   * `"null"` bucket is the in-flight one.
   */
  by_disposition: Record<string, number>
  /** The scope's run count with no `outcome` filter applied — the unfiltered option's figure. */
  unfiltered_total: number
}

/**
 * `GET /api/change-units`: open findings grouped by the vendor change and operation that
 * produced them, fleet-wide or narrowed to one repository.
 *
 * The grain is one row per `(vendor_id, operation_id, change_kind, from_version, to_version)`
 * — `sync.dashboard.fleet.change_units`'s own grouping key — never one row per finding and
 * never one row per repository. A change spanning four repositories and eleven call sites is
 * one row here; `repository_count` and `call_site_count` are how many the grouping folded in,
 * and `finding_ids` / `repo_ids` are the members themselves, for a caller that needs the
 * individual findings rather than the count of them.
 *
 * `standing` and `last_checkpoint_at` arrive `null` together, and `null` is genuine absence —
 * not a zero and not "no remediation needed". The checkpointer read behind this route only
 * runs when `SYNC_CHECKPOINTER_DSN` is configured and a `checkpoints` table exists, so a null
 * pair means either that no run has ever been attempted for any finding this unit groups, or
 * that this deployment has no checkpointer to ask — the two are indistinguishable from this
 * payload alone, and a render site that turns `null` into "not started" is claiming the second
 * case never happens. `last_checkpoint_at`, once present, is staleness — how old the newest
 * checkpoint behind this unit is — never liveness: nothing in this row says whether that run
 * is still going or has died.
 *
 * `standing` carries one value `RunDisposition` does not: `"in_progress"`, written when the
 * checkpointer holds a run for this unit whose outcome has not yet reached one of the three
 * terminal values.
 *
 * `binding_rung` is a plain `string` rather than `BindingSource`: `_weaker_rung_summary` in
 * `sync.dashboard.fleet` answers `"mixed"` when a unit's call sites disagree on rung, which is
 * a real, deliberate value and not one of the five the graph's `binding_rung` column holds.
 */
export interface ChangeUnitRow {
  change_unit_id: string
  vendor_id: string
  operation_id: string | null
  change_kind: string
  from_version: string | null
  to_version: string | null
  severity: string
  repository_count: number
  call_site_count: number
  binding_rung: string
  /**
   * How many findings this unit holds — stated by the payload, never counted from `findings`.
   *
   * Under a severity narrowing this is the count *at that severity*, because the narrowing is
   * applied before the grouping. That is what makes the grouped totals reconcile with the flat
   * ones on every tab: filtering units afterwards would leave each one counting findings the
   * reader is not being shown.
   */
  finding_count: number
  /** The constituent findings, in the same shape the flat table renders. */
  findings: RiskRow[]
  finding_ids: string[]
  repo_ids: string[]
  standing: RunDisposition | "in_progress" | null
  last_checkpoint_at: string | null
}

/**
 * `GET /api/change-units`. Bare `{items, total, next_offset}`, the same reasoning as
 * `RunsPage`: this route reads open findings and the checkpointer, never `GraphSurface`, and
 * carries no feed-fetch timestamp or context-savings figure to fill `Page<T>`'s `Provenance`
 * half with.
 */
export interface ChangeUnitsPage {
  items: ChangeUnitRow[]
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
  /**
   * A bounded window of source around the call, captured by the index pass that wrote the row.
   * `null` under `source_served: true` means the row predates capture -- a different nothing
   * from a deployment that withholds source, which the page-level flag names.
   */
  snippet?: string | null
  /** 1-based file line of the snippet's first line. */
  snippet_start_line?: number | null
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
 * and `RunsPage` off it. `repo_id` and `path_prefix` here are the filters the request was made
 * with, not facts about the answer: null when the caller asked for everything.
 *
 * `repositories` is the option list those filters are set from, and `binding_surface` computes
 * it with neither of them applied — an option list narrowed by the filter it sets collapses to
 * whatever is already selected. Its `call_site_count` is therefore a count over the whole
 * operation and not over `call_sites.total` beside it, which is why a screen showing both has
 * to say which is which.
 */
export interface BindingRepository {
  repo_id: string
  call_site_count: number
}

export interface BindingSurfaceResponse {
  vendor_id: string
  operation_id: string
  repo_id: string | null
  path_prefix: string | null
  call_sites: ItemPage<BindingCallSite>
  /**
   * The deepest directory every call site in the filtered set shares, ending in `/`, or `""` when
   * they share none.
   *
   * A property of the set the page was drawn from rather than of the fifty rows in the window —
   * computing it client-side over one page would make the same call site render differently on page
   * one and page two. The screen states it once above the table and renders each row's remaining
   * path, so nothing is hidden: the full path is the prefix plus the remainder, both on screen.
   * `""` means render the whole path and say nothing.
   */
  call_sites_common_directory: string
  changes: ItemPage<BindingChange>
  repositories: BindingRepository[]
  /** Whether this deployment serves index-captured source windows (SYNC_SERVE_SOURCE). */
  source_served: boolean
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
/**
 * One API product this repository calls, under the vendor that sells it.
 *
 * A vendor is the provider Sync watches; a service is one of the APIs it sells — `Payments` under
 * `stripe`. The graph carried only the provider until 2026-08-19, which is why the console's
 * Services and Vendors screens listed the same identifier under two headings.
 */
export interface ServiceCoverageRow {
  vendor_id: string
  /**
   * `null` where nothing has mapped this vendor's operations onto a product yet.
   *
   * **Not grouped, and never a call site outside every service.** Only a vendor adapter can supply
   * the mapping and none does today, so this null is work not done — a screen rendering it as a
   * service named nothing, or dropping the row, would report a vendor as having no products when
   * what it has is no adapter.
   */
  service_id: string | null
  call_sites: number
  /** Distinct operations in this group, so a reader can see how much of the vendor it covers. */
  operations: number
  last_indexed: string
}

/**
 * One vendor operation this repository calls, carrying the product it belongs to.
 *
 * The grain beneath `ServiceCoverageRow`. Its own aggregate rather than something summed out of
 * this list, so the two can never disagree in a way neither can reveal.
 */
export interface OperationCoverageRow {
  vendor_id: string
  /** `null` for the same reason `ServiceCoverageRow.service_id` is: nothing has grouped it yet. */
  service_id: string | null
  operation_id: string
  call_sites: number
  last_indexed: string
}

export interface IndexCoverageResponse {
  repo_id: string
  by_vendor: Tally
  last_indexed: Record<string, string>
  total_call_sites: number
  /** The product question beside the provider question, computed over the same rows. */
  by_service: ServiceCoverageRow[]
  /** The operations behind those products, so a product can list its own without a second read. */
  by_operation: OperationCoverageRow[]
  /**
   * How much of this codebase's API surface is at risk, clean, or unexamined — counted over
   * **operations**, not call sites, so one heavily-called operation cannot dominate a figure
   * meant to describe breadth.
   *
   * A status absent here was not counted at nought, and an empty object is a repository with no
   * call sites at all. Only ApiSurfacePanel fills a missing member with a zero, and only after
   * establishing that a surface exists — see its own note for why that is honest there.
   */
  by_binding_status: Tally
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
  /**
   * When telemetry was attached to this repository, or `null` when it never was.
   *
   * `observed_telemetry` has always returned this and the type omitted it, so the console could
   * not read the one distinction this rung exists to make: an empty `calls` page under attached
   * telemetry is a measured nought, and the same empty page with no attachment is nobody having
   * looked (B157). Without this field the two render identically, which is the substitution the
   * console refuses everywhere else.
   */
  telemetry_attached_at: string | null
  calls: ItemPage<ObservedCallRow>
  shapes: ItemPage<ObservedShapeRow>
  error_windows: ItemPage<ObservedErrorWindowRow>
  /**
   * Traffic per operation, pooled across every unit of work held — correlated rows only.
   * `requests` counts spans that carried a status (the detector's own denominator rule);
   * `unstatused` is reported beside it so a rate computed over a shrunken sample can be
   * discounted. No rate arrives from the transport: a screen that divides shows both counts.
   */
  traffic: TrafficRollupRow[]
  /** The same rollup for traffic nothing could attribute to an operation — never pooled in. */
  unattributed: TrafficRollupRow[]
  /**
   * Requests and errors per hour, bucketed by each unit of work's `first_seen` — a span carries
   * no timestamp of its own, so a long trace's spans land on the hour its first request did.
   */
  series: TrafficBucket[]
  totals: TrafficTotals
}

export interface TrafficRollupRow {
  vendor_id: string
  operation_id: string
  server_address: string
  http_method: string
  binding_rung: string
  url_template: string
  traces: number
  requests: number
  errors: number
  unstatused: number
  distinct_targets: number
  max_resend: number
  first_seen: string
  last_seen: string
}

export interface TrafficBucket {
  bucket: string
  requests: number
  errors: number
}

export interface TrafficTotals {
  requests: number
  errors: number
  unstatused: number
  unattributed_requests: number
  operations_observed: number
  /** How many distinct operations the static index binds — the coverage denominator. */
  operations_indexed: number
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
  /** The repository this roll-up covers, or `null` for the fleet. See `OverviewResponse`. */
  repo_id: string | null
  detectors: DetectorRow[]
  /**
   * Every open finding counted once by the rung behind it, across all detectors — not the sum
   * of the per-detector `by_rung` maps, which double-count nothing but answer a different
   * question (per detector, rather than over the scope).
   *
   * **Every rung in the vocabulary is a key even at nought**, because `detector_accountability`
   * seeds the tally from `FINDING_RUNGS` rather than from the rows it found. So a rung missing
   * here is a defect, where in almost every other payload on this console a missing key is an
   * absence. Declared late: the route has always sent it and this type did not say so, which is
   * the drift `console-dev-loop.md` warns a green build cannot catch.
   */
  by_rung: Record<string, number>
  total_open_findings: number
}

/**
 * One adapter's row in `GET /api/adapters`.
 *
 * **Every count is nullable, and null is not zero.** `null` means the graph holds no
 * `vendor_change` row for this vendor at all — the adapter has never delivered — while `0` would
 * mean Sync read the vendor's specification and found nothing to say. Both are legitimate and only
 * one is a problem, so a renderer that prints `0` for a null hides the case this screen exists to
 * show. `sync/dashboard/adapters.py` decides it; nothing between there and the cell may soften it.
 *
 * There is deliberately no `decline_reason`. Nothing in Sync records why an adapter declined, and a
 * column null on every row would read as "no adapter has ever declined" — a claim nothing measured.
 */
export interface AdapterRow {
  vendor_id: string
  /**
   * `coded` — an adapter written in this repository. `generated` — served from a manifest the
   * vendor's SDK repository commits. `mcp` — a watched MCP server. `unregistered` — the graph
   * holds history keyed by this vendor and no adapter serves it any more.
   */
  kind: "coded" | "generated" | "mcp" | "unregistered"
  /** The SDK repository or capture directory behind this adapter; `null` for a coded one. */
  source: string | null
  /** Rows the graph holds. `null` when the adapter has never delivered. */
  changes: number | null
  /** Distinct operations those rows name. `null` when the adapter has never delivered. */
  operations: number | null
  /**
   * The newest `detected_at` the graph holds for this vendor, ISO-8601, or `null`.
   *
   * **Not the last time the adapter was asked.** Nothing records an intake attempt, only its
   * result, so an adapter polled hourly that has found nothing new for a week reports last week.
   * The field is named for what it is and the screen must not relabel it.
   */
  last_change_at: string | null
  /** The `source` values those rows carry, sorted. `null` when the adapter has never delivered. */
  sources: string[] | null
  /**
   * When the adapter was last *asked*, ISO-8601, or `null` where no attempt is recorded.
   *
   * **This is the field `last_change_at` says it is not.** The two answer different questions and
   * the difference is the point: a healthy, quiet adapter has a recent `last_attempt_at` and an
   * old `last_change_at`, which was previously indistinguishable from an adapter nobody had run.
   *
   * A `null` here is not "never asked". The attempt record began when the table did, so it means
   * this screen holds no record of an attempt -- a limit of the record rather than a fact about
   * the adapter.
   */
  last_attempt_at: string | null
  /** `success`, `declined` or `failed` on the newest attempt; `null` where none is recorded. */
  last_attempt_outcome: "success" | "declined" | "failed" | null
  /**
   * Why the newest attempt declined or failed, from the closed vocabulary
   * `sync.signals.intake_attempt` owns. `null` on a success, and on a vendor with no record.
   *
   * Closed rather than free text precisely so it can be counted: a promise to learn from
   * failures needs a schema that can answer the question.
   */
  last_attempt_reason: string | null
  /** Changes the newest attempt returned. `null` where no attempt is recorded. */
  last_attempt_changes: number | null
  /**
   * Attempts tallied by outcome, over every attempt recorded for this vendor.
   *
   * Only outcomes that occurred are keys. An outcome absent here never happened for this
   * adapter; it is not an outcome measured at nought, and a view must not render it as one.
   * `{}` means no attempt is recorded at all.
   */
  attempts: Record<string, number>
}

/** `GET /api/adapters`. Registered adapters and historical vendors alike, ordered by vendor id. */
export interface AdapterInventoryResponse {
  adapters: AdapterRow[]
}

/** One edge of the dependency graph: a place this repository calls a vendor operation. */
export interface RepositoryGraphBinding {
  vendor_id: string
  operation_id: string
  path: string
  line: number
  symbol: string
  /**
   * Always `"static"` here. A call site is what the static index found, and nothing about this
   * edge rests on a resolution or a correlation step. A stronger rung for the same operation is
   * a fact about the repository's telemetry and is never blended into this row.
   */
  binding_rung: "static"
}

/** One vendor node, with what the index knows about this repository's calls to it. */
export interface RepositoryGraphVendor {
  vendor_id: string
  indexed_call_sites: number
  /**
   * The newest `indexed_at` among this vendor's call sites, or `null` when none was read.
   * Staleness, never a promise that the index is current.
   */
  last_indexed: string | null
}

/** `GET /api/repositories/{repo_id}/graph`. The picture the Overview draws. */
/** One edge traffic established, aggregated to one per (vendor, operation, rung). */
export interface RepositoryGraphObservedBinding {
  vendor_id: string
  operation_id: string
  /** The rung this edge was established at. Never blended with the static edge beside it. */
  binding_rung: BindingSource
  /** Observed calls behind this edge. `observed_call`'s grain is one row per unit of work. */
  calls: number
}

/**
 * What the repository holds that no edge can carry, as counts.
 *
 * Both are measurements — the tables were read and held what they held. Neither is nothing, and
 * neither may be folded into a rung: an uncorrelated span names no operation to draw an edge to,
 * and `unattributed` is a value no binder emits and which `BindingRung` excludes.
 */
export interface RepositoryGraphOffPath {
  unresolved: number
  unattributed: number
}

export interface RepositoryGraphResponse {
  repo_id: string
  vendors: RepositoryGraphVendor[]
  bindings: RepositoryGraphBinding[]
  observed_bindings: RepositoryGraphObservedBinding[]
  off_path: RepositoryGraphOffPath
  /** The closed rung vocabulary, echoed so a rung with no edge differs from one that cannot be. */
  rungs: BindingSource[]
  /**
   * When the index last wrote a call site here, or `null` if it never has.
   *
   * **This `null` is ambiguous on purpose and the screen must say both.** No call site row has
   * ever existed for this repository, which is either an index that never ran or one that ran and
   * found no vendor call — nothing records an index attempt, only its result, so the payload
   * refuses to pick. Retracted rows still count: a repository whose calls have all gone was
   * indexed, and answering `null` there would claim the index never ran.
   */
  indexed_at: string | null
  /** How many current call sites the repository holds, whether or not all of them were drawn. */
  total_bindings: number
  /** Whether `bindings` is all of them. A partial picture says so rather than implying whole. */
  truncated: boolean
}

/**
 * One operation this codebase calls on a vendor, from
 * `GET /api/vendors/{vendor_id}/operations`.
 *
 * `binding_rung` is always `"static"`: a call site is what the static index found. Telemetry is
 * reported beside it in `observed` rather than blended into it, so a reader sees both facts
 * instead of an average of them.
 */
export interface VendorOperationExposure {
  operation_id: string
  /** Current call sites naming this operation. A retracted site is not counted. */
  call_site_count: number
  /** How many repositories hold those sites. `1` under a repository scope, by construction. */
  repository_count: number
  binding_rung: "static"
  /**
   * Whether traffic named this operation. **Three-valued, and the third value is the point.**
   *
   * `null` means nothing looked — no telemetry is attached to the repository, or the question
   * was asked across every repository at once, where attachment differs per repository and no
   * single answer exists. Rendering `null` as "not observed" would report a measurement nobody
   * took.
   */
  observed: boolean | null
}

export interface VendorOperationsResponse {
  vendor_id: string
  /** The repository this was narrowed to, or `null` for every repository the index has seen. */
  repo_id: string | null
  /** When telemetry was attached to that repository, or `null` when it never was. */
  telemetry_attached_at: string | null
  operations: VendorOperationExposure[]
}

/**
 * One `(change_kind, tier)` pair that has been attempted, from `GET /api/corpus/abandonment`.
 *
 * **The grain is one repair attempt, not one finding.** A finding retried three times is three
 * attempts and one finding, which is why the counts come in pairs and neither is a bare `count`.
 * A query that counts findings by counting attempts is wrong, and wrong quietly.
 *
 * No ratio is served. A change kind abandoning three of four attempts arrives as `4` and `3`;
 * the reader can divide, and the payload does not hand back a percentage that reads as a score.
 */
export interface AbandonmentGroup {
  change_kind: string
  tier: number
  attempt_count: number
  distinct_finding_count: number
  abandoned_attempt_count: number
  abandoned_distinct_finding_count: number
  /**
   * `abandon_reason_code` tallied within this group, over abandoned attempts only.
   *
   * Keys are the closed vocabulary `sync.remediate.state.AbandonReasonCode` declares. **The key
   * `"null"` is not one of them**: it is a row recorded before the column existed, and it is a
   * different fact from `unclassified`, which is a real member meaning a run reached the
   * fallback. A group with no abandonment is `{}`.
   */
  abandon_reason_codes: Record<string, number>
}

export interface AbandonmentResponse {
  groups: AbandonmentGroup[]
}

/**
 * `GET /api/vendors/{vendor_id}/change-volume` -- how often this vendor publishes, and of what kind.
 *
 * **Counted over every change the vendor has, not over a page.** The console used to derive this
 * from whichever page of `VendorChangeRow` happened to be loaded, so the total was a page count
 * wearing the vendor's name and it moved when a reader paginated. `total_changes` here is
 * `len(all_vendor_changes)` and no view can move it.
 */
export interface VendorChangeVolumeResponse {
  vendor_id: string
  total_changes: number
  by_kind: Tally
  by_severity: Tally
  timeline: { period: string; count: number; by_kind: Tally }[]
  /** `null` where the vendor has no change at all -- absence, never a zero date. */
  newest_change_at: string | null
  oldest_change_at: string | null
}

/**
 * `GET /api/findings/over-time`: what Sync produced, by severity, by the day it recorded it.
 *
 * **The day is when Sync first recorded the claim, not when the vendor published the change.**
 * A reader looking at dated bars of API findings assumes the vendor's timeline; this is Sync's,
 * and the two diverge by however long a feed took to arrive and a detector took to run.
 */
export interface FindingsOverTimeDay {
  day: string
  /** Only the severities that occurred. A severity absent here had none that day. */
  counts: Record<string, number>
}

export interface FindingsOverTimeResponse {
  repo_id: string | null
  /** The closed severity vocabulary, echoed so a kind at nought differs from one that cannot be. */
  severities: string[]
  /** Only days something was recorded. A gap is a day nothing was recorded, never a zero. */
  days: FindingsOverTimeDay[]
  /** What the window's findings rest on. Every derived figure carries its rung. */
  by_rung: Record<string, number>
  /** Every finding recorded, including ones since closed. */
  total: number
  /** How many of them are still open, reported beside the series rather than folded into it. */
  still_open: number
}

/**
 * One remediation request — the console's ticket lane (owner ruling 2026-08-19).
 *
 * `status` is the lifecycle the Solutions funnel draws: `requested` (initiated), `picked_up`
 * (in progress), `done` (complete, with `outcome` saying how — the run's own vocabulary).
 * `source` is which lane asked: `operator` from the Findings page, `watch` from the loop.
 */
export interface Ticket {
  id: number
  finding_id: string
  repo_id: string
  source: string
  status: string
  requested_at: string
  picked_up_at: string | null
  done_at: string | null
  thread_id: string | null
  outcome: string | null
  detail: string | null
}

export interface TicketsResponse {
  repo_id: string
  tickets: Ticket[]
}

/**
 * Whether a call this codebase makes is known to be at risk, known to be clean, or unexamined.
 *
 * **Owner question, 2026-08-19: "why do we not show safe APIs?"** Severity could not carry it —
 * severity is the *vendor's* published label on a change and `oasdiff` emits no "safe", so a
 * `safe` severity would be Sync putting a judgement about this codebase in a column that
 * otherwise holds only the vendor's own words. This is the honest form of the same question,
 * computed by `sync.graph.store` rather than stored.
 *
 * **`unchecked` is the member that earns the other two.** It means no successful intake attempt
 * for the vendor — the graph has never read its specification — and without it, `clean` would be
 * an all-clear the console never earned. Most-wanting-attention first, matching
 * `BINDING_STATUSES` in the store, which is what `tests/test_api_routes.py` holds the two to.
 */
export const BINDING_STATUSES = ["at_risk", "unchecked", "clean"] as const

export type BindingStatus = (typeof BINDING_STATUSES)[number]
