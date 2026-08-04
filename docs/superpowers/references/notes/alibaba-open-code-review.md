# `alibaba/open-code-review` — audit against Sync's pipeline

Audited 2026-08-04 against a shallow clone of `main` at commit `6dc3eb0`
("feat(viewer): add repository search filter (#642)"). Everything marked VERIFIED below was read
from that clone this session; repository paths are given so a cold reader can find the same file at
`https://github.com/alibaba/open-code-review/blob/main/<path>`.

## 1. What this reference actually is

Open Code Review (`ocr`) is a single-binary Go CLI, roughly 23,000 lines of non-test source across
`cmd/` and `internal/`, that reads a git diff, dispatches one LLM conversation per changed file, and
prints line-anchored review comments (VERIFIED: `go.mod`, `wc -l` over the tree). It is licensed
Apache-2.0 and its stated origin is Alibaba's internal review assistant, open-sourced after two
years of production use (REPORTED: `README.md` lines 39-41; the GitHub project page shows 18.7k
stars, 41 open issues, primary language Go). Its declared architecture is a deliberate split —
"deterministic engineering" owns everything that must not go wrong (which files are reviewed, which
rules apply, where a comment lands), and the agent owns only dynamic decisions and dynamic context
retrieval (VERIFIED: `README.md` lines 75-93, and the split is real in the code, not just the
marketing).

## 2. How its pipeline and workflow are actually built

This section answers the specific questions the audit was commissioned to answer. All of it is
VERIFIED unless labelled otherwise.

### The stages

`internal/agent/agent.go` is the whole orchestrator. `Agent.Run` executes, in order:

1. **Input resolution.** `loadDiffs` selects one of three diff providers — commit, range, or
   workspace — parses the git diff, and immediately freezes this run's resolved commit endpoints
   (`resolved_base`, `resolved_head`, `exact_range`) plus a credential-free repository identity,
   while a live context and the git-backed provider are still in hand. Nothing later re-resolves
   them, so even a run that ends up skipped or failed records the input it was actually given
   (`agent.go` `loadDiffs`, `applyInputIdentity`).
2. **Filtering, in two passes.** `filterDiffs` applies the selection rules; `filterLargeDiffs`
   then drops any diff whose raw content alone exceeds 80% of the configured `max_tokens`.
3. **Coverage registration and seal.** `registerCoverage` registers every surviving non-deleted
   diff into a `ManifestBuilder` as a `selected` item, then calls `SealSelected()`. After the seal,
   registering another item returns an error. This happens *before* resume reuse and before any
   dispatch, so the coverage denominator cannot be widened mid-run.
4. **Resume application.** `applyResume` fingerprints each diff and looks it up in the prior
   session's checkpoint index; a hit replays the stored comments and marks the item `reused` with no
   model call.
5. **Per-file dispatch.** One goroutine per file behind a semaphore (default concurrency 8), each
   with an optional per-file context timeout and each with a `recover()` that converts a panic into
   a `failed(panic)` item rather than killing the run.
6. **Per file: plan → main loop → self-filter.** The plan phase is skipped below a configured
   changed-line threshold and its failure is non-fatal (the `{{plan_guidance}}` placeholder is
   emptied and the surrounding markdown section stripped). The main phase is
   `llmloop.Runner.RunPerFile`, a bounded tool-use loop. Afterwards `REVIEW_FILTER_TASK` sends the
   just-collected comments back to the model and asks which are provably wrong from the diff alone.
7. **Comment positioning.** `diff.ResolveComment` (`internal/diff/resolver.go`) matches the model's
   `existing_code` against parsed hunk lines — new side first, then old side — falling back to a
   whitespace-normalised sliding-window scan of full new-file content. Only when deterministic
   matching fails does `ReLocateComment` (`internal/diff/relocation.go`) spend a model call to
   regenerate the snippet and retry the deterministic match. This is how the README's "position
   drift" claim is actually paid for.
8. **Finalize.** `finalizeManifest` freezes the builder and `session.Finalize` writes the terminal
   record.

### How state moves

