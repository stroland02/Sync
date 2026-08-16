# Testing strategy across the nine engineering references

Audited 2026-08-04 against clones under
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs/`.
Every claim below is labelled VERIFIED (I opened the file this session), REPORTED (a document in
the repository asserts it and I did not independently confirm the behaviour), or INFERENCE (my
reasoning from what I read).

## 1. What this dimension covers, and why it matters here

Testing strategy is the question of what a green suite is actually evidence *of*. For a project
shaped like Sync the answer is unusually load-bearing, because three of Sync's central claims are
claims a test suite is the only thing standing behind.

The first is the binding. Sync's product claim is that a given call site depends on a given vendor
operation, attributed to a rung. Nothing in the runtime notices when that attribution is wrong; only
a test does, and only if the test's fixture resembles a real vendor record rather than a convenient
one.

The second is idempotence. "Re-running INDEX, SIGNAL or DETECT converges on the same rows" is a
property, not a value, and properties are exactly what a suite of example-based tests is worst at
covering. A single-run test passes on a non-convergent stage every time.

The third is the model. Sync's patch agent is a Claude Agent SDK call sitting inside a pipeline that
must be deterministic at its edges. The model is the one component whose output cannot be asserted
on directly, and the pipeline's correctness therefore rests entirely on what surrounds it: the
prompt construction, the validation of what came back, and the gate that refuses to ship an
unverified patch.

Underneath all three sits the rule in `.claude/rules/test-discipline.md`: a test that cannot fail is
worse than no test, because it manufactures confidence. Sync has been bitten by this twice by its
own account — the import-boundary test that exited 0 without parsing its argument (line 19-21 of
that rule), and the read-only console guarantee asserted by grepping the package for
`\b(INSERT|UPDATE|DELETE)\b`, a pattern that never matches `insert_finding` because underscore is a
word character.

That second one is already fixed on this branch, and the fix is worth recording before the
comparison starts. VERIFIED: `tests/test_api_routes.py` as it stands today contains no source grep.
Its docstring at lines 6-8 says the read-only constraint is "tested by behaviour rather than by
grepping the source for the shape a mutation might take", and lines 320-391 implement that — a
`RecordingSurface` wrapper whose `__getattr__` records every method the routes reach, a
`propose_patch` that raises `AssertionError` if called, and two tests (`test_no_route_reaches_past_
the_read_surface`, `test_a_404_route_reaches_past_nothing_either`) that drive every route including
the unhappy paths and assert the recorded method set is a subset of three allowed reads. VERIFIED
via `git grep` over history: the regex form lived at `tests/test_api_routes.py:292` in commit
`0902571` and at line 413 in `49f3f7e`, and commit `8e6d3b0`'s own message says "read-only is a test,
not a docstring: `test_api_routes.py` greps the package for INSERT/UPDATE/DELETE ... and both
assertions were shown red against planted violations before the code was trusted." That last clause
is the interesting part. The author *did* falsify the test against a planted violation, and the test
was still wrong, because the planted violation was presumably a bare `INSERT` and the real call site
is `insert_finding`. Falsification proves a detector fires on the case you thought of. It does not
prove the pattern's boundary conditions are right.

The whole rest of this note is a search for that failure mode in nine other codebases, plus what
they do about the model.

## 2. The comparison

### 2.1 Coverage, in numbers

VERIFIED by counting files and lines (excluding `.git`, `node_modules`, `dist`, and
codebase-memory-mcp's `vendored/` third-party bulk):

| Repository | Test files | Test LOC | Source LOC | Ratio |
|---|---|---|---|---|
| codebase-memory-mcp | 144 | 230,406 (`tests/*.c`) | 129,584 (`src/*.c`) | 1.78 |
| open-code-review | 126 (105 Go) | 37,535 | 23,347 | 1.61 |
| Understand-Anything | 68 | 18,025 | 20,747 | 0.87 |
| code-review-graph | 79 | 42,396 | 47,617 | 0.89 |
| codegraph | 162 | 53,414 | 79,189 | 0.67 |
| claude-cookbooks | 12 | — | — | notebooks, not a library |
| superpowers | 7 JS + ~15 shell | — | — | one server, plus prompt drills |
| PageIndex | 3 | 227 | 3,965 | **0.06** |
| skills | 0 | 0 | — | none |

Sync sits at roughly 57,000 test lines across 160 files, so it is in the same band as
code-review-graph and Understand-Anything and well above codegraph.

Two entries are findings in themselves. **PageIndex has essentially no test suite**: 227 lines
across three files against 3,965 lines of `pageindex/*.py`, and two of the three files are named
after the issue they regress (`tests/test_issue_163.py`, `tests/test_page_index.py`). What it does
instead is nothing — there is no CI test job, no fixture corpus, and no eval harness in the clone.
**The `skills` repository has no tests at all** — no test files by any extension, and its only CI
workflow is `.github/workflows/release.yml`. What it does instead is `scripts/link-skills.sh` and
`scripts/list-skills.sh`, neither of which asserts anything. For a repository whose entire content
is markdown instructions to a model, that is a defensible position, but it means the reference
offers nothing on this dimension.

### 2.2 Where the tests actually live: three fixture philosophies

**Fixtures as committed source files, checked into a `fixtures/` directory.** code-review-graph is
the clearest case: `tests/fixtures/` holds one small program per language it parses —
`sample.c`, `sample.cpp`, `Sample.cs`, `sample.dart`, `sample.ex`, `sample.jl`, `sample.kt`,
`sample.lua`, `sample.php`, `sample.rb`, `sample.scala`, `KafkaPatterns.java`, `MarkdownMsg.tsx`,
plus `playbooks/` and `roles/` for its Ansible parser (VERIFIED by listing). codegraph does the same
under `__tests__/fixtures/kernel-parity/`. This is the same shape as Sync's `tests/fixtures/`, and
it is the right one for a static-analysis product: the fixture is the input, and it can be read.

**Fixtures constructed in the test body, in a temp directory.** codegraph's
`__tests__/install-sh-prune.test.ts:52-57` builds a fake install tree with `seedVersion()` and
`fs.mkdtempSync`; code-review-graph's `tests/test_agent_transparency.py:20-26` builds a fake repo
with a `.git` directory and a real `GraphStore`. Sync does this too (`tests/test_agent_patch.py`'s
`clone` fixture at line 393).

**No fixtures, because the input is generated.** codebase-memory-mcp writes its corpora
programmatically inside the C test and indexes them. Its `tests/fixtures/` holds exactly one
directory, `cpp_include` (VERIFIED by listing).

Absence worth recording across the whole set: **no repository uses golden files or snapshot
testing**. VERIFIED by grep: zero hits for `toMatchSnapshot` or `toMatchInlineSnapshot` anywhere in
the nine trees, zero `__snapshots__` directories, zero directories named `testdata` or `golden`, and
no `syrupy` dependency. The word "snapshot" appears throughout code-review-graph and codegraph, but
always as a domain noun (a graph snapshot, a config snapshot), never as a test mechanism. Sync's
`tests/golden/tool_schemas.json` has no counterpart in the reference set.

Second absence, and a larger one: **no repository uses property-based testing**. VERIFIED by grep
for `hypothesis`, `fast-check`, `fc.assert`, `testing/quick`, `Fuzz`, and `proptest` across all
Python, TypeScript and Go sources and all dependency manifests — zero hits. Every suite in the set,
including the two largest, is entirely example-based. For codebase-memory-mcp this is startling,
because the property it most needs (parallel indexing produces the same graph as serial indexing) is
exactly a property, and its own reproduction file says so; see 2.5.

### 2.3 How the model is faked, when it is faked at all

Four distinct designs, in increasing order of how much they actually prove.

**Patch the module-level name.** PageIndex's `tests/test_page_index.py:22-25` patches
`pageindex.page_index.toc_transformer`, `count_tokens`, `page_list_to_group_text` and
`add_page_number_to_toc` by string. No recorded response, no fixture — the model's output is written
inline in the test. Sync does the same thing at `tests/test_agent_patch.py:299`
(`monkeypatch.setattr(agent_patch, "query", fake_query)`).

**Split the call into two pure functions and test both ends.** Understand-Anything's
`understand-anything-plugin/packages/core/src/analyzer/llm-analyzer.test.ts` never constructs a
client. It imports `buildFileAnalysisPrompt`, `buildProjectSummaryPrompt`,
`parseFileAnalysisResponse` and `parseProjectSummaryResponse` and tests them as pure string
functions. The parse side is genuinely good — lines 60-83 feed it a response with the JSON wrapped
in a ` ```json ` fence and prose on both sides, lines 85-100 an unlabelled fence, lines 102-110 a
non-JSON response, lines 112-125 a `complexity` value outside the enum, and lines 141-155 a response
missing every optional field. That is a real adversarial corpus for model output. The prompt side is
much weaker: lines 18-22 assert the prompt contains the path and the content that were interpolated
into it, which is close to asserting that string concatenation works.

**Script a transcript against the client interface.** open-code-review is the strongest here.
`internal/llmloop/loop_test.go:15-31` defines a `fakeClient` implementing the real
`llm.LLMClient` interface, holding a `[]*llm.ChatResponse` and a call counter; helpers at lines
33-77 build a `task_done` tool call and a `file_read` tool call with realistic `Usage` blocks. The
agent loop is then driven over a fixed sequence of model turns, and the test asserts on loop
outcomes — did it complete, how many calls did it make, what token totals did it accumulate
(lines 101-123). Critically the fake degrades gracefully: past the end of the scripted responses it
returns an empty message (lines 21-26) rather than raising, so a loop that runs longer than expected
fails on the loop's own termination condition rather than on the fake's bookkeeping. `internal/llm/
client_test.go` complements this with `httptest` servers standing in for the provider HTTP endpoint,
which is where request-shaping is tested (`TestBuildAnthropicParams_CacheControl`, line 105).

**Run the real model and assert on structured output.** superpowers is the only repository in the
set that does this. `tests/explicit-skill-requests/run-test.sh:71-90` runs `claude -p` with
`--output-format stream-json` into a log, then greps the log for `"name":"Skill"` together with
`"skill":"(namespace:)?<name>"`, and exits non-zero if the skill was not invoked. The assertion is
on a tool-call record in a machine-readable stream, not on prose, which makes it binary and
reproducible in a way a text assertion never is. The prompt corpus is
`tests/explicit-skill-requests/prompts/*.txt`, one file per phrasing.

Sync's own approach, VERIFIED at `tests/test_agent_patch.py:431`
(`monkeypatch.setattr(AgentRemediator, "_run_agent", _agent_doing(work))`), is a fifth design and
arguably the best of them: the *model* is replaced, but the *effect* is real — the substitute
performs actual filesystem writes and `git add` inside a real clone, so the tests at lines 437-477
about staged versus unstaged files exercise the genuine `shipped_tree` logic. That combination —
fake the token stream, keep the side effects real — is not present in any reference.

### 2.4 How quality is measured when correctness is not binary

Two repositories run a scored eval rather than an assertion, and both keep it out of the ordinary
test suite.

codegraph's `__tests__/evaluation/` holds `runner.ts`, `scoring.ts`, `test-cases.ts` and `types.ts`.
`scoring.ts:3` sets `PASS_THRESHOLD = 0.5` and scores retrieval by recall against a list of expected
symbols, plus mean reciprocal rank (lines 28-29). The runner writes a timestamped JSON report
carrying the git SHA (`runner.ts:100-114`), which makes the metric comparable across commits.

That harness has a defect worth naming. VERIFIED: `codegraph/package.json:28` declares
`"test:eval": "vitest run __tests__/evaluation/"`, `vitest.config.ts` sets
`include: ['__tests__/**/*.test.ts']`, and `__tests__/evaluation/` contains no file matching
`*.test.ts` — only the four bare `.ts` files listed above. INFERENCE: the documented command
therefore selects zero tests, and since the config sets no `passWithNoTests`, it does not run the
eval at all. The eval is only reachable by invoking `runner.ts` directly with `EVAL_CODEBASE`
pointing at an already-indexed real repository (`runner.ts:9-20`). The quality metric is entirely
outside CI, and the one documented way to run it is broken.

