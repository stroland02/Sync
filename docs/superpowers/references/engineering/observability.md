# Observability across nine reference repositories

Audit date: 2026-08-04. Clones under
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs/`,
one directory per repository, shallow at whatever each repository's default branch held that day.

**Coverage.** I read observability code in all nine: `open-code-review`, `codegraph`,
`codebase-memory-mcp`, `code-review-graph`, `PageIndex`, `Understand-Anything`,
`claude-cookbooks`, `superpowers`, `skills`. Depth is uneven and deliberately so. I read
`open-code-review`'s `internal/telemetry/` and `internal/session/` closely, because they are the
only reference here that solves the same problem Sync's dashboard solves. I read `codegraph`'s
telemetry client, worker schema and design contract closely. For `PageIndex`,
`Understand-Anything`, `superpowers` and `skills` the finding is largely absence, and absence is
cheap to establish, so those sections are short by evidence rather than by neglect. I did not
read `codebase-memory-mcp`'s 2000-file tree exhaustively — I read `src/foundation/log.{c,h}`,
`src/foundation/diagnostics.c`, `src/traces/traces.h` and the `ingest_traces` handler in
`src/mcp/mcp.c`, and I did not audit whether every subsystem actually calls the logger it has.

Every claim below is labelled VERIFIED (I opened the file this session), REPORTED (a document in
the repository asserts it and I did not confirm against code), or INFERENCE (my reasoning from
what I read).

**Second pass, same date.** A later reading re-derived the load-bearing claims independently
against `open-code-review`'s `internal/telemetry/` and `internal/session/`,
`codebase-memory-mcp`'s `src/foundation/log.h` and `src/mcp/mcp.c`, `codegraph`'s
`telemetry-worker/`, and Sync's `queries.py`, `corpus.py`, `store.py` and `agent_patch.py`. Every
claim it checked held. It added four findings, marked below: the dead content-logging switch
(2h), the redaction floor and the `Finalize` backstop sweep (2h and 3.4, 3.9), and span-name
cardinality (2a). It also *withdrew* one claim it had drafted — that `open-code-review`'s trace is
flat because `StartLLMSpan` and `StartToolSpan` discard their returned contexts. They do discard
them (`internal/llmloop/loop.go:202,321,387`), but a per-file span at `internal/agent/agent.go:1092`
rebinds `ctx` before the loop runs, so LLM and tool spans are correctly parented under
`subtask.execute.<path>`. Recorded because the near-miss is the lesson: span nesting is invisible
in a grep and has to be traced through the context variable.

---

## 1. What this dimension covers, and why it matters here

Observability is the set of answers a system can give about a run that has already finished. Four
sub-questions: what does it log and in what shape; does it trace, and against a standard or a
private scheme; does it count anything; and when a run fails at 3am, what survives on disk long
enough for someone to reconstruct the failure.

For most tools this is operational hygiene. For Sync it is closer to the product. Sync's claim is
the binding — which call site depends on which vendor operation — and every artifact downstream of
that claim is an assertion a customer is being asked to trust: this finding is real, this patch is
correct, this pull request is safe to merge. A pipeline that emits assertions without emitting the
evidence behind them is asking for trust it cannot substantiate. The `binding_rung` rule already
encodes this instinct at the data layer: an unattributed finding is refused at write time
(`src/sync/graph/schema.sql:162`, `binding_rung TEXT NOT NULL DEFAULT 'unattributed'`, with the
detector tests standing in for the type system). Observability is the same instinct applied to
execution rather than to data.

There is also a narrower, harder problem the console makes urgent. Sync runs an agent inside
`patch`. An agent is a nondeterministic subprocess whose failures are not exceptions — they are
plausible-looking wrong answers. The only way to debug one after the fact is to have kept what it
did. Everything in this note bends toward that.

---

## 2. The design space, grouped by approach

### 2a. Full OpenTelemetry, opt-in, with graceful degradation to no-op

**`open-code-review` is the only repository here that does this.** VERIFIED.
`internal/telemetry/` is 2201 lines across 14 files, half of them tests, and it is a real OTel
integration rather than a gesture at one.

The design decision worth stealing is the disabled path. `StartSpan`
(`internal/telemetry/span.go:22-27`) returns `trace.SpanFromContext(ctx)` — the no-op span — when
telemetry is off, so every caller can `defer span.End()` unconditionally and no call site needs an
`if enabled` branch. Telemetry is off by default (`config.go:29-38`, `DefaultConfig` returns
`Enabled: false`) and turns on through `OCR_ENABLE_TELEMETRY=1` (`config.go:43`) or a
`telemetry` block in `~/.opencodereview/config.json` (`config.go:61-106`), with environment
beating file (`config.go:108-122`).

Spans are typed by what they wrap rather than freeform. `StartToolSpan` (`span.go:84-87`) and
`StartLLMSpan` (`span.go:105-109`) mint spans with fixed attribute names, and the matching
`RecordToolResult` (`span.go:90-103`) / `RecordLLMResult` (`span.go:111-126`) set
`tool.status`/`llm.status`, duration, token count and error uniformly. That uniformity is what
makes a query across runs possible; a codebase that lets each call site name its own attributes
gets a trace nobody can aggregate. Call sites are real and spread across the pipeline —
`internal/agent/agent.go:231` (`diff.parse`), `:1183` (`main.loop`), `:1226`
(`review_filter.execute`), `internal/llmloop/loop.go:202,321,387,465`, `internal/scan/agent.go:300,693`.

Two details in this package are the kind of thing a reader should note because they are cheap and
almost nobody does them:

- **Distributed context is accepted from the environment.** `ContextWithTraceParentFromEnv`
  (`span.go:32-41`) reads the W3C `TRACEPARENT` environment variable and extracts it into the
  root context, so a CI job that already has a trace can parent the review run under it. Both
  entry points use it (`cmd/opencodereview/review_cmd.go:208`,
  `cmd/opencodereview/scan_cmd.go:203`). A CLI that can be adopted into someone else's trace
  costs about six lines.
- **The trace ID is handed to the human.** `review_cmd.go:216-219` prints
  `[ocr] TraceID: <hex>` to stderr when telemetry is enabled, and `shared.go:330` threads the
  same ID into the JSON output object. The identifier that correlates the backend trace is
  therefore in front of the person who just watched the run fail, without them knowing anything
  about OTel.

Metrics are eight instruments in `internal/telemetry/metrics.go:37-68`: review duration, files
reviewed, comments generated, LLM request count, tokens used, LLM request duration, tool call
count, tool execution duration — with `model` and `status` as attributes
(`metrics.go:104-122`). Exporters cover console (pretty-printed stdout, `exporter.go:180-207`)
and OTLP over gRPC or HTTP (`exporter.go:96-178`).

The span *hierarchy* is right and worth copying: `review.run` (`review_cmd.go:209`) parents
`subtask.execute.<path>` (`agent.go:1092`), which parents the `llm.request` and
`tool.execute.<name>` spans the loop starts (`llmloop/loop.go:202,321,387`), so a concurrent
review of forty files still attributes every model call to a file. The nesting works because
`agent.go:1092` rebinds `ctx` from the returned context; the leaf calls discard theirs, which is
harmless only because nothing is nested under a leaf.

The span *names* are the flaw. `"subtask.execute."+d.NewPath` (`agent.go:1092`) and
`"scan.subtask."+it.Path` (`internal/scan/agent.go:693`) put a file path in the span name rather
than in an attribute — `file.path` is then set as an attribute anyway, two lines later at
`agent.go:1094`. VERIFIED. Span name is the dimension every tracing backend groups, indexes and
bills on, so this turns a bounded set of operation names into one name per file ever reviewed.
The `tool.execute.`/`llm.request` spans get this right (`span.go:85-86`: fixed name, tool name as
an attribute), which makes the inconsistency an oversight rather than a philosophy. If Sync ever
adopts the pattern, node names are the span names and the finding ID is an attribute.

The honest wart, and it is instructive: `checkMetricErr` at `metrics.go:70-72` is an empty
function body with a comment saying telemetry is best-effort and must not interrupt the main flow.
Every metric registration error is discarded, and each recording site then guards with
`if mInstrument != nil`. This is a deliberate, documented choice to fail silent. It is also the
reason a misconfigured meter provider produces zero metrics and zero complaints. Sync's
`checkMetricErr` equivalent would be worse, because Sync's numbers feed routing decisions rather
than a dashboard.

The `exporter.go:134-149` comment is worth reading in full as an example of a comment that states
a constraint the code cannot show: it records that `WithEndpoint` cannot express a URL path, that
Langfuse receives OTLP at `/api/public/otel`, and that every span was therefore silently dropped
with a 404 until they switched to `WithEndpointURL`. That is a bug that produced no error
anywhere — the failure mode of an entire observability stack was "no data, no message."

### 2b. Structured key-value logging with no tracing

**`codebase-memory-mcp`.** VERIFIED. `src/foundation/log.h:1-12` states the design: everything to
stderr because stdout is the MCP JSON-RPC channel; logfmt-style output
(`level=info msg=pass.timing pass=defs elapsed_ms=42`); optional JSON format; four levels plus
`NONE`. The API is variadic key-value pairs terminated by NULL (`log.h:57-68`), which is a C-shaped
way of getting structured fields without a struct. Level and format are both settable from the
environment — `CBM_LOG_LEVEL` accepting names or numerals and failing open on garbage
(`src/foundation/log.c:39-67`), `CBM_LOG_FORMAT=text|json` (`log.c:69-80`). The level is an
`_Atomic` (`log.c:26-27`), and `emit_line` loads the sink pointer exactly once with a comment
explaining that re-reading between test and call would let a concurrent `set_sink` turn a checked
pointer into a NULL call.

Two ideas here I have not seen elsewhere in this set:

- **A record class that bypasses level filtering.** `cbm_log_control_record` (`log.h:74-81`) always
  emits, always in JSON. It is reserved for discovery events — the one that announces where the
  diagnostics files were written (`diagnostics.c:661-664`). The reasoning in the comment is exact:
  a path is the only useful thing that record carries, `CBM_LOG_LEVEL=error` would suppress it, and
  a path with a space in it needs JSON quoting to survive unambiguously. A log line whose entire
  purpose is to tell you where the other logs are must not be subject to log filtering.
- **Operational helpers that structurally cannot leak.** `cbm_log_mcp_request` and
  `cbm_log_http_request` (`log.h:88-93`) take method, tool name, status, duration and byte counts
  — and the comment says they "deliberately avoid request bodies, headers, arguments, and query
  strings." The privacy rule is enforced by the function signature rather than by reviewer
  vigilance.

`codebase-memory-mcp` also has a **debug mode that is a flight recorder**, which nothing else here
has. `CBM_DIAGNOSTICS=1` (`src/foundation/diagnostics.c:637`) starts a background thread that
writes `snapshot.json` (rewritten atomically via a `.tmp`) and appends to `trajectory.ndjson`
every 5 seconds, capped at 8 MB with one rotation to `trajectory.ndjson.1`
(`diagnostics.c:46-57`). The whole subsystem is best-effort with a bounded shutdown: 500 ms
timeout, and if the writer thread has not finished it is detached and its state deliberately
retained until process exit rather than freed, because closing a descriptor the stalled thread may
still hold would create a reuse race (`diagnostics.c:667-693`). A diagnostics facility that can
hang the daemon it is diagnosing is worse than none, and they say so in the code.

**The most useful negative finding in this repository is `ingest_traces`.** VERIFIED. It is
advertised in the MCP tool table at `src/mcp/mcp.c:664` as "Ingest runtime traces to enhance the
knowledge graph" and listed in the CLI help at `src/cli/cli.c:1291`. The handler is
`src/mcp/mcp.c:10885-10914`. It parses the `traces` array, counts its length, frees the document
without reading a single span, and returns:

```
{"status":"accepted","traces_received":N,
 "note":"Runtime edge creation from traces not yet implemented"}