There is no orchestration graph, no state machine, and no database (VERIFIED: `grep` for
`database/sql|sqlite|postgres` across all `.go` files returns nothing; `go.mod` has no DB driver).
State moves as ordinary Go struct fields and function arguments. There are exactly three shared
accumulators, all in-process: the `ManifestBuilder` (a mutex-guarded map with a seal boundary and a
freeze boundary), the `llmloop.Runner`'s token counters (atomics) and warnings slice (mutex), and
the `tool.CommentCollector`. The tool registry is explicitly `Freeze()`d after the diff map is
injected and before any goroutine starts. Cross-process state is one append-only JSONL file per
session.

### How it decides what to review and what to skip

Entirely deterministically; the model is never asked. `Agent.whyExcluded`
(`internal/agent/preview.go`) evaluates in a fixed order and returns a typed reason: binary file →
user exclude glob → user include glob (an early accept that bypasses the remaining rules) →
extension allowlist → default excluded path. Deleted files are registered nowhere and never
dispatched. Oversized diffs are dropped in a separate pass with their own message. `ocr review
--preview` runs steps 1 and 2 and renders the entire decision — every file, whether it will be
reviewed, and the reason if not — without spending a single token.

### What happens when a model call fails mid-run

The transport layer does almost nothing. `OpenAIClient.CompletionsWithCtx`
(`internal/llm/client.go`, around lines 368-386) retries exactly once, only on
`io.ErrUnexpectedEOF`, with no backoff and no retry on rate limits or 5xx. Resilience is entirely a
question of what the *item* does with the error, and that part is careful:

- A plan-phase failure is logged and swallowed; the file is reviewed without a plan.
- A main-loop failure returns a Go error that fails that one file. `classifyItemError`
  (`agent.go`) maps it to a fixed class via `errors.Is` — `DeadlineExceeded` → `timeout`,
  `Canceled` → `cancelled`, the `errMainTaskEmpty` sentinel → `configuration`, everything else →
  `provider`. **The raw error text never enters the manifest**; only a fixed generic reason does.
  The full text goes to the session checkpoint, which is not the artifact consumers read.
- A non-error early stop is a separate typed value, `llmloop.MainLoopStop`. Only the configured
  max-tool-rounds limit maps to `budget`; the "model returned no usable tool result three rounds
  running" and "context compression blew its threshold" exits map to the honest `unknown`
  catch-all. The code comment is explicit that an unclassifiable stop must not be dressed up as a
  declared budget stop.
- Reaching the aggregate token budget is not a failure at all. `SetPendingFailureCause` records
  that the undispatched items should be attributed to `failed(budget)` at Finalize, while
  deliberately *not* calling `SetRunFailure` — which would force the terminal state to `failed` and
  would also consume the single first-wins run-failure slot, blocking a genuine later cause such as
  cancellation from being recorded.
- At Finalize, any item still sitting in `selected` is swept to `failed`, coloured by the
  run-failure class if one is set, else by the pending cause, else `unknown`. A validation failure
  during Finalize *rolls the sweep back* and leaves the builder unfrozen, so a caller can repair the
  problem and retry rather than shipping an invalid manifest.
- The exit contract: non-zero only for a run-level failure or when every selected item failed. Any
  usable coverage exits 0. Partial results are emitted *before* the exit status is decided
  (`executeReview` in `cmd/opencodereview/review_cmd.go`).

### What it persists

One JSONL file per session at
`$HOME/.opencodereview/sessions/<encoded-repo-path>/<session-id>.jsonl`, mode 0600, opened
`O_CREATE|O_WRONLY|O_TRUNC` (`internal/session/persist.go`). Record types: `session_start`,
`llm_request`, `llm_response`, `llm_error`, `tool_call`, `review_item_done`,
`review_item_reused`, `review_item_failed`, and `session_end` — which embeds the frozen
`run_manifest` as its final field. Records are chained by `parentUuid`. Resume
(`internal/session/resume.go`) replays that file into a fingerprint→item index; a
`review_item_failed` record *deletes* the fingerprint from the index so the item is retried.
There is no idempotency and no convergence: every run mints a new UUID and truncates its own new
file, so re-running the same input produces a second complete file rather than the same rows.