code-review-graph does this more carefully. `code_review_graph/eval/runner.py` registers seven named
benchmarks (`token_efficiency`, `impact_accuracy`, `flow_completeness`, `search_quality`,
`build_performance`, `multi_hop_retrieval`, `agent_baseline`, lines 29-37), and `_validate_config` at
lines 48-61 refuses to run unless the config's pinned `commit` equals the last entry in
`test_commits` — a reproducibility guard on the benchmark itself. It has a dedicated
`.github/workflows/eval.yml`, so the eval is wired to CI rather than to a developer's laptop.

### 2.5 Tests that cannot fail: every instance I found

This is what the dimension was commissioned for, so each item names the file and line and states the
input that would slip through.

**claude-cookbooks, `tests/notebook_tests/test_notebooks.py` — four tests with no assertion at
all.** VERIFIED by AST scan and by reading:

- Line 123, `test_no_empty_code_cells`: if empty code cells are found it calls `pytest.skip()`. The
  test passes when the condition it is named for is absent and skips when it is present. There is no
  path to red.
- Line 175, `test_pip_installs_at_top`: `if idx > 2: pytest.skip(...)`. Same shape. A notebook with
  `%pip install` in cell 40 reports as skipped, not failed.
- Line 195, `test_dependencies_documented`: every branch is `return` or `pytest.skip`.
- Line 247, `test_has_title`: `if not source.startswith("#"): pytest.skip(...)`. The function
  contains no `assert` statement of any kind.