```

There is a whole supporting header, `src/traces/traces.h`, defining OTLP span, resource and
attribute structs and an `extractHTTPInfo` result type with service name, method, path, status and
duration — and nothing calls it from the handler. So the tool that would join runtime telemetry
into the code graph — precisely Sync's OBSERVE rung — reports `status: "accepted"` for data it
discards. `"accepted"` is technically true and operationally a lie. This repository's own README
tree is where an operator would go to find out, and they would not.

### 2c. Anonymous product analytics as an auditable public contract

**`codegraph`.** VERIFIED. This is not debug observability at all — it answers "which languages
should we build extractors for," not "why did this run fail." But the way it is built is the best
worked example in the set of shipping telemetry from a local-first tool without destroying the
privacy claim.

`TELEMETRY.md` (110 lines) is the user-facing field-by-field list. `docs/design/telemetry.md` is
the engineering contract, and its first principle is the load-bearing one: *"The schema is the
allowlist. Client sends only the events below; the ingest Worker validates against the same
allowlist and drops anything else. Adding a field = PR that edits this doc + `TELEMETRY.md` + the
Worker allowlist together."* The ingest endpoint's entire source is in the repository
(`telemetry-worker/`), including the SQL that stores events
(`telemetry-worker/migrations/0001_init.sql`) with a comment on every column and a preamble stating
that if a column is not there, it is not kept. The rollup/purge job is public for the same stated
reason (`telemetry-worker/src/rollup.ts:1-22`): "this is every read and every write we make over
the stored events, including the one that deletes them."

Retention is explicit and split by kind: raw events purged after
`DEFAULT_RETENTION_DAYS = 90` (`rollup.ts:25`), deleted in keyset batches of 5000 rows with a
ceiling of 60 batches a night (`rollup.ts:33-35`); daily rollups kept forever because they are
tiny; `machine_days` and `machine_first_seen` never purged because retention cohorts need the full
history. The rollup recomputes three days back, not one, because clients buffer offline and ship
completed days late — and every rollup write overwrites rather than increments, so re-running a
day is a no-op (`rollup.ts:8-16`). That is idempotency stated in the same words Sync's
pipeline-discipline spec uses.

The client (`src/telemetry/index.ts:1-23`) declares four invariants: zero hot-path cost (recording
is an in-memory increment, sends are fire-and-forget), zero stdout because stdio is the MCP
channel, off means no socket is opened at all — not even an opt-out ping — and every failure mode
is silence. `MAX_BUFFER_BYTES = 256 * 1024` (`index.ts:36`) bounds what an offline machine
accumulates. `DO_NOT_TRACK=1` is honored as the cross-tool standard (REPORTED, `TELEMETRY.md`
"Turning it off").

The idea most transferable to Sync is buried in `docs/design/telemetry.md`'s `usage_rollup`
section. The prompt hook rolls up its **gate decision** as fixed counter names —
`prompt-hook-gate-high-keyword`, `-medium-segment`, `-noop-vocab-empty`, `-noop-explore-token`
and six others — never prompt content. The doc then says what the numbers are for: *"This is the
gate's measured recall/precision funnel: a rising `noop-*` share against the `high`/`medium` tiers
is the signal that the gate is missing real questions."* They instrumented a heuristic's decision
distribution so that the heuristic's quality became a query rather than an argument. Sync has
exactly one heuristic of that shape and it is the whole product.

### 2d. Stdlib logging, configured once at the entry point

**`code-review-graph`.** VERIFIED. Thirty of forty-five modules under `code_review_graph/` do
`import logging` with a module-level `logger = logging.getLogger(__name__)`
(e.g. `code_review_graph/daemon.py:37`), and configuration happens only at CLI entry points:
`logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")` at
`code_review_graph/cli.py:1495` and `:1525`, `code_review_graph/daemon_cli.py:239`, and
`scripts/render_pr_comment.py:341`. Output is free text with `%`-style lazy formatting, levels
used sensibly (`logger.warning` for skipped repos at `daemon.py:180-204`, `logger.exception` for
reconciliation failures at `:636` and watcher start failures at `:1067`, `logger.debug` for PID
liveness at `:487`). No structure, no correlation ID, no tracing, no metrics.

