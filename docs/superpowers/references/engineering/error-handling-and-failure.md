# Error handling and failure modes

Audited 2026-08-04 against nine reference repositories cloned under
`scratchpad/engrefs/`. Every claim below is labelled VERIFIED (read this session, path and
line given), REPORTED (a comment or document in the repository asserts it and I did not run
it), or INFERENCE (my reasoning from what I read).

## 1. What this dimension covers, and why it matters here

The question is not "does this code have try/except". It is: when something goes wrong, does
the system's own record of what happened stay true? Three sub-questions decide that.

**Is there a type-level difference between an expected negative answer and a genuine
failure?** "No vendor changes since Tuesday" and "the vendor feed could not be fetched" are
both often rendered as an empty list. Once they are the same value, no consumer downstream
can ever separate them again, and every dashboard, metric, and routing decision built on top
inherits the ambiguity.

**Is a failure retried on evidence, or on hope?** A retry loop that cannot name which
failures are transient will retry a rejected API key ten times and then return a value that
looks like an answer.

**Where a run stops short, is the stop recorded as data or as an absence?** Sync's own rule
says abandoned runs are data and `abandon_reason` stays queryable, because that column is
where routing learns which change kinds are not mechanically safe. A system that expresses
"could not finish" by returning `None`, `[]`, or `""` has thrown that training signal away
at the moment it was generated.

For Sync specifically this is load-bearing in three places. The product claim is the
binding, so a false positive that cannot be attributed to a rung cannot be fixed — and the
same argument applies to a failure that cannot be attributed to a cause. The verification
gate decides whether a pull request opens, and `sync/remediate/state.py:39-42` already
records that a real `tsc` failure can exit non-zero with nothing on either stream, which
means "diagnostics is empty" is not a usable proxy for success. And the console just built
on `sync.api.app` renders a run's state to an operator, where a swallowed error becomes a
lie told with a green tick.

## 2. The design space across the references

### Approach A — a closed enumeration of stop causes, recorded at the trigger site

`open-code-review` is the strongest example in the set, and it is close enough to Sync's
`abandon_reason` that the comparison is direct.

VERIFIED. It carries *two* disjoint failure enumerations. `internal/session/manifest.go:46-60`
defines `FailureClass` — `provider`, `timeout`, `cancelled`, `configuration`, `input`,
`budget`, `panic`, `unknown` — attached to every failed coverage item. `manifest.go:74-95`
defines a separate `RunFailureClass` — `input`, `configuration`, `timeout`, `cancelled`,
`budget`, `internal`, `unknown` — for why the whole run stopped. The comment at 74-83 states
why they are not one enum: a run never fails with `provider` or `panic`, because those are
always attributable to a single item, and a run needs `internal` for a scheduler invariant
violation, which no item can have. `manifest.go:116-131` maps between them explicitly and
documents that `internal` and `unknown` have no item-level equivalent, so swept items degrade
to `FailureUnknown` while the run-level record keeps the precise cause.

VERIFIED. Classification happens where the failure occurs, never inferred later.
`internal/agent/agent.go:991-1002` is `classifyItemError`, which uses `errors.Is` against
`context.DeadlineExceeded`, `context.Canceled`, and a declared sentinel `errMainTaskEmpty`
(declared at `agent.go:981` precisely so callers do not match on error text). The comment at
`manifest.go:406-411` on `SetRunFailure` says it outright: "Callers must record the cause at
the trigger site — `Finalize` never infers it from context state." `SetRunFailure` also
rejects an invalid class and refuses to change an already-set class, so first-cause wins and
an unclassifiable stop is never silently downgraded.

VERIFIED, and this is the piece Sync does not have. `manifest.go:938-955` is
`computeTerminal`: the run's terminal state is *derived* from coverage plus `run_failure`,
never asserted. Zero selected items is `skipped`; no failures is `complete`; all failed is
`failed`; anything between is `partial`. A run cannot report success while carrying failed
items, because the success value is computed from the same data the failures live in.

VERIFIED. `manifest.go:141-156` adds a third category that neither Sync nor any other
reference here models: `pendingFailureCause`, a *controlled coverage truncation*. The run
deliberately stopped covering the remaining items — a budget ceiling, say. Those items are
marked failed and count against coverage, but the run itself did not fail and its terminal
state stays coverage-derived. That is a fourth outcome beside "succeeded", "abandoned", and
"nothing to do".