**claude-cookbooks, `tests/notebook_tests/test_notebooks.py:280` — the exact `\bINSERT\b` failure
mode.** VERIFIED. `test_no_deprecated_models` matches `CLAUDE_MODEL_PATTERN = r"claude-[a-z0-9-]+-\d{8}"`
against every code cell and fails on any match not in `CURRENT_MODELS = {"claude-sonnet-4-6",
"claude-haiku-4-5", "claude-opus-4-6"}` (lines 271-278). The pattern requires an eight-digit date
suffix. INFERENCE, from reading both: a genuinely deprecated undated alias — `claude-2`,
`claude-3-opus-latest`, `claude-instant-1.2` — does not match the pattern and passes silently, which
is precisely the class of miss the test exists to catch. And none of the three strings in
`CURRENT_MODELS` can itself match `\d{8}`, so the membership check at line 294 can never be true; the
allowlist is decoration on the failure message rather than a filter. The test fires on dated model
IDs only, and the deprecated models most likely to linger in an old notebook are the undated ones.

**claude-cookbooks, `tests/notebook_tests/utils.py:193-222` — a validator that cannot report.**
VERIFIED. `validate_uses_env_for_api_key` initialises `warnings = []`, computes `has_anthropic_import`
and `uses_env_get` across every cell, reaches `if has_anthropic_import and not uses_env_get:` at line
217, and the body is `pass  # This is acceptable`. It then returns the empty list. It is wired into
`validate_notebook_structure` at lines 289-290. The function is thirty lines of dead computation
presented as a security check.