Its debuggability story is files plus a subcommand rather than a backend. The daemon writes
`daemon.log` in a configured log directory (`daemon.py:957`) and one `<alias>.log` per watched repo
(`daemon.py:1041,1056`), persists JSON state to a state path (`daemon.py:1026-1029`, read back at
`:514-518`), and `crg-daemon logs [--repo ALIAS]` exists to read them
(`daemon_cli.py:269-274`). No rotation and no retention that I found. For a single-machine daemon
that is a defensible trade; for anything multi-tenant it is a disk-full incident waiting.

`code_review_graph/context_savings.py` is a cost-accounting module of a different shape: it
estimates tokens saved by returning graph context instead of whole files, using a flat
`CHARS_PER_TOKEN = 4` approximation (`context_savings.py:12,29-31`). The module docstring labels
the values estimates and says why — *"a conservative character-count approximation instead of
model-specific tokenizers"* — which is the right way to ship a number you cannot make exact.

### 2e. `print()` as the logging strategy

**`PageIndex`.** VERIFIED, and it is the weakest observability in the set. The core pipeline
narrates itself to stdout with bare prints: `print('start detect_page_index')`
(`pageindex/page_index.py:273`), `print('start toc_index_extractor')` (`:334`),
`print('start toc_transformer')` (`:366`), `print('no toc found')` / `print('toc found')`
(`:857-860`), `print(f"Processing item {item} generated an exception: {result}")` (`:1011`).
`pageindex/client.py` does the same for indexing progress (`:70,98,127`) and for corrupt-file
warnings (`:154`). The `logging` module appears in exactly one file, `pageindex/utils.py`, and
only ever as `logging.error` (`:93,97,135,139,177,184,187`) with no logger name, no configuration
and no handler — so those lines go to the root logger's last-resort handler and everything else
goes to stdout as unlabelled prose. There is no level, no timestamp, no run identifier, no
structure, and no way to turn it off. An exception inside a concurrent map is reported by printing
the exception object and continuing (`:1011`). Nothing persists.

**`Understand-Anything`.** VERIFIED, and barely better. Across `packages/core/src` there are twelve
`console.*` calls total, all `console.warn` or `console.debug`, all free text with a
`[module-name]` prefix — `console.warn(\`[GraphBuilder] Duplicate node ID "${node.id}" —
skipping\`)` (`packages/core/src/analyzer/graph-builder.ts:304`), plus `:315`, and parser warnings
at `plugins/parsers/json-parser.ts:132`, `protobuf-parser.ts:137`, `terraform-parser.ts:126`,
`yaml-parser.ts:82`. No logging dependency in any `package.json`, no `DEBUG`/verbosity environment
variable, no persistence. The `[Module]` prefix convention is the whole of the structure. Notably,
several of these warnings are *silent-degradation* announcements — "unbalanced braces detected,
results may be incomplete," "YAML parse failed, falling back to regex extraction" — which is
precisely the class of event that must be queryable rather than printed, because it describes a
result the caller is about to trust.

### 2f. Agent inspection as a printing concern

**`claude-cookbooks`.** VERIFIED. The repository has a directory named `observability` and an agent
named the observability agent, and neither is about being observable. `observability/usage_cost_api.ipynb`
is a guide to the Anthropic Admin API — `usage_report/messages` and `cost_report` endpoints,
bucketed at `1m`/`1h`/`1d`, grouped by model/workspace/API key, with pagination. That is real cost
accounting, but retrospective and organization-wide, not per-run.
`claude_agent_sdk/observability_agent/agent.py` (146 lines) is an agent that *monitors GitHub* via
the GitHub MCP server; its own observability is a callback named `print_activity`.

The actual agent-inspection machinery is `claude_agent_sdk/utils/agent_visualizer.py`. It streams
tool use with emoji markers, distinguishing main-agent from subagent calls by indentation
(`:119-126`), and reconstructs the run afterwards in `visualize_conversation` (`:317`). Cost comes
off the SDK's `ResultMessage`: `total_cost_usd` at `:258-267` and `:514-517`, with a comment
saying to use the reported value because it is model-aware and authoritative, plus per-turn average
and token counts from `msg.usage` (`:505-512`). Two honest caveats are stated in the file itself:
the module-level activity context is not thread-safe and interleaved operations produce incorrect
subagent tracking (`:110-118`), and `msg.usage` is cumulative across turns rather than per-turn
(`:505`).

The transferable point is small and concrete: **the SDK hands you a `ResultMessage` carrying
`total_cost_usd` and `usage`, and the cookbook's advice is to trust it rather than recompute a
price.** Sync drives the same SDK.

### 2g. Observability as process discipline, with no runtime component

**`superpowers` and `skills`.** VERIFIED. Both are markdown skill libraries. `superpowers/hooks/`
contains `hooks.json`, `hooks-cursor.json`, `run-hook.cmd` and a `session-start` directory, and a
grep for log/journal/debug across them returns nothing — the hooks do not log. `skills/` has six
skill categories and no observability skill; the only hits for "observab" are incidental phrasings
like "Tests assert on observable outcomes through the interface, not internal state"
(`skills/engineering/codebase-design/DEEPENING.md:36`).