The manifest itself (`internal/session/manifest.go`, 964 lines) is the most carefully built thing
in the repository. It is versioned (`ocr.run-manifest/v1`), immutable once frozen, and the *same
object* is serialized to both the CLI JSON and the persisted session so the two outlets cannot
compute coverage differently. Coverage is five sets — `selected`, `completed`, `reused`, `failed`,
`waived` — where `selected` is validated at Finalize to be exactly the disjoint union of the other
four. `terminal_state` is derived *only* from coverage plus `run_failure`, never from comment count
or warning count. Every failed item carries a class from a closed enum
(`provider|timeout|cancelled|configuration|input|budget|panic|unknown`); an invalid class is
rejected rather than downgraded. Every waived item requires a non-empty reason. `item_id` is
content-independent (operation + input mode + normalised paths) so it stays stable across a resume
chain, while a separate `fingerprint` field includes diff content for checkpoint matching.

## 3. What Sync should adopt

### 3.1 The run manifest: a sealed denominator and a coverage-derived terminal state

*Source:* `internal/session/manifest.go` — `RegisterSelected`, `SealSelected`, `Finalize`'s sweep,
`computeTerminal`.

This is the single most valuable thing in the repository and it patches a real hole. Sync's
remediation sweep is a plain loop: `selected = _select(findings, args.limit)` then `for finding in
selected:` with a per-finding LangGraph thread (VERIFIED: `src/sync/cli.py`, around lines 1043-1085).
There is **no `try`/`except` around that loop** (VERIFIED: an `awk` scan of lines 890-1090 finds only
one unrelated `try`, for adapter selection). An exception on finding 2 of 10 therefore ends the
process, and findings 3 through 10 get no `migration_outcome` row at all — which is indistinguishable
from never having been selected. The denominator exists in memory and dies with it.

*Where it lands:* a run-level record written by `sync/cli.py::run`, at grain "one row per
remediation sweep", with the selected finding ids frozen before the loop begins and a Finalize-style
sweep that gives every unreached finding a terminal outcome. Sync's own rule that "abandoned runs are
data" already implies this; the manifest is the mechanism that makes it true even when the process
falls over. `migration_outcome` stays as it is — it is the attempt grain and correct — and the
manifest sits above it at the sweep grain.

### 3.2 A closed failure-class enum beside the free-text reason, recorded at the trigger point

*Source:* `manifest.go` `FailureClass` / `RunFailureClass`; `agent.go` `classifyItemError`,
`classifyMainLoopStop`.

Sync stores `abandon_reason TEXT` (VERIFIED: `src/sync/graph/schema.sql` line 222) and nothing
machine-readable beside it. That makes "which change kinds are not mechanically safe" — the stated
purpose of keeping abandonment data — a regex-over-prose exercise. OCR's split gives the query a
column and keeps the prose for humans. Two details are worth copying exactly: the class is decided
at the site that knows why, never inferred at the end from context state; and an unclassifiable
stop gets the honest `unknown` rather than being rounded up to the nearest plausible class.

*Where it lands:* an `abandon_class` column on `migration_outcome` and a corresponding field on
`RunState` in `src/sync/remediate/state.py`, set by `make_abandon` in `src/sync/remediate/nodes.py`.

### 3.3 `sanitizeReason` as a mandatory redaction floor on stored diagnostics

*Source:* `manifest.go` lines 612-684.

Sync writes `diagnostics` and `abandon_reason` from subprocess output — `tsc` stderr, CI logs,
provider errors. OCR applies one function to every reason before storage: coerce to valid UTF-8
(replacement rune, not deletion), strip control and escape characters and collapse to one line, then
redact URL userinfo, `Bearer`/`Basic` tokens, and credential-like `key=value` pairs, then cap at 500
runes. The ordering carries a comment worth reading: an embedded control byte inside a token
truncates the regex match, so stripping controls *after* redacting would splice the surviving half of
a secret back in.

*Where it lands:* `src/sync/remediate/nodes.py` wherever `diagnostics` or `abandon_reason` is set,
and in the M4 API before either is serialized. Note the interaction with Sync's UTF-8 rule —
`strings.ToValidUTF8` is Go's `errors="replace"`, and this is exactly the diagnostic-not-data case
where CLAUDE.md already says to pass it.

### 3.4 A typed exclusion reason and a zero-cost `--preview`

*Source:* `internal/agent/preview.go` — `whyExcluded`, `Preview`; `cmd/opencodereview/review_cmd.go`
`runPreview`.

