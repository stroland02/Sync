# `alibaba/open-code-review` — audit against Sync's pipeline

Second pass, 2026-08-04, against a shallow clone of `main` at commit `6dc3eb0` ("feat(viewer): add
repository search filter", authored 2026-08-04). The first pass described the repository largely
from its README and its file layout; this pass read the implementation. Everything marked VERIFIED
was read from that clone this session, and repository paths with line numbers are given so a cold
reader can open the same file at
`https://github.com/alibaba/open-code-review/blob/main/<path>`.

Two findings from the first pass are **corrected** here rather than confirmed. They are called out
in place, and again in §5, because a note that quietly revises itself is worse than one that never
existed.

Files read end to end this session: `internal/agent/agent.go` (1,574 lines),
`internal/session/manifest.go` (964), `internal/session/persist.go` (386),
`internal/session/resume.go` (278), `internal/agent/preview.go` (123),
`internal/diff/resolver.go` (237), `internal/viewer/hostguard.go` (135),
`internal/config/template/template.go` (225), `internal/delegate/rulegroup.go` (59),
`internal/config/allowlist/allowed_ext.go` (97), and all ten prompt files under
`internal/config/template/prompts/`. Read in part: `internal/llmloop/loop.go` (the main loop, lines
1–330 of 562), `internal/llm/client.go` (construction and the OpenAI/Anthropic completion paths),
`cmd/opencodereview/review_cmd.go` (the `executeReview` tail), `internal/viewer/server.go` (the
route table and the guard wrapping), `internal/config/rules/system_rules.go` (resolution and the
canonical-config hash), `internal/scan/agent.go` (dispatch and batching only). **Not read at all:**
`cmd/opencodereview/provider_tui.go` (2,953 lines — the interactive provider picker),
`internal/mcp/`, `internal/telemetry/`, `internal/suggestdiff/`, `internal/gitcmd/`,
`extensions/vscode/`, `pages/`, and every `_test.go` file except where a grep needed one. Claims
about those areas are absent rather than hedged.

## 1. What this reference actually is

Open Code Review (`ocr`) is a single-binary Go CLI — 23,347 lines of non-test Go across `cmd/` and
`internal/` — that reads a git diff, dispatches one LLM conversation per changed file, and prints
line-anchored review comments (VERIFIED: `go.mod`, and a `wc -l` over every non-test `.go` file). It
is Apache-2.0. Its stated origin is Alibaba's internal review assistant, open-sourced after two
years and "tens of thousands of developers" (REPORTED: `README.md` line 38 — an assertion with no
artifact behind it in the repository).

Its declared architecture is a split: "deterministic engineering" owns everything that must not go
wrong — which files are reviewed, which rules apply, where a comment lands — and the agent owns
dynamic decisions and dynamic context retrieval (`README.md` lines 75–93). The split is real in the
code. The model is never asked which files to review, never asked where a comment goes unless
deterministic matching has already failed, and never asked whether the run succeeded. That is the
transferable idea, and it is worth more than any single mechanism below.

It ships two pipelines, not one. `ocr review` is the diff path described throughout this note.
`ocr scan` (`internal/scan/`, 1,068 lines) reviews whole files for auditing a codebase with no
meaningful diff; it batches, it deduplicates comments across a batch with an extra model call, and
it has **no run manifest at all** (VERIFIED: `internal/scan/agent.go` lines 176–179,
`func (a *Agent) RunManifest() *session.RunManifest { return nil }`, with the comment "scan is
intentionally outside the v1 run manifest scope"). The accounting discipline this note recommends
adopting is one pipeline deep in its own repository. That is a fact about how new it is, not a
reason to discount it — but it does mean nobody has yet paid the cost of retrofitting it onto a
second pipeline, and Sync would be doing that on day one.

There is also a third mode worth naming: `internal/delegate/` produces a review *specification*
deterministically and calls no model at all (VERIFIED: the package doc at `rulegroup.go` lines 1–2,
"deterministic 'spec' generation for delegation mode, where OCR produces review specifications
without calling any LLM"). The scope decision, the rule resolution, and the grouping all happen
without inference; an external agent executes the spec.

## 2. What Sync should adopt

### 2.1 The run manifest: a sealed denominator and a coverage-derived terminal state

*Source:* `internal/session/manifest.go` — `RegisterSelected` (lines 492–521), `SealSelected`
(528–539), `Finalize` (739–818), `computeTerminal` (938–955); driven from
`internal/agent/agent.go` `registerCoverage` (1038–1052) and `finalizeManifest` (1060–1077).

This remains the single most valuable thing in the repository, and reading the implementation
raised rather than lowered that assessment. The mechanism, precisely:

Before any dispatch and before any resume reuse, every non-deleted diff is registered as a
`selected` item and the set is **sealed**. After the seal, `RegisterSelected` returns `errSealed`
(manifest.go:504–506). The denominator therefore cannot be widened once work has begun. Each item
then moves to exactly one of four terminal states through a single `transition` function
(556–610), which rejects an unknown item id, a conflicting transition, and — this is the sharp bit
— a re-mark of an already-failed item with a *different* classification, on the reasoning that
"reason is free text and does not participate, but the machine-readable classification must match
so a mis-keyed double-mark surfaces instead of silently keeping the first class" (591–595).

At `Finalize`, any item still sitting in `selected` is swept to `failed`, coloured by the run
failure class if one is set, else by the pending cause, else `unknown` (762–790). `validateLocked`
(838–871) then asserts that `selected` is exactly the disjoint union of the four terminal sets, that
every failed item carries a valid class, and that every waived item carries a non-empty reason. A
validation failure **rolls the sweep back item by item** and leaves the builder unfrozen (796–800),
so a caller can repair the problem and retry rather than ship an invalid manifest. `terminal_state`
is computed from coverage plus `run_failure` and nothing else — never from comment count, never from
warning count (938–955).

Sync's remediation sweep has none of this. `src/sync/cli.py` lines 1043–1087 read
`selected = _select(findings, args.limit)` followed by a bare `for finding in selected:` with a
per-finding LangGraph thread, and there is **no `try`/`except` around that loop** (VERIFIED: read
directly; the nearest `try` blocks are at lines 913 and 1226, both unrelated). An exception on
finding 2 of 10 ends the process. Findings 3 through 10 get no `migration_outcome` row, which is
indistinguishable from never having been selected. The denominator lives in a Python local and dies
with the interpreter.

*Where it lands:* a run-level record written by `sync/cli.py::run`, at grain "one row per
remediation sweep", with the selected finding ids frozen before the loop begins and a Finalize-style
sweep giving every unreached finding a terminal outcome. `migration_outcome` stays exactly as it is
— its grain comment (`src/sync/graph/schema.sql` lines 167–174) is correct that one row is one
attempt — and the manifest sits above it at the sweep grain.

### 2.2 A closed failure-class enum beside the free-text reason, recorded at the trigger point

*Source:* `manifest.go` `FailureClass` (46–72) and `RunFailureClass` (74–107); `agent.go`
`classifyItemError` (991–1002) and `classifyMainLoopStop` (1009–1016).

Sync stores `abandon_reason TEXT` (VERIFIED: `src/sync/graph/schema.sql` line 222) and nothing
machine-readable beside it. `make_abandon` sets it to `state.get("diagnostics") or "unknown"`
(VERIFIED: `src/sync/remediate/nodes.py` line 643) — that is, raw `tsc` or CI text. So "which change
kinds are not mechanically safe", the stated purpose of keeping abandonment data, is a
regex-over-prose exercise.

OCR's split gives the query a column and keeps the prose for humans. Three details are worth copying
exactly. First, the class is decided at the site that knows why, never inferred at the end from
context state — `classifyItemError` uses `errors.Is` against sentinels, not string matching, and the
comment says so (982–983: a sentinel exists "so callers classify it with errors.Is instead of
matching error text, which silently breaks the moment the wording changes"). Second, an
unclassifiable stop gets the honest `unknown` rather than being rounded up: only the configured
max-tool-rounds limit maps to `budget`, while the "model returned no usable tool result three rounds
running" and "context compression blew its threshold" exits both map to `unknown`, and the comment
is explicit that "only an explicit budget trigger may use the budget classification" (1004–1016).
Third, the run-level enum is *different from* the item-level enum — a run never fails with
`provider` or `panic` because those are always attributable to one item, and it gains `internal` for
invariant violations — with an explicit mapping function between them (`itemFailureForRunClass`,
116–131).

*Where it lands:* an `abandon_class` column on `migration_outcome`, a corresponding field on
`RunState` in `src/sync/remediate/state.py`, set by `make_abandon` in `src/sync/remediate/nodes.py`.
The `.claude/rules/remediate-stage.md` line "an abandoned run with no reason is a dropped record
with extra steps" already argues the case; this makes the record queryable.

### 2.3 The pending-failure-cause distinction: a controlled truncation is not a failure

*Source:* `manifest.go` `SetPendingFailureCause` (457–478) and the sweep precedence in `Finalize`
(752–790); the only production caller is `agent.go` lines 566–570.

This is the subtlest idea in the repository and the first pass under-sold it. When the aggregate
token budget stops dispatch, OCR does **not** call `SetRunFailure`. It records a *pending failure
cause* instead, which Finalize applies to items that never got dispatched — so those items are
honestly `failed(budget)` and count against coverage — while the terminal state stays
coverage-derived and reports `partial` rather than `failed`. The comment at agent.go:549–565 gives
two reasons, both real: a run that stopped exactly where it was told to stop did not fail, and
`SetRunFailure` consumes a single first-wins slot that a genuine later cause (a global deadline,
a cancellation) would then be unable to claim.

Sync has the same shape and currently collapses it. `--limit` truncates the finding set before the
sweep begins, and there is no record anywhere that the untouched findings were candidates. Adopting
§2.1 without §2.3 would give Sync a manifest that reports a deliberately limited run as a failure,
which is worse than no manifest — an operator learns to ignore it.

*Where it lands:* the same sweep-grain record as §2.1, with a distinction between "not reached
because the run broke" and "not reached because `--limit` said so".

### 2.4 `sanitizeReason` as a mandatory redaction floor on stored diagnostics

*Source:* `manifest.go` lines 612–684, applied inside `transition` (568–574), `SetRunFailure` (431),
and `SetPendingFailureCause` (476) — every path that stores a reason, with no way around it.

Sync writes `diagnostics` and `abandon_reason` from subprocess output: `tsc` stderr, CI logs,
provider errors. OCR applies one function to every reason before storage. In order: coerce to valid
UTF-8 with the replacement rune (not deletion), strip control and escape characters and collapse to
one line, redact URL userinfo, `Bearer`/`Basic` tokens, and credential-like `key=value` pairs, then
cap at 500 **runes** so multibyte text is never cut mid-character.

The ordering carries a comment worth reading in full (663–672): an embedded control byte inside a
token truncates the regex match, so stripping controls *after* redacting would drop the byte and
splice the surviving half of the secret back in. The invalid-UTF-8 byte becomes `�` rather than
disappearing, deliberately, "so it can still truncate a token match" — the sanitizer is honest that
it is a floor and that callers still own context-aware redaction.

*Where it lands:* `src/sync/remediate/nodes.py` wherever `diagnostics` or `abandon_reason` is set,
and in the M4 API before either is serialized. Note the interaction with Sync's UTF-8 rule:
`strings.ToValidUTF8` is Go's `errors="replace"`, and this is exactly the
diagnostic-rather-than-data case where `CLAUDE.md` already says to pass it.

### 2.5 A typed exclusion reason and a zero-cost `--preview`

*Source:* `internal/agent/preview.go` — `whyExcluded` (31–57), `Preview` (61–99).

Every rejected file carries a reason from a fixed enum, evaluated in a fixed order: binary → user
exclude glob → user include glob (an early *accept* that bypasses everything after it) → extension
allowlist → default excluded path. `Preview` runs the diff load and the whole filter and returns
structured per-file entries with `WillReview` and `ExcludeReason`, without a single model call. A
user can see the entire selection decision for free before spending anything.

Sync's analogue is DETECT: which findings were produced, and which call sites were considered and
rejected and why. Today `_coverage_lines(unread)` prints what the adapter could not read, which is
the same idea at a coarser grain.

*Where it lands:* a typed rejection reason on the DETECT path, and in M4 it is the content of the
Codebase → API Services level. The console's claim is that it shows the graph as it happened, and
"considered, not selected, because X" is part of that graph.

### 2.6 The host-header allowlist on the local viewer

*Source:* `internal/viewer/hostguard.go` (135 lines), wired at `internal/viewer/server.go` lines
49–58; threat T4 in `ASSURANCE_CASE.md` line 64.

M4 serves a read-only Starlette API on localhost carrying the customer's call sites, findings, patch
diffs and CI output. **`src/sync/api/app.py` has no middleware of any kind** (VERIFIED: read the
whole 158-line file; `create_app` returns `Starlette(routes=routes)` at line 158 with no
`middleware=` argument). Without a Host check, any web page the operator happens to visit can point
its own domain at 127.0.0.1 and read all of it — the browser sends the attacker's Host header, which
is exactly why the check works.

OCR's implementation is default-deny: the allowlist always contains the loopback names, adds the
bind host only when it is concrete, and **refuses to auto-allow a wildcard bind** (`0.0.0.0`, `::`,
empty) so an operator exposing the viewer publicly must say so out loud via
`OCR_VIEWER_ALLOWED_HOSTS` (58–79). `hostOnly` (17–35) handles bracketed IPv6 and rejects an
ambiguous bare IPv6 rather than guessing. The server.go comment states the stake plainly: the
session JSONL "contains LLM request bodies = source code being reviewed and the LLM's analysis of
it."

*Where it lands:* Starlette middleware in `src/sync/api/`. Small, self-contained, and the kind of
thing that never gets added later.

### 2.7 Provenance as a grouping key, not a derived label

*Source:* `internal/delegate/rulegroup.go` `GroupRules` (24–58); `internal/config/rules/system_rules.go`
`CanonicalConfig` (145–151, 404–…).

Two files whose resolved rule text is byte-identical stay in separate groups when their source layer
or matched pattern differs. The key is literally `source + "\x00" + pattern + "\x00" + text` (line
44), and the doc comment says why: "a group's Source/Pattern metadata is accurate for every file it
contains." Collapsing on the value would lose the ability to attribute.

That is the same argument as Sync's rung column — provenance is part of the key, not an annotation.

*Where it lands:* nowhere new. It is a citation to reach for the next time someone proposes deriving
the rung from a join instead of carrying it as a column. `.claude/rules/graph-grain.md` is where that
argument lives.

### 2.8 Publish the result before deciding the exit status

*Source:* `cmd/opencodereview/review_cmd.go` `executeReview` lines 223–249, and `reviewResultError`
(252–278).

The manifest is emitted first — "A successfully constructed manifest is publishable even when
execution or session delivery failed" — and only then does an independent process error decide the
exit code. The exit contract is stated in the code: non-zero only for a run-level failure or when
every selected item failed; any usable coverage exits 0. On failure it also prints the session id
with the exact `--resume` command (244–246).

Sync's sweep should write its manifest before it raises, and print the resume handle.

## 3. What to deliberately skip, and what it would cost

### 3.1 The literal instruction — "base our data pipeline on this repo" — still cannot be followed

Stated plainly because it was the framing of the commission, and reading the code confirmed rather
than softened it. **OCR has no pipeline in the sense Sync means.** There is no orchestrator, no
state graph, no stage boundary, no reducer, no database, and no cross-run idempotency. `Agent.Run`
(agent.go:229–337) is a function that calls five other functions in sequence and then fans out
goroutines over files. State moves as ordinary Go struct fields and function arguments. There are
exactly three shared accumulators, all in-process: the `ManifestBuilder` (a mutex-guarded map with a
seal boundary and a freeze boundary), the `llmloop.Runner`'s token counters (atomics, loop.go:63–72)
and warnings slice (mutex, 89–97), and the `tool.CommentCollector`. A grep for
`database/sql|sqlite|postgres|mysql` across every `.go` file returns nothing (VERIFIED this session);
`go.mod` has no driver.

Basing Sync's pipeline on it would mean deleting LangGraph and Postgres and regressing from
node-level checkpointing to file-level JSONL. What Alibaba actually perfected is not the pipeline —
it is the **accounting over the pipeline** (§2.1–2.4) and the deterministic/agent split. Take those.
The substrate underneath them is weaker than Sync's, and copying it is a downgrade, not standing on
a giant's shoulders. This is not a criticism of OCR: a CLI that must run from any developer's laptop
with no services cannot have a database, and every design decision below the manifest follows from
that constraint, which Sync does not share.

### 3.2 JSONL in the home directory as the system of record

*Cost of adopting:* Sync loses SQL over `migration_outcome`, which is the corpus the strategic
argument rests on. It also loses convergence: `persist.go` line 112 opens each session file
`O_CREATE|O_WRONLY|O_TRUNC` under a freshly minted UUID, so re-running the same input produces a
second complete file rather than the same rows — precisely what
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` forbids and what `efcc19d` already
cost once.

One nuance the first pass missed and that softens this slightly: the *read* side does converge.
`resume.go` `applyResumeLine` (110–140) folds the log into a map where `review_item_done` and
`review_item_reused` set a fingerprint and `review_item_failed` **deletes** it (134–138). Replaying
the same file twice yields the same index. So OCR has a deterministic fold over an append-only log —
which is a real property, just not the one Sync's rule asks for. Sync's rule is about the *write*
converging; OCR only guarantees the read does.

### 3.3 The concurrency shape

*Cost of adopting:* OCR's unit of concurrency is a file and its marginal cost is one model
conversation, so `MaxConcurrency` defaulting to 8 (agent.go:517–520) is cheap and correct there.
Sync's unit is a finding and its marginal cost is an agent run plus a push plus a full CI wait —
`src/sync/cli.py` lines 1040–1042 say so in a comment above the loop, and the latency spec says the
critical path is dominated by the customer's CI run. Eight-way fan-out would mean eight branches
pushed and eight CI runs started on a customer's repository at once.

Take the *isolation* pattern and leave the width alone. The isolation is worth studying on its own:
each goroutine registers a `recover()` **before** the timeout-cancel defer, so on unwind the cancel
runs first and the file context is already dead — which is why the panic handler deliberately uses
the parent `ctx` for telemetry (agent.go:585–602). The recovered panic value is written to the local
checkpoint and the warning, while the manifest gets the fixed string "subtask panicked during
review" (595). One file's panic never ends the sweep and never leaks arbitrary text into the
published artifact.

### 3.4 `REVIEW_FILTER_TASK` — but steal its framing

*Cost of adopting:* one extra model call per unit whose only product is a JSON array of ids to drop,
parsed with `fmt.Sscanf(id, "c-%d")` and silently ignored on any parse error (VERIFIED: `agent.go`
`parseFilterResponse`, 1312–1331 — a `json.Unmarshal` failure logs a 200-character preview and
returns nil, and any id that does not scan is skipped without comment). For Sync the equivalent
question, "is this patch right", is already answered deterministically and much better by `tsc` and
the customer's CI. An agent that neither shortens the critical path nor improves a result is exactly
what the latency spec exists to reject. Do not add the stage.

**But read the prompt before dismissing the idea.** `prompts/review_filter_task_system.md` is seven
lines and it is not "grade your own work":

> These review comments come from an Agent that can invoke tools to obtain the full code context.
> You can currently only see the code diff. Therefore, your task is NOT to verify whether all review
> comments are correct, but to **filter out only those review comments that can be confirmed as
> incorrect based solely on the current diff**. For review comments whose correctness cannot be
> determined from the diff alone, even if you find them suspicious, you should let them pass —
> because the Agent may have access to context that you cannot see.

That is a filter that knows it has *less* information than the producer and is therefore permitted
only to remove what it can prove wrong. The asymmetry is the design. Sync has a place for the same
framing without the extra call: any check that runs on a strict subset of the evidence the producing
stage had — a summary view, a cached artifact, a downstream reader of `Finding` — should be allowed
to reject only on proof, never on suspicion. Write that into the prompt of anything that reviews a
patch it did not produce.

### 3.5 Treating the planning phase as optional

*Cost of adopting:* OCR skips the plan below a 50-changed-line threshold and continues when it fails
(agent.go:1115–1130 — a plan failure logs "continuing without plan" and sets `planResult = ""`,
after which `stripEmptyPlanBlock` removes the surrounding markdown section so the model never sees a
dangling header). Plan is enrichment there. Sync's LOCATE is a data dependency of PATCH, not an
ordering accident (`.claude/rules/remediate-stage.md`). A LOCATE that returns nothing leaves nothing
to patch, so "continue without it" is not available.

### 3.6 The redaction *policy*, as opposed to the mechanism

*Cost of adopting:* `sanitizeReason`'s own doc comment (656–658) states that it deliberately does
not strip absolute local paths, cookies, or raw request bodies, leaving those to the caller.
`migration_outcome`'s grain comment (`schema.sql` lines 170–173) says the table is safe to aggregate
across customers precisely because it stores no path and no diff. Adopting OCR's floor without
tightening it would let a customer path reach the one table whose cross-customer safety is
load-bearing. Take the function; make the policy stricter.

### 3.7 The retry story — **corrected from the first pass**

The first pass reported that OCR "retries exactly once, only on `io.ErrUnexpectedEOF`, with no
backoff and no retry on rate limits or 5xx," and recommended not reading it as a validated design.
**That is wrong, and it was wrong because the first pass read the completion function and not the
client constructor.**

Both clients are built with five SDK-level retries and a five-minute per-request timeout:
`openaiopt.WithMaxRetries(5)` and `openaiopt.WithRequestTimeout(cfg.Timeout)` at
`internal/llm/client.go` lines 316 and 318, and `option.WithMaxRetries(5)` and
`option.WithRequestTimeout(cfg.Timeout)` at lines 621 and 623, with `cfg.Timeout` defaulting to
`5 * time.Minute` (303–305, 602–604). The `openai-go` and `anthropic-sdk-go` retry layers handle
429 and 5xx with exponential backoff and honour `Retry-After`. So OCR *does* have provider
resilience; it is delegated to the vendor SDKs rather than hand-rolled.

The application-level retry at lines 366–383 is an *additional*, narrow guard for the one case the
SDK does not cover: a body that terminates mid-read (`io.ErrUnexpectedEOF`), which is not an HTTP
status the SDK can see. It retries once, checks `ctx.Err()` both before retrying and after failing so
a cancelled context is never retried and never misattributed, and refuses to replace the original
error with a second identical EOF.

*What to take:* the layering, which is the actual lesson. Status-code resilience belongs to the SDK;
the application layer adds only the failure modes the SDK is structurally unable to see. Sync should
check what the Agent SDK already retries before writing any retry loop of its own.

### 3.8 The code itself

Apache-2.0 permits derivation, but it is Go and Sync is Python, and Sync's engine is open-core under
FSL. Nothing here is worth transliterating module-for-module; the transferable content is §2.1–2.6.

## 4. Which milestone or subsystem should consult this, and what it answers

| Consult from | The question it answers |
|---|---|
| **M4, the operator console** (`src/sync/api/`, `web/`) | *What must a run record contain so a UI can show failed attempts honestly?* Answer: `manifest.go` — a sealed denominator, five disjoint sets, a terminal state derived only from coverage, a closed failure class per item, and a redacted reason, with a Finalize that rolls back rather than shipping an invalid record. Also: *how do I stop any web page the operator visits from reading this API?* Answer: `hostguard.go`, and note that `src/sync/api/app.py` has no middleware at all today. Also: *what should the console refuse to display?* Answer: OCR never puts a raw error string in the artifact a consumer reads — the raw text goes to the local checkpoint only. |
| **The remediation sweep** (`src/sync/cli.py::run`, `src/sync/remediate/`) | *What happens to findings 3 through 10 when finding 2 raises?* Answer today: nothing is recorded, and there is no `try`/`except` around the loop at cli.py:1053. Answer to adopt: register-and-seal before dispatch, per-item isolation with the recover-before-cancel ordering, a pending-cause distinction so `--limit` reports `partial` rather than `failed`, and a Finalize sweep that gives every unreached item a class. |
| **Pipeline discipline** (`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md`, `.claude/rules/graph-grain.md`) | *When someone proposes making `abandon_reason` more expressive, or deriving the rung instead of storing it, what is the counter-argument with a working implementation behind it?* Answer: `FailureClass` beside `Reason`, and `GroupRules`' insistence that provenance is part of the key. Also: *what does a reproducibility hash look like when someone proposes one?* Answer: §5.2. |
| **Anything that reviews work it did not produce** | *How do I stop a checker with less context from deleting good results?* Answer: `prompts/review_filter_task_system.md` — permit removal only on proof, never on suspicion, and say so in the prompt. |
| **SIGNAL and adapter authors** | Nothing. OCR has no vendor-adapter concept, no spec diffing, and no notion of an external API at all. Do not consult it here. |

## 5. What the source says that the documentation does not

This section is the reason the second pass exists.

### 5.1 The coverage guarantee holds against errors and panics — not against process death

`grep -rn "signal.Notify\|os.Interrupt\|SIGINT\|NotifyContext"` over every non-test `.go` file
returns **nothing** (VERIFIED this session). There is no signal handling anywhere in the repository,
and `review_cmd.go` line 208 builds its root context from a bare `context.Background()` with no
cancel. Press Ctrl-C during a review and the process dies: no `session_end`, no manifest, no
`terminal_state`, no `run_failure`.

The manifest code knows this and says so, in a comment easy to skim past: "It only runs when the
process can still execute Finalize; a hard kill falls back to the per-item checkpoints"
(manifest.go:760–761). Read that against the persistence layer and it becomes a coherent design
rather than a gap. `writeReviewItemRecord` — and *only* that function — flushes the buffered writer
after every record (`persist.go` lines 213–215). `WriteLLMRequest`, `WriteLLMResponse`,
`WriteToolCall` and `WriteLLMError` do not. The durability boundary is drawn exactly at the resume
checkpoint: kill the process and you lose the conversation transcript and the manifest, but you keep
every per-file outcome, which is the only thing resume needs.

The consequence is that `RunFailureCancelled` and `FailureCancelled` exist in the enum and are
essentially unreachable in the review path — nothing cancels the root context, so `errors.Is(err,
context.Canceled)` in `classifyItemError` can only fire from a per-file deadline's parent, which is
never cancelled either.

**For Sync this is the most important sentence in the note.** Sync's remediation sweep waits on a
customer's CI run — minutes to tens of minutes per finding — which is exactly the window in which an
operator hits Ctrl-C, a laptop sleeps, or a container is evicted. If Sync copies §2.1 verbatim, it
inherits a manifest that is written only on the paths where nothing much went wrong. Sync has a
strictly better tool available and should use it: LangGraph already checkpoints to Postgres per
node, so the sweep-grain record should be **written incrementally to Postgres at seal time and
updated per finding**, not assembled in memory and flushed at the end. OCR assembles in memory
because it has nowhere else to put it. Sync does.

### 5.2 There is a three-part reproducibility hash nobody mentions

`agent.go` lines 807–905 compute three SHA-256 digests that appear in the manifest and are described
nowhere in the README:

- `source_artifact_sha256` (821–843) — the content identity of the run's input. For every non-deleted
  diff in the sealed selected set it pairs the content-independent `item_id` with the raw diff
  fingerprint, deduplicates by `item_id` with first-wins "matching `RegisterSelected`'s dedup", sorts
  by `item_id`, and folds the result. It deliberately uses the fingerprint rather than the `item_id`
  "so a content change to the same logical file changes the artifact — exactly what a resume needs to
  detect a moved ref's new input."
- `rule_config_sha256` (853–867) — the identity of the resolved rule configuration across all four
  layers (custom > project > global > system) plus the include/exclude filter, obtained through an
  optional `CanonicalConfig() []string` interface. Rule order is significant because first match
  wins, and so it is **never sorted** (852).
- `runtime_config_sha256` (879–890) — protocol, model, credential-free endpoint host, language,
  timeout, concurrency, and the token budget. The budget is folded in with a reason: "two otherwise-
  identical runs with different budgets are not interchangeable when auditing why one stopped short."

All three go through `hashFields` (896–905), which writes an 8-byte big-endian length prefix before
each field "so no two distinct field sequences can collide at a boundary" — the standard defence
against `["ab","c"]` and `["a","bc"]` hashing identically, applied without being asked.

Together these answer "was this run configured the same way as that one" without storing any
configuration, and without storing any secret — `RuntimeConfig`'s own doc comment (144–155) says it
"deliberately excludes every secret: no token, and only the endpoint host (scheme, embedded
credentials, path and query stripped) — never the full URL."

Sync's equivalent question is sharper and currently unanswerable: two `migration_outcome` rows for
the same finding at different `attempt_index` values may have been produced under different
catalogue versions, different model configurations, or different tier routing tables, and nothing on
the row says which. A `config_sha256` on `migration_outcome`, computed with length-prefixed framing
over the catalogue and the resolved model settings, would make "compare only comparable attempts" a
`WHERE` clause. This is the single most directly transferable mechanism in the repository after the
manifest itself.

### 5.3 `item_id` normalizes Windows path separators — and Sync runs on Windows

`ItemID` (manifest.go:196–207) NUL-joins operation, mode and both paths, but only after passing each
path through `normalizePath` (213–223), which replaces `\` with `/` and runs `path.Clean`, so
"cosmetically different spellings of the same path yield the same item_id." An empty path stays
empty; `"."` collapses to empty.

This matters more for Sync than for OCR. Sync's development machine is Windows 11, its clone paths
and call-site paths cross that boundary constantly, and every fixture in the repository is ASCII and
POSIX-shaped, so no test would catch a key that differs only by separator. Any identity Sync derives
from a path — a finding id, a thread id, a manifest item id — needs the same normalization, and
needs it written once in one function rather than at each call site. OCR makes that explicit:
"RegisterSelected and every Mark* MUST go through this one helper so a mismatched key can never
silently no-op a transition" (191–195).

### 5.4 The `waived` set is designed, validated, and has no production caller

`MarkWaived` (manifest.go:710–712) is reachable only from tests. `grep -rn "MarkWaived"` finds it in
`manifest.go`, `manifest_test.go` and `list_test.go` and **nowhere in production code** (VERIFIED
this session). `Finalize` validates that every waived item carries a non-empty reason (862–866); no
code path produces one.

The same is true of most of `RunFailureClass`. There are exactly two `SetRunFailure` call sites in
the whole repository — `RunFailureInput` at agent.go:239 and `RunFailureInternal` at agent.go:509 —
and one `SetPendingFailureCause` at 567. `RunFailureTimeout`, `RunFailureCancelled`,
`RunFailureBudget` and `RunFailureUnknown` are unreachable today.

This is not a defect, and it is worth naming precisely because it looks like one. The enum is a
frozen v1 contract: `ManifestSchemaVersion = "ocr.run-manifest/v1"` (line 20), and the comment on
`pendingFailureCause` says outright that a fact was kept out of the struct because "schema v1 is
frozen" (148–150). Declaring the full vocabulary up front and wiring producers later is the correct
order when consumers must switch on the value. **The lesson for Sync is the sequencing**, not the
completeness: decide the closed vocabulary of `abandon_class` before shipping the column, including
the members nothing produces yet, because widening a vocabulary that consumers already switch on is
a migration and adding a producer is not.

### 5.5 The README describes a bundling feature that does not exist

`README.md` line 85 claims: "**Smart file bundling** — Groups related files into a single review unit
(e.g., `message_en.properties` and `message_zh.properties` are bundled together)."

There is no bundling in the diff-review path. `dispatchSubtasks` (agent.go:484–674) iterates
`toDispatch` and launches exactly one goroutine per `model.Diff`; the loop body takes a single `d
model.Diff` (line 579). A grep for `bundle|bundling` across every non-test `.go` file returns five
hits, all Go doc comments about struct fields ("Deps bundles all per-call dependencies"), none of
them a file-grouping implementation (VERIFIED this session). Batching does exist — in
`internal/scan/` (`groupBatches`, `resolveBatchStrategy`, scan/agent.go:509–560) — which is the other
pipeline, and it batches for prompt-cache locality, not for semantic relatedness.

The README's own example makes it worse: `.properties` is **not** in the 83-entry extension allowlist
(VERIFIED: parsed `internal/config/allowlist/supported_file_types.json`), so `whyExcluded` returns
`ExcludeExtension` and a `.properties` file is never reviewed at all — even though
`internal/config/rules/system_rules.json` has a dedicated `**/*.properties` path rule and
`rule_docs/properties.md` exists to serve it. That rule is reachable only if a user explicitly adds
`**/*.properties` to their include patterns, because a user include short-circuits the extension
check (preview.go:43–45).

A second, smaller version of the same gap: the README (line 86) says "template-engine-based rule
matching is more stable and predictable" than language-driven guidance. There is no template engine.
`text/template` appears nowhere in the repository; the only `html/template` import is the viewer's
server-rendered HTML (`viewer/server.go` line 6). Every prompt placeholder is substituted with
`strings.ReplaceAll` (agent.go:1141–1157, 1465–1471; relocation.go:34–39). The mechanism is fine —
it is the claim about it that is inflated. The two modules do not even agree on delimiter syntax:
the main and plan tasks use `{{diff}}`, and the relocation task uses `{diff}`.

*The general lesson:* this repository's README oversells and its code comments undersell. Reverse
the usual reading order. The doc comments in `manifest.go` and `agent.go` are the specification;
the README is marketing that has drifted.

### 5.6 Prompts are ten markdown files totalling 223 lines, and the indirection is deliberate

`internal/config/template/task_template.json` is a *manifest*, not a prompt store: each conversation
lists `{"role": ..., "prompt_file": ...}` and `resolveConversation` (template.go:72–86) reads the
named file out of an embedded FS. Every prompt is a separate `.md` file under `prompts/`, all
compiled into the binary by `//go:embed task_template.json prompts/*` (line 45).

The whole corpus is 223 lines across ten files: `main_task_system.md` 25, `main_task_user.md` 25,
`plan_task_system.md` 37, `plan_task_user.md` 21, `memory_compression_task_system.md` 31,
`memory_compression_task_user.md` 1, `review_filter_task_system.md` 7, `review_filter_task_user.md`
55, `re_location_task_system.md` 1, `re_location_task_user.md` 20. The tuning parameters live beside
them as plain integers: `MAX_TOOL_REQUEST_TIMES: 30`, `PLAN_MODE_LINE_THRESHOLD: 50`,
`MAX_TOKENS: 58888`.

The indirection buys three things worth copying. A prompt diff is a diff of a markdown file, not a
diff of an escaped JSON string. The role/order structure is reviewable separately from the wording.
And the parameters that govern the loop sit in one place a human can audit. Notably the *scan*
template (`scan_template.json`, 9,739 bytes) does **not** use the indirection and embeds its message
content inline — the older shape, presumably, and the one that is harder to review.

Sync's prompts should follow `task_template.json`, not `scan_template.json`.

### 5.7 Resume refuses the case where the input is not stable

`ResumeState.ValidateOptions` (resume.go:183–209) rejects a resume outright when the review mode is
`workspace` — "resume requires --from/--to or --commit; workspace resume is not supported" — and
rejects it again when the prior session's range or commit does not match the current one exactly.

This is a stronger position than "resume is best effort", and the reasoning is structural rather
than defensive: a workspace review's input is the mutable working tree, so a fingerprint computed
against it has no stable referent, and a partial reuse would silently mix results from two different
trees. OCR declines rather than guessing.

Sync's remediation resume path (`_thread_to_invoke` and the `graph.get_state(config)` branch at
cli.py:1055–1064) keys on `f"{finding.id}:{args.run_id or repo.head_sha[:12]}"`, which already
encodes the head SHA and therefore already has most of this property. What it lacks is the explicit
refusal: if a caller passes `--run-id` and the head has moved, the thread id is stable while the
tree underneath it is not. Adding OCR's validation — refuse to resume unless the input identity
matches — closes that.

### 5.8 Two smaller things the code shows and no document mentions

**`Registry.Freeze()` is a discipline marker, not a lock.** `internal/tool/definitions.go` lines
75–103: the registry is a plain `map[string]Provider` with a `frozen bool`. `Register` panics if
frozen; `Get` never checks. The entire concurrency guarantee is "the map stops being written before
any goroutine starts", enforced by a panic at the one write path, and `agent.go` line 262 calls
`Freeze()` immediately after `injectDiffMap()` and before dispatch. Go maps are safe for concurrent
reads; that is the whole argument. It is a cheap, legible pattern for "immutable after setup" and
Sync's `load_catalogue()` result has the same shape.

**Comment anchoring is first-match-wins over whitespace-normalized lines, and `normalizeLine` strips
a leading `+` or `-`** (`diff/resolver.go` lines 230–237). That makes the anchor survive
reformatting, but it also means a source line that legitimately begins with `-` — a unary minus, a
YAML list item, a continuation in a string concatenation — normalizes identically to a deleted diff
line, and `matchConsecutive` (148–165) returns the *first* run that matches rather than the best
one. Only when both the new-side and old-side hunk scans fail does `ReLocateComment`
(`diff/relocation.go` 20–70) spend a model call to regenerate the snippet and retry the
deterministic match. That is how the README's "position drift" claim is actually paid for, and the
ordering is the point: the model is the fallback, not the mechanism. Sync's LOCATE has exactly this
shape and should keep exactly this ordering.

## 6. What could not be verified

- **The benchmark.** The README's precision, F1, and "~1/9 of the tokens" claims exist only as PNG
  images (`imgs/benchmark-*.png`). The 50 repositories, 200 pull requests, 1,505 annotated issues and
  the harness that produced the numbers are not in the repository. REPORTED, not verified, and not
  independently checkable from what is published. The README does at least disclose the trade-off
  honestly: "its Recall is lower than general-purpose agents — a deliberate trade-off favoring
  precision over noise" (line 50).
- **The provenance claims.** "Two years internal, tens of thousands of developers, millions of
  defects" is a README assertion (line 38) with no artifact behind it in the repository. REPORTED.
- **Whether the manifest predates open-sourcing.** The clone was `--depth 1`, so the history that
  would show whether `RunManifest` was built for the community release or carried over from
  Alibaba's internal version was not read. Could not verify. It matters mildly: if the manifest is
  post-release, it is community-hardened rather than production-hardened. The circumstantial evidence
  leans post-release — the schema is explicitly `v1`, the scan pipeline has none of it, and several
  enum members have no producer (§5.4) — but that is inference, not a reading of history.
- **Behaviour under sustained provider rate limiting.** The SDK retry layer is configured (§3.7) but
  no test or measurement in the repository exercises a 429 or a sustained 5xx, and the SDK's own
  behaviour was not read this session. Could not verify what a rate-limited run actually produces.
- **`cmd/opencodereview/provider_tui.go`, `internal/mcp/`, `internal/telemetry/`,
  `internal/suggestdiff/`, `internal/gitcmd/`, and the VS Code extension.** Not read. Roughly 4,000
  lines of the 23,347 are unexamined, concentrated in the interactive provider picker. No claim in
  this note depends on them.