**superpowers, `tests/explicit-skill-requests/run-test.sh:97-121` — a documented failure mode with a
non-failing detector.** VERIFIED. The block is headed "Check if Claude took action BEFORE invoking
the skill (the failure mode)". When premature tool calls are found it prints
`WARNING: Tools invoked BEFORE Skill tool:` and continues; the script's exit status at lines 132-136
depends only on `TRIGGERED`. The behaviour the comment calls "the failure mode" cannot fail the test.
Line 120's `WARNING: No Skill invocation found at all` is likewise cosmetic, though that case is
already caught by `TRIGGERED=false`.

**superpowers, `tests/claude-code/run-skill-tests.sh:110-114` — a missing test file is a skip.**
VERIFIED. `if [ ! -f "$test_path" ]; then ... skipped=$((skipped + 1)); continue; fi`, and the exit
status at line 184 keys on `$failed` only. Deleting a test file turns the suite green.

**superpowers, `tests/claude-code/test-subagent-driven-development.sh` — assertions loose enough to
be near-unfailable, and honestly labelled as such.** VERIFIED. The file's own header (lines 5-9)
says: "this test asks the agent to *describe* SDD (string-matches its verbal explanation against
expected keywords ...). Drill scenarios test behavior ..., not description-recall." The assertion at
line 171 accepts any of `worktree|feature.*branch|not.*main|never.*main|avoid.*main|don't.*main|
consent|permission`; a model reply containing only the word "permission" passes a test named "Warns
against main branch". Line 118 accepts `loop|again|repeat|until.*approved|until.*compliant`. I count
the self-labelling as a mitigation rather than a defence — the test still runs and still reports
green — but it is more honest than anything in the cookbook.

**codebase-memory-mcp, `scripts/check-no-test-skips.sh:27` — the linter's own glob misses the
violation.** This is the best parallel to Sync's bug in the whole set, because the repository has
gone further than anyone else to prevent the failure mode and still has an instance of it. VERIFIED:
the script forbids plain `SKIP()` in tests, and its comment at lines 11-12 states the doctrine
outright — "a test that cannot establish its preconditions has FAILED, not been 'skipped'. Convert
such SKIP() to FAIL('reason')." The scan is
`grep -rnE '(^|[^A-Za-z0-9_])SKIP\(' "$ROOT"/tests/*.c`. That glob is non-recursive. VERIFIED by
running the same pattern recursively: `tests/repro/repro_parallel_determinism.c:143` and `:180` both
contain plain `SKIP(...)`, and the linter has never seen them. The subdirectory `tests/repro/` holds
20+ `.c` files. Note also that the comment at lines 21-23 reasons carefully about *two* boundary
conditions (that `SKIP_PLATFORM(` cannot match `SKIP(` because the next character is an underscore,
and that the macro definitions live in a `.h` the glob excludes) and gets both right — while missing
the third. Reasoning about a pattern's boundaries in a comment is necessary and demonstrably not
sufficient.

**code-review-graph, `tests/test_prompts.py:47` — a substring assertion that is nearly free.**
VERIFIED. `test_mentions_test_gaps` asserts `"test" in _text(result[0]).lower()`. INFERENCE: "test"
is a four-letter substring of a prompt about code review; this fails only on a total rewrite. The
sibling assertions on `"detect_changes"` and `"affected_flows"` (lines 41, 45) are meaningfully
tighter because those are tool names the prompt must name exactly.

**Not a defect, though my scanner flagged it:** `code-review-graph/tests/test_http_origin_guard.py:114`,
`test_run_http_async_accepts_the_kwargs_we_pass`, contains no `assert`. It calls
`inspect.signature(FastMCP.run_http_async).bind_partial(...)` with the exact kwargs the entry point
passes, which raises `TypeError` when they do not bind. The exception is the assertion. See 3.2 —
this one is a pattern Sync should copy.

### 2.6 One repository's answer to "prove it can fail"

codebase-memory-mcp is the only reference that treats falsifiability as a first-class engineering
artifact, and it does so three ways.

It has a **no-skips lint** (2.5 above), which converts the discipline into a CI gate instead of a
convention.

It has a **contract test for the test harness itself**: `tests/test_parallel_harness_contract.sh`
asserts that the parallel scheduler reports `rc=124 pass=1 fail=0` for a suite that hangs after
printing its summary (line 103) and `rc=97 pass=0 fail=0` for a suite that never prints one (line
109), by running deliberately misbehaving fake runners. VERIFIED. That is "break the thing
deliberately, watch the test go red" institutionalised as a permanent test rather than a one-time
ritual.