Every rejected file carries a reason from a fixed enum, and there is a command that renders the whole
selection decision without a model call. Sync's analogue is DETECT: which findings were produced,
and which call sites were considered and rejected and why. Today `_coverage_lines(unread)` prints
what the adapter could not read, which is the same idea at a coarser grain.

*Where it lands:* a typed rejection reason on the DETECT path, and in M4 it is the content of the
Codebase → API Services level — the console's claim is that it shows the graph as it happened, and
"considered, not selected, because X" is part of that graph.

### 3.5 The host-header allowlist on the local viewer

*Source:* `internal/viewer/hostguard.go` (130 lines), `internal/viewer/server.go` lines 51-56,
`ASSURANCE_CASE.md` threat T4.

M4 serves a read-only Starlette API on localhost carrying the customer's call sites, findings, patch
diffs and CI output. Without a Host check, any web page the operator happens to visit can point its
own domain at 127.0.0.1 and read all of it — the browser will send the attacker's Host header, which
is the whole reason the check works. OCR's implementation is default-deny (loopback names plus a
concrete bind host), refuses to auto-allow a wildcard bind, and exposes one env variable so an
operator who binds publicly has to say so out loud.

*Where it lands:* Starlette middleware in `src/sync/api/`. This is small, self-contained, and the
kind of thing that never gets added later.

### 3.6 Provenance as a grouping key, not a derived label

*Source:* `internal/delegate/rulegroup.go` `GroupRules`.

Two files whose resolved rule text is byte-identical stay in separate groups when their source layer
or matched pattern differs, and the code says why: the group's provenance metadata has to be accurate
for every file in it. That is the same argument as Sync's rung column — provenance is a key, not an
annotation, and collapsing on the value loses the ability to attribute a false positive.

*Where it lands:* nowhere new. It is a citation to reach for the next time someone proposes deriving
the rung from a join instead of carrying it as a column. `.claude/rules/graph-grain.md` is the place
that argument lives.

### 3.7 Publish the result before deciding the exit status

*Source:* `cmd/opencodereview/review_cmd.go` `executeReview` lines 234-249.

The manifest is emitted first, and only then does the independent process error decide the exit code,
so a JSON consumer keeps the complete coverage diagnosis even on a failing run. Sync's sweep should
write its manifest before it raises.

## 4. What to deliberately skip, and what it would cost

### 4.1 The literal instruction — "base our data pipeline on this repo" — cannot be followed

Stated plainly because it was the framing of the commission: **OCR has no pipeline in the sense Sync
means.** There is no orchestrator, no state graph, no stage boundary, no reducer, no database, and no
idempotency. It is one process fanning out goroutines over files with three in-memory accumulators
(VERIFIED throughout §2). Basing Sync's pipeline on it would mean deleting LangGraph and Postgres and
regressing from node-level checkpointing to file-level JSONL. What Alibaba actually perfected is not
the pipeline — it is the **accounting over the pipeline** (§3.1-3.3) and the deterministic/agent
split. Take those; the substrate underneath them is weaker than Sync's and copying it is a
downgrade, not standing on a giant's shoulders. This is not a criticism of OCR: a CLI that must run
from any developer's laptop with no services cannot have a database, and every design decision below
the manifest follows from that constraint, which Sync does not share.

### 4.2 JSONL in the home directory as the system of record