What they contribute to this dimension is the norm, not the mechanism.
`superpowers/skills/verification-before-completion/SKILL.md` states the Iron Law — "NO COMPLETION
CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE" — and a five-step gate: identify what command proves
the claim, run it in full, read the output and exit code, check whether it confirms the claim, and
only then say anything. Its failure table has one row that belongs on Sync's wall: **"Agent
completed" requires a VCS diff showing changes; "agent reports success" is not sufficient.** Sync's
`patch` node accepts an agent's word for a great deal.

`superpowers/skills/systematic-debugging/root-cause-tracing.md` is the same idea for post-mortems:
trace backward through the call chain to the original trigger rather than fixing where the error
surfaced. That process is only executable if the call chain survived the run, which is the
argument for section 3's first three recommendations.

### 2h. Replayable persisted traces — the one approach that matches Sync's problem

**`open-code-review` again, `internal/session/`.** VERIFIED, and this is the most valuable part
of the whole audit.

Every run streams a JSONL transcript to
`$HOME/.opencodereview/sessions/<encoded-repo-path>/<session-id>.jsonl`
(`internal/session/persist.go:19-21`, path built at `resume.go:59-69`). Record types, all written
through `writeRecordLocked` with a `parentUuid` chaining each record to the previous one
(`persist.go:35`, `:122-131`):

| record | writer | what it carries |
|---|---|---|
| `session_start` | `persist.go:133-138` | session id, repo, branch, model, review mode, diff range, resumed-from |
| `llm_request` | `persist.go:221-229` | file path, task type, request number, full messages |
| `llm_response` | `persist.go:243-251` | content, tool calls, model, `TokenUsage`, duration |
| `llm_error` | `persist.go:273-281` | error message, duration |
| `tool_call` | `persist.go:296-304` | tool name, arguments, result, ok flag, duration |
| `review_item_done` / `_reused` / `_failed` | `persist.go:172-186` | path, fingerprint, comments, source session, error |
| `session_end` | `persist.go:326-334` | duration, files reviewed, LLM failure count, the run manifest |

Three things are then built on that one file, and this is the architectural point:

1. **Resume.** `ResumeState` (`resume.go:16-36`) replays the JSONL into a read-only checkpoint
   index keyed by diff fingerprint, so `--resume <session-id>` skips work already done. The
   transcript is not a byproduct of the run; it *is* the checkpoint.
2. **A local read-only web viewer.** `internal/viewer/` serves repos → sessions → one session,
   reconstructing `TaskCard`s that pair each `llm_request` with its `llm_response` and the tool
   calls it made (`internal/viewer/store.go:284-306`), with per-file token breakdowns
   (`:249-266`). An operator can open a failed run and read the model's actual reasoning turn by
   turn. This is structurally the same product as Sync's console, over a JSONL file instead of
   Postgres.
3. **A versioned coverage manifest.** `RunManifest` (`internal/session/manifest.go:271-283`) is
   emitted once at `Finalize` and serialized into *both* the CLI JSON and the persisted session,
   with the explicit comment that the two outlets "can never compute coverage differently."

The manifest deserves its own paragraph because it is the best-designed artifact in this audit.

- `SchemaVersion` is `"ocr.run-manifest/v1"` (`manifest.go:20`) and consumers are told to gate on
  it and ignore unknown future versions.
- Failures are two fixed enumerations, not strings. `FailureClass` for items — provider, timeout,
  cancelled, configuration, input, budget, panic, unknown (`manifest.go:46-70`). `RunFailureClass`
  for the whole run — input, configuration, timeout, cancelled, budget, internal, unknown
  (`:73-93`). They are deliberately different sets, and the comment says why: a run never fails
  with "provider" or "panic" because those always attribute to a single item, and a run can fail
  "internal" because a scheduler can. `itemFailureForRunClass` (`:105-120`) maps a run-level stop
  onto the item-level colouring of its pending items, and where there is no equivalent the item
  falls back to `unknown` while `run_failure` keeps the precise cause.
- `TerminalState` is complete / partial / failed / skipped (`:156-167`), and the comment states it
  is "computed only from the coverage sets plus run_failure, never from comment count or
  warnings" — it explicitly replaced a warning-derived `completed_with_errors` status.
  `computeTerminal` is `:938-953`.
- `Coverage` is five disjoint sets where `selected` is the denominator and equals the disjoint
  union of the other four (`:225-232`), arrays always non-nil so JSON renders `[]` not `null`.
- `ItemID` (`:187-206`) is a SHA-256 over NUL-joined `(operation, mode, normalized old path,
  normalized new path)` — deliberately *content-independent*, so a file keeps its identity across
  a resume chain even when its diff changes. The content-dependent `Fingerprint` is kept as a
  separate field for checkpoint matching. Two identities for two jobs, and the comment says every
  call site must key on the same one "so a mismatched key never silently no-ops a transition."
- The builder has two explicit lifecycle boundaries beyond its mutex (`:305-330`): *sealed* closes
  the selected set before any dispatch so the denominator cannot widen mid-run, and *frozen* makes
  the whole thing immutable after `Finalize`. Mutating calls after either return errors —
  `errFrozen`, `errSealed`, `errEmptyID` (`:296-301`) — and the comment on that var block is the
  argument: "a silent no-op would let a mis-keyed or late transition drop an outcome and be
  discovered only at Finalize (or never)."
- `ManifestExecution` (`:255-263`) stores `RuleConfigSHA256` and `RuntimeConfigSHA256`, hashes
  rather than config, with the comment "never tokens, endpoints or raw config."
- **Every stored reason passes one redaction floor.** `sanitizeReason` (`manifest.go:659-684`) is
  called by the builder on every failure and waive reason, so no caller path can write an
  unredacted summary into an artifact that is serialized to two outlets. VERIFIED. It strips URL
  userinfo, `Bearer`/`Basic` tokens and credential-shaped `key=value` pairs, drops C0/DEL/C1
  control characters, collapses to one line, coerces to valid UTF-8, and caps at 500 *runes* so a
  multibyte character is never cut in half. The ordering comment (`:663-672`) is the part worth
  reading twice: UTF-8 coercion and control-character stripping must run *before* the redaction
  regexes, because an embedded control byte inside a token truncates the regex match — `Bearer
  AAA\x00BBB` matches only `Bearer AAA` — and the later strip would then remove the byte and
  splice the surviving `BBB` back in, leaking the tail of the secret. It is documented as a floor
  rather than a substitute for caller-side redaction, and it names what it does *not* strip:
  absolute local paths, cookies, and raw request or response bodies.
- **No selected item may end a run without an outcome.** `Finalize` (`manifest.go:739-818`) opens
  with a backstop sweep (`:762-790`): every item still in `selected` is moved to `failed` and
  coloured by a stated precedence — the run failure's class if one was recorded, else the pending
  failure cause, else `unknown` with the reason `"no terminal outcome recorded"`. VERIFIED. The
  sweep covers goroutines that exited early, cancellation before dispatch, deliberate coverage
  truncation, "or any path the caller forgot," and the comment is honest about its limit: it only
  runs when the process survives to call `Finalize`, and a hard kill falls back to the per-item
  JSONL checkpoints. The detail that makes it safe is the rollback at `:796-800` — if validation
  then fails, every swept item is restored to exactly its pre-sweep value and the builder is left
  unfrozen, so a caller can repair the problem and record the real outcome instead of being handed
  a manifest full of fabricated failures.