`codebase-memory-mcp` does the same thing one layer down, for subprocesses.
`src/foundation/subprocess.h:26-34` classifies how a supervised child ended into
`CBM_PROC_CLEAN`, `CBM_PROC_EXIT_NONZERO` (annotated "a graceful failure"), `CBM_PROC_CRASH`
(POSIX fault signals or a Windows NTSTATUS exit code `>= 0xC0000000`), `CBM_PROC_HANG`,
`CBM_PROC_KILLED`, and `CBM_PROC_SPAWN_FAILED` — "no child ever ran". VERIFIED. The result
struct at `subprocess.h:37-45` goes further and carries `supervision_failed` and
`tree_quiesced`: a terminal result that admits the supervisor could not prove the process
tree was actually gone. The header comment at `subprocess.h:99-111` says callers must log
that as a critical teardown failure. That is a system declining to report a clean answer it
cannot substantiate.

### Approach B — a discriminated union where "unknown" is a first-class status

`Understand-Anything` models graph freshness as a four-arm union at
`understand-anything-plugin/packages/core/src/staleness.ts:18-54`: `fresh`, `dirty`, `stale`,
`unknown`. VERIFIED. Two properties make it better than a boolean plus an error channel.

First, `unknown` carries a `reason` typed as `GraphFreshnessUnknownReason`
(`staleness.ts:11-16`), a closed set of five values including `git-command-timeout` and
`git-head-unavailable`. `staleness.ts:144-149` shows `unknownReason` promoting a
`GitCommandError` with `timedOut` set to the timeout reason rather than the generic fallback,
so a five-second git hang (`GIT_TIMEOUT_MS` at `staleness.ts:69`) is distinguishable from a
missing commit. Every failing git call in `evaluateGraphFreshness` returns an `unknown` result
rather than throwing — `staleness.ts:232-238`, `255-261`, `344-351`.

Second, the `fresh` arm types `changedFileCount: 0`, `changedFiles: []`, `commitsBehind: 0`,
`commitsAhead: 0` as *literal* types, not `number` and `string[]`. VERIFIED at
`staleness.ts:19-28`. A "fresh" result carrying a changed file will not compile. That is the
type system enforcing what a comment would otherwise ask for.

`codegraph` reaches for the same shape more locally. `src/extraction/index.ts:1696-1697`
buffers each file's parse as `{ ok: true; ... } | { ok: false; filePath: string; err: unknown }`,
and `flushOrdered` at `index.ts:1799-1812` routes the `ok: false` arm into
`recordParseFailure` (`index.ts:1776-1786`), which increments `filesErrored` and pushes a
structured `ExtractionError` with `code: 'parse_error'` onto the result. A parse failure
becomes a row in the answer, not a gap in it. Same idea at
`src/resolution/index.ts:1623-1639`.

`codegraph` also carries a conservation invariant I have not seen elsewhere.
`src/extraction/index.ts:93-99`: `IndexResult.filesDiscovered` is "the ground truth the
indexed/skipped/errored tallies must add up to. A shortfall means files were silently dropped
mid-pipeline (e.g. a killed worker under load) and the index is PARTIAL; callers surface that
rather than trusting the counts." VERIFIED as a documented field with that comment. That is a
detector for the failure mode where nothing threw and the answer is still wrong.

### Approach C — classify the exception at the boundary, then retry only what is transient

`code-review-graph` has the best-argued retry loop in the set, at
`code_review_graph/embeddings.py:471-598` (OpenAI) and `700-790` (Voyage). VERIFIED.
`max_retries = 3`, backoff `wait = 2 ** attempt` (`embeddings.py:591`), and the retryable set
is enumerated at `embeddings.py:566-586`: HTTP 429 and 5xx, plus `URLError`, `socket.timeout`,
`TimeoutError`, `ConnectionError`, `ssl.SSLError`, and — with a comment naming
Cloudflare-fronted endpoints and LiteLLM as the observed triggers —
`http.client.IncompleteRead`, `BadStatusLine`, and `RemoteDisconnected`. Everything else,
including other 4xx and any malformed response, re-raises immediately: "those are caller-side
bugs that will keep failing on retry."

The inner structure is the subtle part. At `embeddings.py:480-487` a 429/5xx is deliberately
*re-raised as the original `HTTPError`* rather than wrapped, with the comment "We must not
convert to `RuntimeError` here or retry below can't tell it was a transient HTTP failure."
Other 4xx get their response body parsed and wrapped so the operator sees the gateway's actual
reason instead of "400 Bad Request". Converting an error to a friendlier type destroys the
information the retry policy needs; this code knows that and orders the two steps accordingly.