And it has `tests/repro/repro_parallel_determinism.c`, whose header (VERIFIED, lines 1-40) is the
single most relevant document I read this session. The bug is that multi-threaded indexing of a fixed
corpus produces different edge counts run to run and trends below the single-threaded reference. The
invariant is stated as a set equality over sorted `(source_qn, type, target_qn)` triples, explicitly
"NOT raw counts" (line 16). Then, under a heading the author calls an "honest calibration record",
lines 19-31 document three escalating attempts at a self-contained synthetic fixture — 300 files with
dense cross-file calls, 500 files with large fingerprinted bodies, 600 files with token-identical
clustered bodies to force similarity edges — all of which produced a fully deterministic graph across
six multi-threaded runs. The conclusion, quoted: "Rather than ship a false guard (green on buggy
code), this uses the smallest REAL corpus on which the flicker was directly observed."

That is Sync's rule, applied and then obeyed when it cost something. The author had a fixture, could
not make it go red on known-broken code, and refused to commit it as a guard.

The cost is real and also visible: the corpus is a hardcoded absolute path on the author's laptop
(`#define RPD_CORPUS "/Users/martinvogel/perf-bench/linux/fs/xfs"`, line 55), so the test skips
everywhere else including CI — and it is precisely that skip which the no-skips linter cannot see.
The determinism invariant is guarded on exactly one machine in the world.

### 2.7 Non-determinism other than the model

**Clocks.** Almost nobody injects one. VERIFIED by grep for `useFakeTimers`, `freezegun`,
`freeze_time` and `vi.setSystemTime`: five files across nine repositories —
`code-review-graph/tests/test_agent_transparency.py`, `code-review-graph/tests/test_embeddings.py`,
`codegraph/__tests__/daemon-bind-failure.test.ts`,
`open-code-review/extensions/vscode/src/extension/services/__tests__/CliService.cancel.test.ts`, and
`Understand-Anything/.../dashboard/src/__tests__/freshness.test.ts`. Everything else that touches time
uses real time. Sync's mtime rule in `CLAUDE.md` ("never detect a write by comparing against a live
mtime") has no analogue anywhere in the set, and given how little clock injection exists, INFERENCE:
the same class of defect is likely latent in several of these suites and simply undetected.

**Seeds.** VERIFIED: no test in any repository seeds a random number generator. The `random.seed`
hits are in `code-review-graph/diagrams/generate_diagrams.py` (a diagram generator) and cookbook
demo data.

**Environment and home directory.** code-review-graph has the best answer, and its reasoning is
worth quoting. `tests/conftest.py:15-36` is an autouse fixture redirecting `~/.code-review-graph`
into a tmp dir, and its docstring explains both leaks that motivated it and then says: "Autouse and
unconditional: an opt-in fixture would silently stop protecting a test the day someone forgets to
request it." VERIFIED.

**Process and platform.** codebase-memory-mcp's `test-infrastructure/ladder.sh` runs four legs in
parallel — macOS native in the foreground, lint plus a Linux container plus a Windows UTM VM in the
background — and its header states "A missing prerequisite fails that leg loudly — never silently
skips it" (VERIFIED, lines 15-16). Understand-Anything's `.github/workflows/ci.yml:25` runs the
matrix on `[ubuntu-latest, windows-latest]`. open-code-review runs `go test -race` in CI
(`.github/workflows/ci.yml:57`).

**Coverage gates.** Exactly one repository enforces one. VERIFIED:
`open-code-review/.github/workflows/ci.yml:60-68` computes total coverage from `coverage.out` and
exits 1 below 80%. No other repository in the set gates on coverage, and Sync does not either.

## 3. What Sync should adopt

### 3.1 A no-skips lint, with `SKIP_PLATFORM` as the single exemption

Proof it works: `codebase-memory-mcp/scripts/check-no-test-skips.sh` plus the `FAIL` and
`SKIP_PLATFORM` macros at `tests/test_framework.h:68-88`. The doctrine is in the script's lines
11-12.

Where it lands in Sync: a new `scripts/lint_test_skips.py` alongside the existing
`scripts/lint_encoding.py` and `scripts/lint_dead_links.py`, wired into the same CI step, and a
paragraph in `.claude/rules/test-discipline.md` under the existing "A test that cannot fail" heading.
The rule would be that `pytest.skip` is forbidden except where the reason names a platform or a
genuinely absent local toolchain, enforced by requiring a marker rather than a bare call.

Sync needs this more than most, because it already has a bare skip on exactly the axis the rule
protects: `tests/test_api_routes.py:81-86`, `_web_source()`, calls `pytest.skip` when `web/` is not
checked out — and the test it guards, `test_the_consoles_default_page_size_matches_the_surfaces`
(line 418), is described in its own comment as "the only place a drift can be noticed" because
`web/` has no CI gate. A checkout without `web/` reports that test as skipped, and skipped does not
fail CI. The single guard on a cross-language constant is disarmed by an absent directory.

**Learn the linter's own bug too.** Write the check to walk `tests/` recursively from the start,
not with a flat glob. codebase-memory-mcp's version misses `tests/repro/` and has missed it for as
long as that directory has existed.

### 3.2 A signature-contract test against the installed Claude Agent SDK