Finally, the exit-code contract at `cmd/opencodereview/review_cmd.go:253-262` follows from the
manifest rather than from an ad-hoc guess: non-zero only for a run-level failure or when every
selected item failed, so a budget stop that covered anything exits 0, and partial results are
published before the error decides the status.

**And the absence.** A grep for `prune`, `retention`, `MaxSessions`, `Cleanup`, `ttl` across
`internal/session/` returns nothing. VERIFIED. Sessions accumulate under `$HOME` forever, one
JSONL per run containing every prompt and every model response. That is unbounded disk growth and
an unbounded local corpus of source excerpts, with no documented lifetime. `codegraph`, which
stores far less sensitive data on someone else's server, has a documented 90-day purge.
`open-code-review`, which stores far more sensitive data on the user's own disk, has none.

**And the worse absence: the off switch exists and is not wired to anything.** VERIFIED, and this
is the single most instructive defect in the audit. `Config.ContentLog` is described at
`internal/telemetry/config.go:25` as "Include prompt/response content in log events". It defaults
to `false` (`config.go:15,36`), is settable by `OCR_CONTENT_LOGGING=1` (`config.go:56-58`), by a
`content_logging` key in `~/.opencodereview/config.json` (`config.go:66,102-104`), and by
`ocr config set telemetry.content_logging` (`cmd/opencodereview/config_cmd.go:494-500`, with its
own struct field at `:319`). It is read back by an exported accessor, `ContentLogging()` at
`internal/telemetry/provider.go:74-80`. **That accessor has no callers.** A grep for
`ContentLogging()` across `internal/` and `cmd/` returns only its own definition. Meanwhile
`WriteLLMRequest` (`internal/session/persist.go:221-229`) writes the full resolved `messages`
array — the prompt, including the customer's diff — on every request, unconditionally, gated by
nothing.

So a user who reads the config reference, sets `content_logging: false`, and confirms it with
`ocr config get` has changed nothing at all. Four layers of plumbing were built, tested
(`config_test.go` is 277 lines) and documented, and the one line that consults the result was
never written. This is a strictly worse failure than having no switch: no switch is a gap a user
can see, and a dead switch is a gap that reports itself as closed. It belongs in the same category
as `codebase-memory-mcp`'s `ingest_traces` returning `"accepted"` for data it drops (4.5) — a
control surface that lies — and it is the reason section 5's transcript question should be settled
before 3.3 is built rather than after. INFERENCE on intent: the naming and the config precedence
strongly suggest the switch was meant to gate the `llm_request`/`llm_response` records, but
nothing in the repository states that, and it is equally consistent with a plan to gate span
attributes that were never added.

---

## 3. What Sync should adopt

Each item names the reference file that proves it works and the Sync file it lands in. Sync's
current state is VERIFIED from the worktree at
`C:/Users/strol/orca/Sync/Sync/.claude/worktrees/sync-m4-dashboard/`.

### 3.1 Configure logging once, and make the format switchable

**Sync's current state.** Nine modules create a module logger — `src/sync/detect/parameter_deprecation.py:25`,
`src/sync/index/python_lang.py:59`, `src/sync/index/typescript.py:63`,
`src/sync/remediate/corpus.py:61`, `src/sync/signals/datadog/shapes.py:77`,
`src/sync/signals/generated/adapter.py:95`, `src/sync/signals/registry.py:111`,
`src/sync/signals/sentry/errors.py:51`, `src/sync/signals/sentry/shapes.py:58`. A grep for
`basicConfig`, `dictConfig` or `logging.config` across the repository returns hits only inside
`.venv`. VERIFIED. So no handler is ever installed: Python's last-resort handler emits `WARNING`
and above to stderr with no timestamp and no logger name, and every `log.info` and `log.debug`
in the codebase is discarded unconditionally. Concretely, `src/sync/remediate/corpus.py:266`
logs at debug the distinction between a run that never attempted a repair and one that attempted
and found no tier — a distinction its own comment says "an operator reading logs needs" — and
that line has never reached an operator. Meanwhile all operator-facing output is 44 `print()`
calls in `src/sync/cli.py` (plus one in `src/sync/mcp/server.py`), which cannot be filtered,
levelled, redirected or parsed.

**Adopt from** `codebase-memory-mcp/src/foundation/log.h:1-12` and `log.c:39-80`: one
initialisation entry point, level from an environment variable, and a text/JSON format switch on
the same variable-driven path.

**Lands in** a new `src/sync/obs/log.py` holding `configure(level, fmt)` plus a JSON formatter,
called once from `main()` in `src/sync/cli.py`, driven by `SYNC_LOG_LEVEL` and `SYNC_LOG_FORMAT`.
Keep the `print()` calls that are the CLI's deliberate human output; convert none of them
reflexively. The point is that the log stream starts existing, not that the CLI stops talking.

### 3.2 Give every run an identifier the operator can see and paste

**Sync's current state.** A run ID exists but only as a substring of a LangGraph thread ID:
`src/sync/cli.py:1054` builds `f"{finding.id}:{args.run_id or repo.head_sha[:12]}"` and
`src/sync/dashboard/queries.py:19-22` documents the convention. VERIFIED. It is never printed,
never logged, and never attached to a log record. An operator who watches a run fail has nothing
to search with.

**Adopt from** `open-code-review/cmd/opencodereview/review_cmd.go:216-219` (trace ID printed to
stderr) and `cmd/opencodereview/shared.go:330` (same ID inside the JSON result). The pattern is
one identifier, surfaced in both the human and the machine outlet, minted at the entry point.

**Lands in** `src/sync/cli.py`'s `run` command: mint the run ID unconditionally rather than
defaulting to `head_sha[:12]`, print it once on entry, bind it into a `logging` filter so every
record carries it, and return it in the dashboard's workflow payload from
`src/sync/dashboard/queries.py:223-227` so the console can display it beside the node timeline.

### 3.3 Capture the patch agent's transcript, not just its verdict

**This is the most serious gap and it sits directly under the product claim.**
`src/sync/remediate/agent_patch.py:328-331`:

```python
result: ResultMessage | None = None
async for message in query(prompt=prompt, options=options):
    if isinstance(message, ResultMessage):
        result = message
```

VERIFIED. Every `AssistantMessage`, every `ToolUseBlock`, every tool result streamed by the SDK is
iterated and dropped. What survives a `patch` node is a boolean, a diff, and a strategy name.
When an agent writes a wrong patch that compiles, there is nothing on disk that says what it read,
what it tried first, or why it chose that edit. Sync's console can render `patch → static_verify`
faithfully and still cannot answer the only question worth asking about that hop.