The same function contains the single best example in the whole audit of refusing a plausible
answer. `embeddings.py:522-559` handles three disjoint shapes of an embeddings response —
all items carry an integer `index`, no item carries one, or some do and some do not. The first
two are handled. The third raises: "OpenAI API returned mixed indexed/unindexed data — refusing
to misalign vectors." It would have been trivial to zip in server order and return something.
The code declines, because a misaligned vector is a wrong answer that never looks wrong.

`PageIndex` reaches for the same classification and gets the boundary right while getting the
result type wrong — see Approach E. VERIFIED: `pageindex/utils.py:46-53` defines
`_UNRECOVERABLE_STATUS = frozenset({401, 403, 404})` with a comment stating the constraint
("no retry can fix a rejected key or a model that does not exist") and, unusually, stating
what was deliberately *excluded* and why: 400 is not in the set because it also carries
`context_length_exceeded`, which is a per-prompt failure the caller absorbs. The same
classifier is reused in the tree expansion loop at `pageindex/tree_optimize.py:679-681`, where
an unrecoverable error re-raises with the comment "every remaining node would fail
identically". That comment is the argument for fail-fast stated in one line.

`claude-cookbooks` documents the provider-side version of the same distinction, and it is the
one most directly relevant to Sync's agent calls. `fable_5_fallback_billing/guide.ipynb` cell 3
(REPORTED — I read the notebook source, did not execute it) explains that a classifier block
returns **HTTP 200** with `stop_reason: "refusal"`. The instruction is explicit: "Branch your
logic on `stop_reason`, not on `content` or `stop_details`. `stop_details` is informational and
can be `null`." Cell 7 adds `served_by_fallback`, which reads `usage.iterations` rather than
looking for a `fallback` content block, because a sticky-served turn carries no block —
i.e. the obvious in-band signal is *incomplete* and the authoritative one is elsewhere. This is
exactly the failure Sync's own `verify_ok` comment guards against: routing on the shape of an
output rather than on a field a producer set deliberately.

### Approach D — a last-resort handler that exits rather than continues

`codegraph/src/bin/fatal-handler.ts:1-33` is worth reading in full and is the clearest
statement of this dimension's thesis I found anywhere. VERIFIED. The file documents that the
CLI previously overrode Node's default for uncaught exceptions and unhandled rejections with
"log the error and keep running", and names two production incidents that caused: issue #799,
where a stdin socket error was logged and the process kept running, orphaning a detached MCP
daemon and spinning a POLLHUP fd at 100% CPU; and issue #850, where logging a *different*
uncaught exception forced V8 to lazily format `.stack`, which entered a non-terminating
source-position walk and pinned a core — and because the handler kept the process alive, the
daemon's own watchdog and idle timers could never fire, leaving it wedged until a manual kill.

The fix has two properties the file calls load-bearing and says are covered by tests:
`describeFatal` (`fatal-handler.ts:38-54`) never reads `error.stack` and never hands the raw
Error to `console.*`, because that formatting step is itself the hang; and the write goes
synchronously to fd 2 before `exit`, since `process.exit()` does not drain async streams.
This is a swallowed-error postmortem written into the source by the people it bit.

`open-code-review` takes the opposite-but-compatible position for *isolated* work.
`internal/agent/agent.go:585-601` recovers a panic in a per-file review goroutine, but the
recovery is not a swallow: it increments `subtaskFailed`, marks the item `FailurePanic` in
the manifest with a fixed safe reason, records the detail in the session checkpoint, emits a
telemetry error event, and records a warning. The panic becomes five pieces of durable
evidence. The comment says the intent directly — "isolated exactly like an error return … so
other files still complete and the all-failed rollup below stays correct."

The contrast within the same repository is instructive. `internal/llmloop/pool.go:93-100`
recovers a panic in the comment worker pool and does nothing but print to stdout. The work
that panicked contributes no comments; nothing counts it. VERIFIED. That path can silently
shrink a review's output, and unlike the agent path there is no tally that would notice.

### Approach E — the sentinel that eats the failure

This is the anti-pattern, and the references supply clean specimens.