Proof it works: `code-review-graph/tests/test_http_origin_guard.py:107-126`, and the module docstring
at lines 4-6 states the argument exactly — "A mock of `mcp.run` cannot catch a keyword the pinned
FastMCP does not accept, so the signature contract is asserted explicitly." The test calls
`inspect.signature(FastMCP.run_http_async).bind_partial(...)` with the real kwargs and lets the
`TypeError` be the assertion.

Where it lands in Sync: `tests/test_agent_patch.py`, beside the existing `fake_query` monkeypatches
at lines 291-374. Every one of those tests replaces `agent_patch.query`, which means none of them can
detect a `ClaudeAgentOptions` field that the installed SDK does not accept. `CLAUDE.md` says the
project has already been wrong about this surface once — "Verified against the installed package:
`ClaudeAgentOptions` exposes `cwd`, `model`, `thinking`, `effort`, `allowed_tools`,
`disallowed_tools`, and `permission_mode` ... and this document previously said otherwise." A
five-line test that constructs `ClaudeAgentOptions(**the_exact_kwargs_run_agent_passes)` and asserts
nothing beyond "it constructed" turns that documentation into a gate, and it costs no network and no
model call. The same test should assert that `output_config`, `max_tokens`, `temperature` and
`budget_tokens` are *rejected*, since CLAUDE.md pins that too.

### 3.3 Extract and execute, rather than grep, when the subject is a config or script

Proof it works: `codegraph/__tests__/install-sh-prune.test.ts:28-49`. Instead of asserting that
`install.sh` contains a prune loop, it locates the block between two sentinel comments
(`# >>> CODEGRAPH_PRUNE_OLD_VERSIONS` / `# <<<`), injects `INSTALL_DIR` and `dest`, runs the real
block under `sh` against a seeded temp tree, and asserts on what is left on disk (lines 69-112). Its
header states the reason: "Rather than duplicate the shell (which would drift from the shipped
script), these tests extract the REAL prune block."