**Adopt from** `open-code-review/internal/session/persist.go:221-324`, where `llm_request`,
`llm_response` and `tool_call` records are written as the run proceeds, and
`internal/viewer/store.go:284-306`, where they are reassembled into per-task cards showing request,
response, tool calls, durations and per-file token counts.

**Lands in** `src/sync/remediate/agent_patch.py`, as a sink passed into `_drive_agent` that
appends one JSONL record per message; the file keyed by `(finding_id, attempt_index)` — the same
grain `migration_outcome` already declares at `src/sync/graph/schema.sql:168-170`. Storage choice
is section 5's first open question. Do not put the transcript in the LangGraph checkpoint: it is
large, it would be rewritten on every hop, and `src/sync/dashboard/queries.py:14-17` depends on
channel values staying small enough to inline in the `checkpoint` JSONB.

One constraint that must be settled before writing a line of this: the transcript contains
customer source. `migration_outcome`'s grain comment
(`src/sync/graph/schema.sql:171-175`) records that the table is safe to aggregate across customers
precisely because it stores no diff and no path. A transcript store has the opposite property, so
it needs its own retention rule and its own boundary — see 3.6.

### 3.4 Make `abandon_reason` a closed vocabulary alongside the prose

**Sync's current state.** `abandon_reason` is `str` on the state
(`src/sync/remediate/state.py:148`), `str | None` on the model
(`src/sync/core/models.py:290`), and `TEXT` in the column list at
`src/sync/graph/store.py:528`. It is written from free-form node text —
`src/sync/remediate/nodes.py:653,667`, with `nodes.py:433` noting the string names the stage
"because this becomes `abandon_reason` and a bare [reason] is unreadable." VERIFIED. The project
rule says abandoned runs are data and the reason stays queryable. Prose is *readable*, not
*queryable*: "which change kinds are not mechanically safe" is a `GROUP BY` question, and today it
is a `LIKE` question over sentences written by nine different call sites.

**Adopt from** `open-code-review/internal/session/manifest.go:46-93`, where item failures and run
failures are two separate fixed enumerations, plus `:105-120` where one maps onto the other, plus
`:938-953` where the terminal state is computed from those values and never from warnings.

**Lands in** `src/sync/remediate/state.py` as an `AbandonClass` literal type, a new
`abandon_class` column on `migration_outcome` in `src/sync/graph/schema.sql` (with the grain
comment updated *before* the column is added, per the standing rule), and the existing
`abandon_reason` retained as the human sentence. Two fields, one grep-able and one readable. The
`sync.core` import boundary is not at risk: this is an enum in `sync.core.models`, which is where
`Severity` already lives.

The `unknown` member is mandatory and should be named, not omitted —
`manifest.go:57` calls it "the mandatory catch-all: it only applies to an item that is known to
have failed but cannot be reliably mapped to a more specific class." An enumeration without an
escape hatch gets one anyway, spelled as a lie.

**And put a redaction floor on the prose half.** The sentence that stays free-form is written from
nine call sites (`src/sync/remediate/nodes.py:433,653,667` and the report paths), and at least one
of them composes it from `diagnostics` — raw `tsc` output. Compiler output quotes source lines,
and a source line can contain an API key as easily as anything else; a git remote in an error
string can carry userinfo. Sync's own rule is to validate at system boundaries, and the boundary
here is the write, not the nine callers. **Adopt** `open-code-review`'s `sanitizeReason`
(`internal/session/manifest.go:659-684`) — including its ordering argument, which is the part that
is easy to get wrong: coerce to valid UTF-8 and strip control characters *before* the redaction
regexes run, or an embedded control byte truncates a token match and the later strip splices the
unredacted tail back in. **Lands in** `src/sync/remediate/corpus.py`, in `_record` immediately
before `MigrationOutcome.from_attempt`, so that every row written to a table the project intends
to aggregate across customers has passed one function. Its docstring should name what it does not
strip, as the reference's does.

### 3.5 Record per-node duration in the checkpoint

**Sync's current state.** `src/sync/remediate/state.py:134` has `attempt_started_at: float`, one
timestamp per attempt, and `src/sync/remediate/corpus.py:283-284` turns it into a single
`wall_ms`. VERIFIED. `_EVIDENCE_KEYS` in `src/sync/dashboard/queries.py:47-56` maps each node to
its evidence and no entry is a duration. The console can therefore say `await_ci` is current and
cannot say it has been current for forty minutes, nor that `locate` took nine seconds last
Tuesday and ninety today.

**Adopt from** `open-code-review/internal/telemetry/events.go:49-61`, where `PhaseEvent` records
`phase`, `file.path` and `duration_ms` for every phase completion, error or not.

**Lands in** `src/sync/remediate/state.py` as a `node_ms: dict[str, int]` channel and a matching
entry in every node's return, surfaced through `src/sync/dashboard/queries.py`'s node loop at
`:213-221`. **This key needs a reducer declaration** — the standing rule in `CLAUDE.md` is that any
state key written by parallel branches must declare one, and a dict accumulated across nodes is
exactly the shape that silently drops writes without it. A merge reducer (`{**old, **new}`) is
correct here and costs nothing even while the graph stays sequential.

### 3.6 Set a retention rule before there is anything to retain