`PageIndex/pageindex/utils.py:88-99`. After ten attempts one second apart (no backoff — a flat
`time.sleep(1)`), `llm_completion` logs "Max retries reached" and **returns `""`**. The async
twin at `utils.py:130-140` does the same. VERIFIED. Every caller then treats that empty string
as model output. `pageindex/page_index.py:989-996` parses it with `extract_json`, which on
failure returns `{}` (`utils.py:176-188`, including a bare `except:` at line 183), and then
`.get('completed', 'no')` yields `"no"`.

The consequence is that a total provider outage is indistinguishable from a confident negative
answer — and this is not an oversight, it is *asserted by the test suite*.
`PageIndex/tests/test_issue_163.py:19-31` patches `llm_completion` to return `""` and asserts
`toc_detector_single_page(...) == "no"`; `test_issue_163.py:56-59` asserts `detect_page_index`
returns `"no"` on an empty response. VERIFIED. The tests are titled `TestRobustKeyAccess`, and
they do make the code not crash. They also lock in "the model was unreachable" and "this
document has no table of contents" as the same value.

Other specimens in the same repository: `pageindex/page_index_md.py:5-8` is a bare `try:
from .utils import * / except: from utils import *`, which will swallow any error raised
during import of `utils`, not just `ImportError`. `pageindex/page_index.py:161-166` gathers
concurrently with `return_exceptions=True` and, on an exception, sets `item['appear_start'] =
'no'` — the failure becomes the negative answer again, one item at a time.
`page_index.py:1008-1013` does the same and drops the item entirely, shrinking the result set
with only a `print`. `pageindex/retrieve.py:134` catches bare `Exception` and returns a JSON
`{'error': ...}` to the agent, which at least is honest, but sits beside all of the above.

`Understand-Anything` supplies the cleanest contrast, because the same file gets it right and
wrong. `staleness.ts:361-378` — `getChangedFiles` catches everything and returns `[]`, and the
docstring says so plainly: "Returns an empty array if there are no changes **or if git
encounters an error**." VERIFIED. Two hundred lines above, `evaluateGraphFreshness` was
returning `status: "unknown"` with a typed reason for the same class of git failure. The
better model was already in the file. Also `packages/core/src/analyzer/llm-analyzer.ts:140`
and `:183` — both `parseFileAnalysisResponse` and `parseProjectSummaryResponse` end in
`} catch { return null; }`, so a malformed model response and an absent one are one value.