*Cost of adopting:* Sync loses SQL over `migration_outcome`, which is the corpus the strategic
argument rests on. It also loses idempotency — OCR opens each session file `O_TRUNC` under a fresh
UUID, so a re-run produces a second file rather than converging, which is precisely what
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` forbids and what `efcc19d` already
cost once.

### 4.3 The concurrency shape

*Cost of adopting:* OCR's unit of concurrency is a file, and its marginal cost is one model
conversation, so `MaxConcurrency: 8` is cheap and correct there. Sync's unit is a finding, and its
marginal cost is an agent run plus a push plus a full CI wait — `src/sync/cli.py` says so in a
comment above the loop, and the latency spec says the critical path is dominated by the customer's CI
run. Eight-way fan-out would mean eight branches pushed and eight CI runs started on a customer's
repository at once. Take the *isolation* pattern (per-item panic recovery, per-item timeout, one
item's failure never ending the sweep) and leave the width alone.

### 4.4 `REVIEW_FILTER_TASK` — asking the model to filter its own output

*Cost of adopting:* one extra model call per unit whose only product is a JSON array of ids to drop,
parsed with `fmt.Sscanf(id, "c-%d")` and silently ignored on any parse error (VERIFIED: `agent.go`
`parseFilterResponse`). For OCR this is defensible — precision is the benchmarked metric and nothing
else can check a review comment. For Sync the equivalent question, "is this patch right", is already
answered deterministically and much better by `tsc` and the customer's CI. An agent that neither
shortens the critical path nor improves a result is exactly what the latency spec exists to reject.

### 4.5 Treating the planning phase as optional

*Cost of adopting:* OCR skips the plan below a line threshold and continues when it fails, because a
plan is enrichment there. Sync's LOCATE is a data dependency of PATCH, not an ordering accident
(`.claude/rules/remediate-stage.md`). A LOCATE that returns nothing leaves nothing to patch, so
"continue without it" is not available.

### 4.6 The redaction *policy*, as opposed to the mechanism

*Cost of adopting:* `sanitizeReason` documents that it deliberately does not strip absolute local
paths, cookies, or raw request bodies, leaving those to the caller. `migration_outcome`'s grain
comment says the table is safe to aggregate across customers precisely because it stores no path and
no diff. Adopting OCR's floor without tightening it would let a customer path reach the one table
whose cross-customer safety is load-bearing. Take the function; make the policy stricter.

### 4.7 The retry story

*Cost of adopting:* one retry, only on `io.ErrUnexpectedEOF`, no backoff, nothing for 429 or 5xx. Do
not read this as a validated design for provider resilience; read it as an area OCR has not needed to
solve because a human is watching the CLI.

### 4.8 The code itself

Apache-2.0 permits derivation, but it is Go and Sync is Python, and Sync's engine is open-core under
FSL. Nothing here is worth transliterating module-for-module; the transferable content is the four
patterns in §3.1-3.5.

## 5. Which milestone or subsystem should consult this, and what it answers

| Consult from | The question it answers |
|---|---|
| **M4, the operator console** (`src/sync/api/`, `web/`) | *What must a run record contain so a UI can show failed attempts honestly?* Answer: `manifest.go` — a sealed denominator, five disjoint sets, a terminal state derived only from coverage, a closed failure class per item, and a redacted reason. Also: *how do I stop any web page the operator visits from reading this API?* Answer: `hostguard.go`. |
| **The remediation sweep** (`src/sync/cli.py::run`, `src/sync/remediate/`) | *What happens to findings 3 through 10 when finding 2 raises?* Answer today: nothing is recorded. Answer to adopt: register-and-seal before dispatch, per-item isolation, and a Finalize sweep that gives every unreached item a class. |
| **Pipeline discipline** (`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md`, `.claude/rules/graph-grain.md`) | *When someone proposes making `abandon_reason` more expressive, or deriving the rung instead of storing it, what is the counter-argument with a working implementation behind it?* Answer: `FailureClass` beside `Reason`, and `GroupRules`' insistence that provenance is part of the key. |
| **SIGNAL and adapter authors** | Nothing. OCR has no vendor-adapter concept, no spec diffing, and no notion of an external API at all. Do not consult it here. |

## 6. What could not be verified

- **The benchmark.** The README's precision, F1, and "~1/9 of the tokens" claims exist only as PNG
  images (`imgs/benchmark-*.png`). The 50 repositories, 200 pull requests, 1,505 annotated issues,
  and the harness that produced the numbers are not in the repository. REPORTED, not verified, and
  not independently checkable from what is published.
- **The provenance claims.** "Two years internal, tens of thousands of developers, millions of
  defects" is a README assertion with no artifact behind it in the repo. REPORTED.
- **Whether the manifest predates open-sourcing.** The clone was `--depth 1`, so the history that
  would show whether `RunManifest` was built for the community release or carried over from
  Alibaba's internal version was not read. Could not verify. It matters mildly: if the manifest is
  post-release, it is community-hardened rather than production-hardened.
- **Behaviour under provider rate limiting.** No test and no measurement in the repository covers a
  429 or a sustained 5xx, and given §4.7 there is no code path that would handle one specially.
  Could not verify what a rate-limited run actually produces.