Where it lands in Sync: `tests/test_ci_runs_the_serial_scheduler.py` and
`tests/test_ci_stages_the_corpus_inputs.py`. Sync's version is already better than a grep — it parses
the YAML and walks jobs and steps, and the docstring at lines 27-30 explains why ("`SYNC_DSN` can
reach a step from three scopes and only a parse tells a workflow-level `env` from another job's").
But `SERIAL_SCHEDULER = re.compile(r"-n\s*0(?![.\d])")` at line 42 still matches a regex against a
`run:` string, and the docstring already names the one thing a parse cannot see: a variable written
to `$GITHUB_ENV` by an earlier step. The codegraph pattern suggests the next increment — mark the
serial-run step with a sentinel comment and execute it against a fixture — though I would rate this
the lowest-priority of the three, because Sync's parse is already two rungs above the failure mode.

### 3.4 An adversarial corpus for what the patch agent returns

Proof it works: two files. `PageIndex/tests/test_page_index.py:12-32` feeds the code a model response
that has the right *shape* and the wrong *content* — a table of contents of the correct length with
the entries reordered — and asserts `ValueError`. Lines 34-54 feed it a continuation chunk claiming
`<physical_index_99>` on a two-page document and assert the result's `physical_index` is `None`
rather than 99. And `Understand-Anything/.../llm-analyzer.test.ts:60-155` covers fenced JSON, prose
around JSON, non-JSON, an out-of-enum value, and every optional field missing.

Where it lands in Sync: `tests/test_agent_patch.py`. Sync's existing fakes at lines 291-374 cover the
SDK's failure signals — `ResultMessage` reporting a failed run, no `ResultMessage` arriving at all —
which is the transport layer. What is not covered is the model succeeding while returning something
wrong: staging a file it did not need, editing inside `node_modules`, producing a patch that
typechecks but changes a different call site. Some of that is already tested through
`_agent_doing(work)` at line 431, which is the right mechanism; the gap is a systematic
*adversarial* list of what a confidently wrong agent does, tested one case per behaviour, in the
spirit of PageIndex's reordered-TOC test.

There is a Sync-specific reason this matters more here than in either reference. Sync's patch agent
sits inside a pipeline the project requires to be idempotent, and a model call is not idempotent. The
convergence guarantee therefore has to come from what is written down after the agent runs, not from
the agent. INFERENCE: the property that needs a test is not "the agent produces the right patch" but
"two runs of the remediation stage over the same finding converge on the same `migration_outcome`
rows", and no reference tests anything of that shape.

### 3.5 A scored eval, kept separate from the suite but wired to CI

Proof it works: `code-review-graph/.github/workflows/eval.yml` plus the reproducibility guard at
`code_review_graph/eval/runner.py:48-61`, which refuses to run a benchmark whose config pin does not
match its latest test commit. The counter-example is codegraph, whose eval is genuinely well-designed
(`__tests__/evaluation/scoring.ts`) and reachable by nobody — see 2.4.

Where it lands in Sync: this is largely already built. `tests/test_benchmark_axes.py`,
`test_benchmark_report.py`, `test_binding_accuracy.py`, `test_rank_coverage.py` and the corpus gate
tests exist. The adoptable piece is the config pin — a guard that refuses to report a binding-accuracy
number unless the corpus spec's pinned commit matches the corpus it actually scored. Compare the
existing `tests/test_corpus_hold_back.py:329`, which reads the corpus spec YAML.

## 4. Where Sync is already ahead, and where a reference would be a step back

**Sync's fixture realism is better than anything in the set.** VERIFIED at
`tests/test_agent_patch.py:19-32`, whose comment reads: "Shaped like a real oasdiff record, not a
convenient one: no `field` key (real records never carry one), `path_ptr` is the URL path oasdiff
reports (not a JSON pointer), and the changed property is named only in the backticked token inside
`text`." No reference fixture carries that kind of note. Understand-Anything's parser tests use JSON
the test author wrote to be parsed; PageIndex's model output is invented at the call site. The
difference matters because a fixture that is easier than reality tests a code path that reality will
not take.

**Sync's read-only console test is now stronger than the equivalent in any reference.** The
`RecordingSurface` design at `tests/test_api_routes.py:320-391` observes what the routes *do*.
codebase-memory-mcp's no-skips lint and codegraph's install-script tests are both still greps or
extractions over source. Sync arrived at behavioural observation, which is the rung above.

**Sync's e2e isolation is stricter.** `pyproject.toml:98-99` deselects `-m 'not e2e'` by default and
declares the marker as "makes network and model calls", and `.claude/rules/test-discipline.md` line
23 states the no-vendor-API, no-model-API rule outright. claude-cookbooks does the opposite: its
execution test (`tests/notebook_tests/test_notebooks.py:216-241`) runs real notebooks against the
real API behind `--execute-notebooks` and an `ANTHROPIC_API_KEY` check, and skips otherwise, so its
default-green state proves only that the JSON parses.

**Sync's encoding discipline exceeds the set, and the set demonstrates why it is needed.** VERIFIED:
`claude-cookbooks/tests/notebook_tests/utils.py:339` calls `subprocess.run(cmd, capture_output=True,
text=True, timeout=...)` with no `encoding=` and no `PYTHONIOENCODING` in the child environment —
the exact defect `CLAUDE.md` describes at length, in Anthropic's own repository, in a Windows-hostile
form. Sync's `scripts/lint_encoding.py` plus `tests/test_subprocess_encoding.py` and
`tests/test_decode_handlers.py` have no counterpart anywhere in the nine.

**Three reference approaches would be regressions if adopted.**

*Testing prompts by substring.* `code-review-graph/tests/test_prompts.py:47` and
`Understand-Anything/.../llm-analyzer.test.ts:18-22` both assert that a template contains the strings
that were interpolated into it. Adding this to `build_patch_prompt` would buy Sync eight more green
tests and zero information, and — worse — it would create the impression the prompt is under test.
The parse side of Understand-Anything's file is worth copying; the prompt side is not.

*An 80% coverage gate.* open-code-review's `.github/workflows/ci.yml:60-68` is the only such gate in
the set, and Go's ratio of trivially-coverable getters makes it cheap there —
`internal/agent/coverage_test.go:19-60` is a test named for coverage that asserts on
`Session()`, `FilesReviewed()`, `Diffs()` and five token counters against a freshly constructed
struct. For Sync, whose expensive paths involve Postgres, `tsc`, `git` and a model, a percentage gate
would push effort toward exactly that kind of getter test, which is a test that cannot fail wearing a
different costume. Sync's `.claude/rules/test-discipline.md` already has the better rule: assert the
property the code promises.

*Skipping as a soft failure.* Everything in 2.5. The cookbook's four assertion-free tests and
superpowers' non-failing premature-action check are the reference set's characteristic defect, and
Sync's existing skip at `tests/test_api_routes.py:85` is the one place the same habit has already
taken root.

## 5. Open questions only the owner can settle

**Does the patch agent need an idempotence test, and what would it assert?** The pipeline discipline
requires every stage to converge; the patch agent cannot. Sync's stated position is that `oasdiff`-
derived `vendor_change` rows are the single named exemption. INFERENCE: PATCH is a second
non-convergent source and is not currently exempted in writing. Either the convergence guarantee
attaches to `migration_outcome` and the attempt grain rather than to the patch, in which case that
should be stated in `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` the way the
oasdiff exemption is; or a second exemption is needed. This is a spec question, not a test question,
and only you can answer it.

**Is a real-model drill worth its cost?** superpowers is the only reference that runs the model and
asserts on structured output, and the mechanism transfers cleanly — the Agent SDK can emit a
tool-call stream the same way `claude -p --output-format stream-json` does, so a drill could assert
"the patch agent called Edit before it called Bash" without asserting anything about the code it
wrote. That would catch a prompt regression that no fake can. It also costs money per run, is
inherently flaky, and violates the letter of `.claude/rules/test-discipline.md`'s no-model-API rule —
though the existing `@pytest.mark.e2e` carve-out is the obvious home for it. Worth it or not is a
budget call.

**Should `web/` be in CI, given that one skip disarms the only guard on it?** Section 3.1 covers the
mechanism, but the underlying question is scope: `tests/test_api_routes.py:419-421` states plainly
that `web/` has no CI gate and that this test is the only place a `DEFAULT_LIMIT` drift can be
noticed. Either the console gets a CI job, or the skip becomes a hard failure and every checkout must
carry `web/`. Both are defensible; the current state — a guard that quietly stands down — is the one
that is not.

**Is the absence of property-based testing across all nine references a signal or an accident?**
Nobody in the set uses hypothesis or an equivalent, including codebase-memory-mcp, which spent three
documented attempts hand-building a fixture for a property (`repro_parallel_determinism.c:19-31`) and
gave up. Sync has at least three properties that are natural fits — stage idempotence, the rung
attribution invariant, and the `graph-grain` refusal to write an unattributed finding. INFERENCE: a
generator over `Finding` and `CallSite` shapes would probe the grain rules far harder than the
current example-based tests do. But it is a dependency, a learning curve and a source of slow flaky
failures for a solo founder, and the fact that nine substantial projects all declined is at least
weak evidence against.

## Coverage honesty

Examined for this dimension, in descending depth:

- **claude-cookbooks** — read `tests/notebook_tests/test_notebooks.py` and `utils.py` in full,
  plus `conftest.py`. Did not examine the 92 notebooks, the `evals/agentic_search` notebook, or
  `tool_evaluation/`.
- **codebase-memory-mcp** — read `tests/test_framework.h`, `scripts/check-no-test-skips.sh`,
  `tests/repro/repro_parallel_determinism.c` header and skip sites, `tests/test_parallel_harness_
  contract.sh` head, `test-infrastructure/ladder.sh` head, and the header of
  `tests/test_convergence_probe.c`. Did **not** read the other ~140 C test files; the LOC figures are
  counts, not reads.
- **superpowers** — read `tests/explicit-skill-requests/run-test.sh`,
  `tests/claude-code/run-skill-tests.sh`, `tests/claude-code/test-subagent-driven-development.sh`.
  Did not read the seven `brainstorm-server/*.test.js` files or the other shell suites.
- **open-code-review** — read `internal/llmloop/loop_test.go` (first 140 lines),
  `internal/llm/client_test.go` (first 120), `internal/agent/coverage_test.go` (first 60),
  `internal/tool/stub.go`, `internal/tool/code_comment.go:55-130`, `ASSURANCE_CASE.md` (first 80),
  `.github/workflows/ci.yml:50-80`. Did not read the remaining ~100 Go test files.
- **code-review-graph** — read `tests/conftest.py`, `tests/test_http_origin_guard.py` (head and the
  signature-contract class), `tests/test_prompts.py` head, `code_review_graph/eval/runner.py` head,
  `pyproject.toml` pytest section. Scanned `tests/test_embeddings.py` and
  `tests/test_agent_transparency.py` by grep only.
- **codegraph** — read `vitest.config.ts`, `__tests__/install-sh-prune.test.ts`,
  `__tests__/evaluation/{runner,scoring}.ts`. Did not read any of the 162 `*.test.ts` files beyond
  the one named.
- **PageIndex** — read all three test files in full. This repository's suite is small enough that
  coverage here is complete.
- **Understand-Anything** — read `llm-analyzer.test.ts` in full, plus `vitest.config.ts` and
  `.github/workflows/ci.yml`. Did not read the 67 other test files.
- **skills** — listed the tree and confirmed zero test files and one release-only workflow. Nothing
  further to read.

Sync itself: read `.claude/rules/test-discipline.md`, `tests/test_api_routes.py`,
`tests/test_ci_runs_the_serial_scheduler.py` (first 80 lines), the head of `tests/test_agent_patch.py`
and `tests/test_e2e_stripe.py`, the `[tool.pytest.ini_options]` block, and the git history of
`tests/test_api_routes.py`. I did not read the other ~155 Sync test files, so any claim about what
Sync does *not* test should be read as scoped to what I opened.

Two claims I could not close:

- The `\bINSERT\b`-style regex `_MUTATING = re.compile(r"\b(?:INSERT\s+INTO|UPDATE)\s+(vendor_change|
  finding|migration_outcome)\b", re.IGNORECASE)` appears at `tests/test_severity_vocabulary.py:467` in
  commit `0902571`. I did not open the current working-tree version of that file to check whether the
  same pattern survives and whether it has the same underscore blind spot. It is worth ten minutes.
- `open-code-review`'s `ASSURANCE_CASE.md` claims under T6 that malicious LLM responses are mitigated
  by "line number bounds checking against actual diff ranges". I read `internal/tool/code_comment.go`
  (`ParseComments`, lines 71-123) and found no line-number field parsed at all — comments are anchored
  by `existing_code` text — and grep over `internal/` found bounds checks only in
  `internal/tool/file_read.go:39`, which validates a tool *argument*. INFERENCE: the assurance claim
  overstates the code. I did not read `internal/session/` or `internal/scan/` exhaustively, so I state
  this as unresolved rather than as a defect.