`codegraph` carries a large number of `catch {}` blocks — 114 catches in `src/` outside tests
— but most are annotated with an explicit degradation contract:
`src/bin/codegraph.ts:231` ("telemetry must never break the CLI"), `:476` ("detection is
advisory"), `:1379` ("Degradable by contract: never surface an error to the prompt pipeline"),
`src/db/index.ts:468-472` and `:479-483` (a missing WAL sidecar is legitimately size zero).
VERIFIED. INFERENCE: these are defensible individually, because each names a subsystem whose
failure genuinely must not propagate. The risk is aggregate rather than local — a codebase
where "degradable by contract" is a common phrase drifts toward it being the default answer.

`code-review-graph` has the widest spread of swallow quality. Good:
`communities.py:954-956` catches `BaseException` purely to roll back a transaction and
re-raises, which is the correct use of the broadest catch. `daemon.py:854-862` catches a config
parse failure and keeps the last good config, logging with `exc_info=True` and returning — a
named, reversible degradation. Weaker: `communities.py:720-727` logs "Failed to split
community, keeping as-is" and appends the unsplit community, so the output silently contains
oversized communities the caller asked to have split. Weakest: the installer path at
`cli.py:366-406` wraps four separate `install_*_hooks` calls in `except Exception as exc:
logger.warning("Could not install X hooks")` and continues, then unconditionally prints "Next
steps: … Restart your AI coding tool to pick up the new config". VERIFIED. An installation that
installed nothing reports the same closing message as one that succeeded.

### Approach F — repositories with essentially no runtime error model

`superpowers` and `skills` are skill libraries: markdown plus a handful of shell scripts.
VERIFIED. `superpowers` uses `set -euo pipefail` consistently
(`hooks/session-start:4`, `scripts/bump-version.sh:11`, `scripts/lint-shell.sh:11`,
`scripts/package-codex-plugin.sh:10`, `scripts/sync-to-codex-plugin.sh:29`). Its one notable
swallow is `hooks/session-start:10`, which reads the skill file with `2>&1 || echo "Error
reading using-superpowers skill"` and then `exit 0` at line 49 — a hook whose payload failed
to load still reports success to the host, and the agent silently starts without its mandate.
`skills` contains no runtime code worth auditing on this dimension; its only relevant
statement is `skills/engineering/codebase-design/SKILL.md:16`, which lists "error modes"
among the things a module's *interface* must declare, alongside invariants and ordering
constraints. That is the right doctrine and there is no code in the repository to test it
against.

## 3. What Sync should adopt

**A typed `unknown` for the workflow reader, instead of one `None` covering three
situations.** `src/sync/dashboard/queries.py:181-199` returns `None` when the checkpointer
database has no `checkpoints` table at all (line 185), and again when no thread matches the
finding (line 198-199). `src/sync/api/app.py:144-149` turns both into the same 404 body,
`{"error": "workflow not found"}`. VERIFIED by reading both files. Those are two different
facts: "Sync has never remediated this finding" and "the console is pointed at a database
that has never held a run". An operator debugging a deployment cannot tell them apart, and
neither can a support ticket. `Understand-Anything`'s
`staleness.ts:11-16` plus `:49-54` shows the fix at the smallest possible cost — a closed
`Literal` of reasons and a fourth arm on the return type. It would land as a
`{"status": "no-run", "reason": "..."}` payload from `workflow_state`, with `app.py` mapping
only the genuine "no such finding" case to 404.

**A terminal state for a run that died between hops.** VERIFIED: `queries.py:209` deliberately
suppresses the `running` outcome so the console keeps polling, and `Outcome`
(`src/sync/remediate/state.py:15`) has no value meaning "the process stopped without reaching
a terminal node". INFERENCE, and I consider it high-confidence: a run killed mid-flight — an
OOM, a CI runner reclaimed, a `Ctrl-C` — leaves its last checkpoint with `outcome: "running"`,
which `queries.py` renders as `outcome: null` and a `current` node forever. The console polls a
dead run indefinitely and shows it as in-progress. `open-code-review` solves this by deriving
the terminal state rather than asserting it (`internal/session/manifest.go:938-955`): there,
a run with unfinished selected items *cannot* read as complete, because completeness is
computed from coverage. The cheapest Sync analogue is a staleness rule in `workflow_state` —
newest checkpoint older than some bound with a non-terminal outcome reads as `stalled`, with
the last node reached carried as the reason. That is a query-side change in
`src/sync/dashboard/queries.py`, requiring no schema work.

**Refuse an ambiguous vendor response rather than guessing at it.**
`code-review-graph/code_review_graph/embeddings.py:522-559` is the model: three disjoint
response shapes, two handled, the mixed one raising rather than zipping in server order.
Sync's equivalent surface is the vendor adapter boundary in `sync.signals.*` — anywhere an
adapter joins a vendor's change list against operation ids. The rule to import is that a
partial or inconsistent correspondence is a refusal, not a best-effort alignment, because a
binding attributed to the wrong operation is exactly the false positive the rung column exists
to make fixable and would arrive already mis-attributed.

**Classify subprocess termination, not just its exit code.**
`codebase-memory-mcp/src/foundation/subprocess.h:26-45` separates clean exit, graceful
non-zero exit, crash, hang, killed, and spawn-failed, and adds `supervision_failed` for the
case where even the classification could not be established. Sync already knows it needs this:
`src/sync/remediate/state.py:39-42` records that a real `tsc` failure can exit non-zero with
nothing on either stream, citing a silent `npx` fetch failure. Today `src/sync/index/tsc.py`
catches `subprocess.TimeoutExpired` (line 172) and `src/sync/index/deps.py` likewise (line
106), which is the timeout arm only. A crash of the toolchain and a compiler that rejected the
patch are both `verify_ok = False`, and only one of them is evidence about the patch. This
lands in `src/sync/index/tsc.py`, and the payoff is a distinct `abandon_reason` so routing
never learns "this change kind is not mechanically safe" from a broken node install.

**Validate an enumerated or structured query parameter rather than degrading it.**
`codebase-memory-mcp/src/mcp/mcp.c:5036-5062` rejects an unknown `aspect` token with an
`isError` result listing the valid values, and the comment states the reason: the JSON-Schema
enum is advisory because many MCP clients do not validate arguments, "so without this check a
typo degraded to a silent near-empty payload". Sync has exactly that defect at
`src/sync/mcp/tools.py:212`: `whats_changed` filters with
`change.detected_at.isoformat() >= since`, a lexicographic string comparison against an
unvalidated caller-supplied value, and `src/sync/api/app.py:140-141` passes the raw
`?since=` query string straight in. VERIFIED. `?since=yesterday` compares `"2026-08-04T…"`
against `"yesterday"`, `'2' < 'y'`, and every row is filtered out — the API returns an empty,
`200`-status page that reads as "this vendor changed nothing". Parse `since` as an ISO-8601
instant at the transport boundary and return 400 for anything else. This is a system boundary,
so it is squarely inside Sync's own "validate at boundaries" rule rather than an exception to
"no error handling for conditions that cannot occur".

**Distinguish the malformed pagination cursor from the malformed filter.** Related but
separate: `src/sync/api/app.py:40-52` deliberately falls back to a default when `limit` or
`offset` will not parse, and the docstring argues that a 400 for a stray typed URL is more
surprise than help. That reasoning holds *for pagination*, because a wrong page size still
returns correct rows. It does not transfer to a filter, where a swallowed parse changes which
rows exist. The distinction is worth stating in the same docstring so the next parameter added
lands on the right side of it.

## 4. What Sync already does better, and where a reference would be a step backwards

**Sync converts exceptions into queryable state at the node boundary; most references convert
them into a log line.** `src/sync/remediate/nodes.py:105-110` — `locate` catches the store
lookup, returns `{"fatal": True, "diagnostics": _describe(exc)}`, and `route_after_locate`
(`nodes.py:126-133`) sends it to `abandon`, where `make_abandon` (`nodes.py:641-653`) writes
the reason to the corpus with `terminal_status="abandoned"`. VERIFIED. The exception becomes a
row, and the row is the negative class a future router trains against. `PageIndex` at the same
juncture returns `""`; `Understand-Anything`'s `getChangedFiles` returns `[]`. Only
`open-code-review` is comparable, and its record is a JSON manifest rather than a queryable
table.

**Sync's `reported` versus `abandoned` split is finer than anything in the references.**
`src/sync/remediate/state.py:9-15` and the reasoning at `nodes.py:594-614` separate "Sync
tried and could not finish" from "the decision table correctly found there was nothing to
try", and refuse to write `abandon_reason` for the second because it would corrupt the exact
signal the field exists to carry. `open-code-review` has `StateSkipped` for a zero-item run
but does not distinguish a deliberate no-op from a failure at the *item* level. No other
reference models it at all.

**Sync already routes on booleans a producer set, not on the shape of an output.**
`state.py:36-42` (`verify_ok`) and `state.py:44-56` (`replay_outcome` /`replay_ok`) both state
the rule and its reason. The `replay` comment is the sharper one: `declined` and
`not-attempted` must never read as "the patched path was executed", "because that sentence
goes in front of a reviewer". That is the same discipline `claude-cookbooks` teaches for
`stop_reason`, arrived at independently, and it is stricter than what `PageIndex`,
`Understand-Anything`, or `code-review-graph`'s CLI actually practise.

**Sync separates the operator's line from the agent's feedback.** `state.py:22-28` keeps
`diagnostics` (one line, what the CLI prints) apart from `feedback` (paragraphs and a diff,
what the next patch attempt is told), on the argument that serving both from one key means one
of them gets the other's format. `open-code-review` reaches the same conclusion for a different
reason — `agent.go:983-989` keeps the raw error out of the manifest because it may embed a
provider payload, credentials, or absolute paths, and preserves it in the session checkpoint
instead. Two independent arguments for the same split; Sync should read the second as a reason
to keep the first.

**Where a reference would be a step backwards.** Adopting `codegraph`'s density of
`catch { /* advisory */ }` would be a mistake here. It is defensible in a CLI whose telemetry
and prompt-injection paths genuinely must never break a user's command, and each site is
annotated. Sync has no such subsystem on the critical path: every stage of INDEX through PR
either produces evidence a pull request rests on or should abandon and say why. A degradation
contract in Sync is a claim that some part of the answer does not matter, and the places where
that is true are few enough to name individually.

Adopting `PageIndex`'s retry shape would be worse. Ten flat one-second retries with no
backoff is a thundering herd against a rate-limited vendor, and the terminal `return ""`
would put a fabricated empty answer into the graph. `code-review-graph`'s three attempts with
`2 ** attempt` backoff over an enumerated retryable set is the shape to copy; keep
`PageIndex`'s `_is_unrecoverable` idea (`utils.py:46-53`) and its habit of documenting the
deliberate *exclusion* from the set, and discard everything after the loop ends.

One caveat on Sync's current position, which is a real gap rather than a strength.
`src/sync/api/app.py` installs no exception handler at all, so anything the surface raises
becomes Starlette's default 500 with no body. INFERENCE: for internal code that is consistent
with "trust internal code", but the graph store is a database boundary, and a connection
failure and a genuine bug currently look identical to the console. `codebase-memory-mcp`'s
`cbm_mcp_text_result(text, is_error)` at `src/mcp/mcp.c:276-312` shows the minimum viable
version — every tool result carries an explicit `isError` flag rather than relying on the
transport's status.

## 5. Open questions only the owner can settle

1. **Is a dead run a terminal outcome, or an operational condition?** Adding `stalled` to
   `Outcome` widens a `Literal` the checkpoint serialiser and the corpus both read. Inferring
   it in `queries.py` from checkpoint age keeps the state machine untouched but puts a
   heuristic in the read path. The two choices have different blast radii and I cannot pick
   between them without knowing whether the corpus should count a killed run at all.

2. **Should `tsc` crashing be a different `abandon_reason` from `tsc` rejecting the patch?**
   The value of the split is that routing stops learning "this change kind is unsafe" from a
   broken toolchain. The cost is a wider reason vocabulary and a classification step that can
   itself be wrong. `subprocess.h`'s six-way enum is the ambitious version; a two-way
   `toolchain-fault` / `patch-rejected` split may be all that is needed.

3. **Does the console distinguish an empty answer from an unreachable API today?** I was asked
   not to read `web/`, so I cannot say. If the React side renders a 500 and an empty
   `vendors: []` the same way, then every type-level improvement proposed above stops at the
   transport and the operator still cannot tell.

4. **How should a vendor adapter report a partially-parsed feed?** Nothing I read in
   `sync.signals` settles whether an adapter that understood eight of ten changes should
   return eight, return nothing, or return eight plus a count of what it dropped.
   `codegraph`'s `filesDiscovered` conservation invariant (`src/extraction/index.ts:93-99`) is
   the third option and is the only one that lets a later query notice the loss — but it needs
   a place in the schema to live, and that is a grain decision.

5. **Is the oasdiff non-convergence exemption in `CLAUDE.md` a failure mode or a data source?**
   The rule says treat that source as at-least-once and never read a row count from it as a
   measurement. That is currently prose. Nothing I read makes it a property of the type, so a
   query that counts `vendor_change` rows sourced from oasdiff is still writable and still
   wrong. Whether that deserves enforcement is a judgement about how likely the mistake is.

## Coverage

Examined for this dimension, with the files I actually read named above:
`open-code-review` (`internal/session/manifest.go`, `internal/agent/agent.go`,
`internal/llm/client.go`, `internal/llmloop/pool.go`), `PageIndex` (`pageindex/utils.py`,
`page_index.py`, `page_index_md.py`, `tree_optimize.py`, `retrieve.py`, `client.py`,
`tests/test_issue_163.py`), `code-review-graph` (`embeddings.py`, `communities.py`,
`daemon.py`, `cli.py`), `codegraph` (`src/extraction/index.ts`, `src/db/index.ts`,
`src/bin/codegraph.ts`, `src/bin/fatal-handler.ts`, `src/mcp/index.ts`),
`Understand-Anything` (`packages/core/src/staleness.ts`,
`packages/core/src/analyzer/llm-analyzer.ts`), `codebase-memory-mcp`
(`src/foundation/subprocess.h`, `src/foundation/diagnostics.h`, `src/mcp/mcp.c`),
`claude-cookbooks` (`fable_5_fallback_billing/guide.ipynb`,
`claude_agent_sdk/hosting/server.py`), `superpowers` (`hooks/session-start`, `scripts/*.sh`),
`skills` (doctrine only — no runtime code on this dimension).

Not reached, and I am not claiming coverage of them: `codebase-memory-mcp`'s daemon retry
state machine (`src/daemon/application.c` has roughly thirty retry-related sites I surveyed by
grep but did not read), `codegraph`'s telemetry and upgrade paths, `code-review-graph`'s
`eval/` tree, and every repository's test suites except `PageIndex/tests/test_issue_163.py`,
which I read because it asserts the behaviour I am reporting as a defect. I did not execute
any code in any repository.