**Sync's current state.** No retention policy exists for checkpoint rows, and `migration_outcome`
is explicitly a keep-forever corpus (`src/sync/graph/schema.sql:174-175`: "It cannot be
backfilled"). VERIFIED. For the anonymised corpus, forever is the right answer and the schema
argues for it. For LangGraph checkpoints — which inline `RunState` values including `diagnostics`,
compiler output containing customer source — no argument has been made either way, and none can be
made retroactively.

**Adopt from** `codegraph/telemetry-worker/src/rollup.ts:1-35`: raw events purged on a stated
window, aggregates kept forever, purge bounded in batches, and — crucially — the retention rule
published in the same document as the schema. **Avoid** `open-code-review/internal/session/`,
which stores full prompts and responses under `$HOME` with no prune path anywhere in the package.

**Lands in** `src/sync/graph/schema.sql` as a grain-comment sentence on the checkpoint-adjacent
tables and, once 3.3 exists, on the transcript store; plus a `sync gc` subcommand in
`src/sync/cli.py`. The split codegraph uses is the right shape for Sync: the identifying, bulky
thing expires; the anonymised aggregate is forever.

### 3.7 Fill in the token columns that already exist

**Sync's current state, and this one is a live defect.** `migration_outcome` declares
`input_tokens`, `output_tokens` and `cache_read_input_tokens`
(`src/sync/graph/schema.sql:213-215`), and `src/sync/graph/store.py:526-527` lists them among the
written columns. `MigrationOutcome.from_attempt` accepts them via `**outcome`
(`src/sync/core/models.py:301-341`). But `src/sync/remediate/corpus.py:288-315` — the only caller
— passes no token argument at all, and a grep for `input_tokens` or `.usage` across
`src/sync/remediate/` returns nothing. VERIFIED. The three columns are therefore always NULL.

The consequence: `src/sync/benchmark/axes.py:115-116` computes
`_tokens(attempt) = (attempt.input_tokens or 0) + (attempt.output_tokens or 0)`, so the
`tokens_per_merged_patch` axis — one of six axes the benchmark reports — is structurally zero for
every run ever recorded. The module's docstring at `axes.py:35-44` argues carefully about why
cache reads are excluded from the cost total, and the total it is arguing about does not exist.
INFERENCE on the "every run ever recorded" clause: I did not query the database, only the write
path, and the write path has no route for those values.

**Adopt from** `claude-cookbooks/claude_agent_sdk/utils/agent_visualizer.py:258-267,505-517`: read
`total_cost_usd` and `usage` off the SDK's `ResultMessage` and treat the reported cost as
authoritative rather than recomputing a price. Sync's `agent_patch.py` already holds that exact
object at `:328-331` and reads only `is_error` and `subtype`.

**Lands in** `src/sync/remediate/agent_patch.py` (capture `result.usage` and return it),
`src/sync/remediate/state.py` (carry it per attempt), and `src/sync/remediate/corpus.py:288`
(pass it through the existing `**outcome`). This is the cheapest fix in this note — the columns,
the model field and the benchmark consumer all already exist — and per the standing rule it needs
a failing test first: an assertion that a recorded attempt has non-NULL `input_tokens`, watched
to fail against today's code.

### 3.8 Instrument the detector's decision distribution

**Adopt from** `codegraph/docs/design/telemetry.md`'s `usage_rollup` section, where the prompt
hook's gate outcome is rolled up under ten fixed counter names and the doc states the reading:
a rising `noop-*` share against the `high`/`medium` tiers means the gate is missing real
questions.

Sync's DETECT stage is the same shape of heuristic and carries far more weight — a suppressed
finding is an invisible false negative, and false negatives leave no trace at all today. Counting
detector outcomes by fixed name (`emitted`, `suppressed-no-binding`, `suppressed-rung-static`,
`suppressed-below-severity`, and so on) turns detector quality into a query. **Lands in** the
DETECT modules under `src/sync/detect/` plus a small counter table in
`src/sync/graph/schema.sql`, whose grain would be one row per `(day, detector, outcome)`.

This is the one recommendation whose value is strategic rather than operational: Sync's stated
differentiator is the binding, and nothing currently measures how often the binding logic declines
to speak.

### 3.9 Distinguish a node that has not run yet from one that never will

**Sync's current state.** `workflow_state` classifies every node as `current`, `done` or
`pending`, and `pending` is the fallback branch — `else: status = "pending"` at
`src/sync/dashboard/queries.py:218-219`. VERIFIED. A node is `pending` when it is absent from
`versions_seen`, which is true both for a node the run has not reached yet and for a node the run
will never reach because the process was killed at `await_ci` three days ago. The console renders
those identically, forever. `_pending_node` (`:230-244`) reads the checkpoint honestly, but a
checkpoint that stopped being written says nothing about why, and the newest-checkpoint query at
`:190-197` has no staleness bound.

The corresponding gap in the corpus is narrower than it first looks, and worth stating precisely.
`record` has three call sites: `nodes.py:217` on a retry (`terminal_status="retried"`), `:571` on
a pull request (`"opened"`), and `:653` on abandonment (`"abandoned"`). VERIFIED. So an
interrupted run that had already retried at least once leaves a row; a run killed during its first
attempt leaves nothing, because `src/sync/remediate/corpus.py:248-260` also returns `False`
without a row whenever `attempt_index < 1` or the finding, site or change is missing. The
population that goes unrecorded is therefore exactly first-attempt deaths — which is the
population most likely to indicate a node that hangs rather than a repair that is hard. The
project rule says abandoned runs are data; a run that was *interrupted* before it ever retried is
currently not data at all.

**Adopt from** `open-code-review/internal/session/manifest.go:739-800`: the `Finalize` backstop
sweep moves every item still lacking an outcome into `failed` with a stated class, under a
documented precedence, and reverts the whole sweep if validation then fails. Its comment is also
honest about the limit — the sweep only runs if the process lives to call `Finalize`, and a hard
kill falls back to the per-item checkpoints written as the run proceeded. Both halves matter:
a finalizer for the recoverable case, and durable per-step records for the case where there is no
finalizer.

**Lands in** two places. First, `src/sync/dashboard/queries.py`: carry the newest checkpoint's
timestamp out of the query at `:190-197` and let the node loop distinguish `pending` from
`stalled` past a threshold, which is a read-only change and needs no schema. Second — the larger
one — a terminal sweep in `src/sync/remediate/graph.py`'s exit path that records an attempt row
with the `abandon_class` of 3.4 set to an `interrupted` member for any run whose state carries an
`attempt_index >= 1` and no `terminal_status`. That second half depends on 3.4 landing first, and
on the ruling in section 5 about whether an interrupted run is the same kind of fact as an
abandoned one.

---

## 4. Where Sync is already ahead, and where a reference would be a step backwards

### 4.1 The checkpoint-derived node timeline is better than any reference's run view

`src/sync/dashboard/queries.py:230-244` reconstructs the pending node from LangGraph's own
`channel_versions` and `versions_seen` — comparing each node's `branch:to:<node>` trigger version
against the version that node last consumed. The docstring calls it "the checkpointer-row shadow
of Pregel's own next-task rule," and names the property that makes it worth the effort: a `patch`
node that already ran once and is due again renders as *current*, not *done*, so a retry loop
reads honestly.

No reference here does this. `open-code-review`'s viewer reconstructs a finished session from an
append-only log — it can show what happened but is not derived from the executor's own scheduling
state, so a re-entered phase is a second card rather than a node that is current again.
`code-review-graph`'s daemon has state but no per-stage view. Sync gets live, correct, mid-flight
run state for free from a data structure it was already writing. Do not trade this for an
event-log design.

The related correctness detail at `queries.py:206-209` — reporting `outcome` only when it is
terminal, because `locate` writes `running` on the first hop and a console that treated `running`
as terminal would stop polling a live run — is the kind of thing that is obvious once written and
absent from every reference's equivalent.

### 4.2 `migration_outcome` is a better artifact than `RunManifest` in three respects

`RunManifest` is per-run, JSON, and lives in a file. `migration_outcome`
(`src/sync/graph/schema.sql:168-236`) is per-attempt, relational, and carries a natural key with a
declared conflict clause (`UNIQUE (finding_id, attempt_index)` at `:235`, with the comment that a
restarted run "must converge rather than inflate the corpus, and an inflated corpus silently
overstates every rate computed from it"). It is also privacy-shaped by construction — symbol is a
shape, argument keys are salted digests, neither diff nor path is stored — which is what makes it
aggregable across customers. `open-code-review` hashes its *config* but stores full prompts and
responses beside the manifest, so its manifest's discretion is undone by the file it sits in.

And Sync's table declares its grain in a comment, which `RunManifest` does not: an operator
reading `ocr session list` output has to infer from `SelectedFiles`/`CompletedFiles`
(`internal/session/list.go:32-36`) that the unit is a file rather than a run.

### 4.3 Full OTel would be a step backwards *today*

`open-code-review` spends 2201 lines on `internal/telemetry/`, roughly a thousand of them tests,
to get spans, metrics and OTLP export. For a solo, self-funded project whose pipeline runs as a
CLI against one customer repository at a time, the operational return is small: there is no
collector, no Grafana, no on-call rotation, and no multi-tenant service where a `p99` matters.
What Sync actually needs is the *narrow* thing OTel gives you — a correlation ID, per-node
durations, and typed outcomes — and all three are available for a fraction of the cost via 3.2,
3.5 and 3.4.

The specific cost of adopting OTel prematurely is worse than the line count. `sync.core` imports
nothing from any sibling package, enforced by `tests/test_import_boundary.py`. An OTel dependency
that a vendor adapter author inherits is the same category of harm as inheriting Postgres, and it
is more insidious because `opentelemetry-api` looks harmless. If OTel ever lands it must land in a
sibling package that adapters never import, and the no-op-span pattern from
`internal/telemetry/span.go:22-27` is what makes that possible without conditionals at call sites.
Adopt the *pattern* now; defer the *dependency*.

### 4.4 Two references' approaches would be actively harmful

**Fail-silent metric registration.** `open-code-review/internal/telemetry/metrics.go:70-72` is a
function whose body is empty, discarding every metric registration error, with a comment saying
telemetry must not interrupt the main flow. That is correct for a dashboard counter and wrong for
Sync, where the same numbers feed tier routing through `migration_outcome`. Sync's own precedent is
better: `src/sync/remediate/corpus.py:275` logs a warning when a row is omitted because no tier
ran, naming the finding and the attempt. A recording failure Sync cannot see is a routing decision
Sync will make on partial data.

**Silent degradation announced by `console.warn`.** `Understand-Anything`'s parsers warn to the
console when they fall back to regex extraction or detect unbalanced braces
(`packages/core/src/plugins/parsers/yaml-parser.ts:82`,
`terraform-parser.ts:126`, `protobuf-parser.ts:137`) and then return the degraded result to a
caller that cannot tell. Sync's tree-sitter indexers have the same failure available to them. The
rung column is the right answer and Sync already has it: a degraded extraction must change the
binding's rung, not print a sentence. Nothing in this audit should be read as licence to move any
degradation signal from the graph into the log.

### 4.5 One reference behaviour Sync must never copy

`codebase-memory-mcp`'s `ingest_traces` returns `{"status":"accepted"}` for spans it discards
(`src/mcp/mcp.c:10885-10914`), while advertising itself at `src/mcp/mcp.c:664` as ingesting runtime
traces to enhance the knowledge graph. There is a supporting header full of OTLP structs
(`src/traces/traces.h`) and no code path from the handler to it. This is the exact defect class the
repository's own operator interface cannot surface: a success report for work not done.

Sync is not immune, and its shape is the same. `sync.remediate.agent_patch` returns a patch whose
`ResultMessage` said success; `migration_outcome` writes `terminal_status` from a node's own
account of itself. `superpowers/skills/verification-before-completion/SKILL.md`'s failure table
names the antidote in one row: an agent's completion claim requires a VCS diff, not the agent's
report. Sync partly does this — `static_verify` is an independent check on the tree a push would
carry — and partly does not, because nothing independently verifies that the patch attempted the
change the finding described.

---

## 5. Open questions only the project's owner can settle

**Where does the agent transcript live, and who is allowed to read it?** It contains customer
source, model reasoning about that source, and tool arguments. Postgres beside the checkpoints
keeps one storage system and puts it behind the same access boundary as everything else; a JSONL
file per attempt is cheaper, streamable, and trivially deletable, which matters more if the answer
to the retention question is short. `open-code-review` chose files under `$HOME`
(`internal/session/persist.go:19-21`) and then never wrote a prune path. Choosing the store and
choosing the lifetime are the same decision and should be made in one sitting.

**Does the customer see the transcript?** There is a real product argument that the transcript
*is* the differentiator — a pull request that ships with "here is exactly what the agent read and
tried" is a different product from one that ships a diff. There is an equally real argument that
exposing it turns every agent misstep into a support conversation. This decision changes 3.3's
design: a customer-visible transcript needs redaction, a schema version, and a stability promise;
an internal one needs none of those.

**What is the retention window for LangGraph checkpoints?** They inline `diagnostics` — raw
compiler output containing customer source — into the `checkpoint` JSONB, which is precisely what
makes `src/sync/dashboard/queries.py` able to read state without the serialiser
(`queries.py:13-17`). That convenience is also a retention liability. codegraph's split of
"identifying data expires, anonymous aggregate is forever" maps cleanly onto Sync's checkpoints
versus `migration_outcome`, but the window itself is a business decision: 30 days is enough to
debug, 90 is enough to spot a pattern, and forever is a promise to a future auditor.

**Is `abandon_reason`'s vocabulary stable enough to close?** 3.4 proposes a closed enum beside the
prose. Enums are expensive to change once written into a table that cannot be backfilled — the
same schema comment that makes `migration_outcome` valuable
(`src/sync/graph/schema.sql:174-175`) makes it unforgiving. `open-code-review` shipped two
enumerations of eight and seven members with a mandatory `unknown` in each; whether Sync's
abandonment causes are that well understood yet is a judgement only the person who has read the
abandoned runs can make.

**Does anything ever leave the customer's machine?** Every telemetry recommendation in section 3 is
local: logs to stderr, transcripts to disk or the local Postgres, counters to a table. codegraph's
model — a first-party endpoint, a published allowlist, a public ingest source, `DO_NOT_TRACK`
honoured — is the strongest template available for the day Sync wants aggregate signal across
customers, and `migration_outcome`'s privacy shape means Sync is unusually close to being able to
ship it. But that is a positioning decision for an open-core product with a trust story, not an
engineering one, and nothing in this audit argues for making it now.

**Is an interrupted run the same kind of fact as an abandoned one?** 3.9 proposes sweeping runs
that died mid-flight into `migration_outcome` with their own class. The argument for is that
`migration_outcome`'s stated purpose is routing learning, and a change kind whose runs reliably die
at `await_ci` is exactly the signal routing wants. The argument against is that the table's grain
is one *attempt*, an interrupted attempt has no verdict, and a swept row inflates every denominator
computed from the table — the same harm the `UNIQUE (finding_id, attempt_index)` natural key at
`src/sync/graph/schema.sql:234` exists to prevent, arriving through a different door.
`open-code-review` resolved the equivalent question by keeping the swept items inside `coverage`
but forcing the terminal state to be computed from the sets rather than inferred
(`manifest.go:938-953`), which is a third option: record it, and make every rate that reads the
table state which classes it counts. Whichever way this goes, it should be decided before 3.4's
enum is written, because the answer determines whether `interrupted` is a member of it.

**Should DETECT's suppression counters be part of the graph or beside it?** 3.8 proposes counting
detector decisions. The project rule says anything that does not read from or write to the API
Dependency Graph should be questioned. A suppression counter reads from the graph and writes
nowhere near it, which makes it the first thing in this audit that the rule genuinely puts under
suspicion — and possibly the first case where the rule should bend, since a false negative is by
definition a fact about a binding that does not exist.
