# Continuous integration and release engineering

Reference note, written 2026-08-04 against the nine clones under
`scratchpad/engrefs/`. Every claim below is labelled VERIFIED (I opened the file this
session), REPORTED (a comment or document in the repository asserts it and I did not
independently reproduce it), or INFERENCE (my reasoning from what I read).

## 1. What this dimension covers, and why Sync should care

Continuous integration is the only mechanism a solo, self-funded project has for
noticing that something broke while nobody was looking. It answers three questions that
are otherwise unanswerable: what runs before a change lands, what can actually stop a
change from landing, and what is allowed to reach a user without a human in the loop.

Sync is unusually exposed on all three. It has one maintainer, so there is no second
reviewer whose eyes serve as a backstop. Its product claim is the binding — which call
site depends on which vendor operation — which means correctness lives in a *measurement*
rather than in a feature, and a measurement degrades silently. And it is now polyglot: a
React 19 console reads a Starlette transport whose types are defined in Python, and the
TypeScript side restates several of those types by hand.

That last property is the dangerous one, because the failure has no local symptom.
`tsc` proves the TypeScript is internally consistent. `pytest` proves the Python is
internally consistent. Both stay green while the two disagree. This note therefore
weights the cross-language question heavily, and reports what each reference does about
it — including the ones that do nothing.

The second thing this dimension is good for is finding gates that exist but cannot fail.
A green check that is structurally incapable of turning red is worse than no check,
because it is read as assurance. Sync's own rule says a test that has never failed has
never been shown to test anything; the same rule applies to a workflow step, and the
corpus contains a lot of steps that fail it.

## 2. The design space across the nine repositories

I read every workflow file in all nine clones, plus the CI helper scripts each of them
calls. Total surface: 55 workflow files, 6,172 lines.

### 2.1 Three topologies, and one absence

**Monolithic single job.** `Understand-Anything/.github/workflows/ci.yml` (VERIFIED) is
64 lines and one job. It installs pnpm and Python in the same runner (lines 30-40),
builds three TypeScript packages (48-55), runs two vitest suites (57-61), then runs
`python -m unittest` on the Python skill helpers (63-64). Matrix is `[ubuntu-latest,
windows-latest]` with `fail-fast: false` (22-26). The virtue is that the two languages
cannot be independently green: one job, one verdict. The cost is that a Python-only
change pays for three TypeScript builds.

**Per-artifact workflows with path filters.** `open-code-review` splits by artifact.
`ci.yml` (VERIFIED) is the Go pipeline with no paths filter; `pages-ci.yml:4-7` scopes to
`pages/**`; `vscode-ext.yml:4-7` scopes to `extensions/vscode/**`; `translation-sync.yml:9-14`
scopes to `README*.md` and the docs tree. Each is a separate required context. This is the
same shape Sync's new `web` job takes, generalised, and it is the cheapest topology to
reason about. It has one trap, discussed in §3.5.

**Reusable workflows composed by an entry point.** `codebase-memory-mcp` is the most
elaborate CI in the corpus by a wide margin (VERIFIED: 22 workflow files, 2,479 lines).
The underscore-prefixed files (`_lint.yml`, `_security.yml`, `_test.yml`, `_build.yml`,
`_smoke.yml`, `_soak.yml`) are `workflow_call`-only libraries; `pr.yml`, `release.yml`,
`dry-run.yml` and `nightly-soak.yml` are the entry points that compose them with different
inputs. `pr.yml:30-41` calls `_test.yml` with `skip_perf: true, shard_suites: true`;
`release.yml:58-65` calls the same file with `broad_platforms: true`. One test definition,
three venues, no copy-paste drift. INFERENCE: this is the right answer once you have more
than two entry points, and overkill below that.

**No CI at all.** Four of the nine either have no pipeline or have one that runs nothing:

- `codegraph` has 162 vitest files under `__tests__/` and `"test": "vitest run"` at
  `package.json:26`, and **no workflow that ever runs them on a pull request** (VERIFIED).
  Its only two workflows are `deploy-site.yml` (push to main, `paths: site/**`) and
  `release.yml` (`workflow_dispatch` only, `release.yml:23-24`). A codegraph PR receives
  zero automated verification of any kind. Its excellent kernel-parity gate (§2.5) runs
  only inside the release.
- `PageIndex` has `tests/test_page_index.py`, `tests/test_page_index_md.py` and
  `tests/test_issue_163.py`, and six workflows, none of which run pytest (VERIFIED). Five
  are issue triage and auto-close automation; the sixth is CodeQL. A published Python
  library with no test CI whatsoever.
- `superpowers` has no `.github/workflows` directory (VERIFIED). It has
  `.pre-commit-config.yaml` with three hooks, all three scoped `files: ^evals/.*\.py$`
  (lines 8, 14, 21). The 89 markdown skill files, 38 shell scripts and 12 test
  subdirectories under `tests/` have nothing at all, locally or remotely.
- `skills` has exactly one workflow, `release.yml`, which is changesets versioning
  (VERIFIED). No lint, no test, no check of any kind on a pull request.

This is worth stating plainly: **four of the nine references, including two that ship to a
package registry, would look green on a change that broke them.** Sync's ci.yml is above
the median of this corpus, not below it.

### 2.2 Gates that exist but cannot fail

Each of these I opened and read this session (VERIFIED). I separate the deliberate ones
from the accidental ones, because the distinction is the whole finding.

**Accidental, or at least undocumented:**

| Path | What it is |
|---|---|
| `claude-cookbooks/.github/workflows/notebook-quality.yml:41-42` | `uv run ruff check **/*.ipynb --show-fixes \|\| true` and `ruff format --check \|\| true`. Both lints run, print, and can never fail. |
| `claude-cookbooks/.github/workflows/notebook-quality.yml:44-55` | "Validate notebook structure" computes `has_issues` and `exit 1`s, then carries `continue-on-error: true`. Unlike its sibling in `lint-format.yml`, this file has **no downstream step that re-raises** — the file ends at line 138 and the only consumer of `has_issues` is the Claude comment step at line 58. Notebook structure validation is advisory. |
| `claude-cookbooks/.github/workflows/notebook-quality.yml:105-116` | Notebook execution against the live API, with `\|\| echo "⚠️  Failed: $notebook"` on line 115. Every execution failure is swallowed. The workflow's own comment at 91-95 admits it: "Non-fatal in the meantime". |
| `claude-cookbooks/.github/workflows/claude-model-check.yml:69-88` | The workflow's only substantive step invokes `claude-code-action` with the prompt `/model-check` and `--allowedTools "Bash(gh pr comment:*)…"`. There is no final status step. The job succeeds if the *action* ran, regardless of what it found. An LLM-as-gate that costs money per PR and is structurally incapable of blocking. |
| `claude-cookbooks/.github/workflows/links.yml:124-125, 140-141` | Both lychee invocations pass `fail: false` and `failIfEmpty: false`. The only consumer of the result is a sticky PR comment (line 143-148). Link rot never fails a build. |

**Deliberate and documented — different thing, worth separating:**

- `code-review-graph/.github/workflows/eval.yml:39` — `|| true` on the benchmark run,
  with a six-line header comment (lines 3-6) saying eval failures are informational
  "until the co-change baseline has enough history to set thresholds against". That is
  exactly Sync's argument for not gating coverage, arrived at independently. The residual
  weakness: the upload and summary steps use `if: always()` (42, 51), so a crashed eval
  produces an empty artifact and a report over stale results with nothing that notices.
- `open-code-review/.github/workflows/translation-sync.yml:47-53` — docs translation drift
  is `continue-on-error: true` and says so at line 44. Its sibling check on the same file,
  README structural parity across five locales, is blocking (line 39-40). Advisory and
  blocking, side by side, each labelled.
- `codebase-memory-mcp/.github/workflows/smoke.yml:97-101` and `_smoke.yml:337-343` — the
  first is an experimental `windows-11-arm` runner, the second a Glama directory image;
  both carry a comment naming why a red there must not block a release.
- `codebase-memory-mcp/.github/workflows/_test.yml:101, 373` —
  `continue-on-error: ${{ matrix.optional == true }}`. Only broad-matrix legs are optional,
  and `_test.yml:46` states that broad legs are required gates elsewhere.

**The counter-pattern, and the best-engineered soft gate in the corpus.**
`claude-cookbooks/.github/workflows/lint-format.yml:89` and `:113` also carry
`continue-on-error: true` — but lines 150-156 re-raise:

```yaml
- name: Fail if issues found
  if: |
    steps.format-check.outputs.has_format_issues == 'true' ||
    steps.lint-check.outputs.has_lint_issues == 'true'
  run: exit 1
```

This is a *deferred* gate, not a broken one. It exists so the Claude-authored PR comment
can be posted before the job dies. `notebook-tests.yml` does the same at lines 117 and 215
with a "Final status check" at 231-256, and its comment (233-240) shows they had already
been bitten by the subtle version of this bug:

> 'failure' only when the execution step's own SCRIPT errored (its per-notebook test
> failures never fail the step) … Without this, a script error there leaves
> `exec_failures` unwritten and would read as a clean skip.

INFERENCE: if Sync ever wants a comment-then-fail step, this is the shape to copy, and the
`EXEC_OUTCOME` discrimination is the part that is easy to omit and expensive to omit.

### 2.3 Fail-open composition — the two best comments in the corpus

`codebase-memory-mcp/.github/workflows/release.yml` carries two hard-won lessons about
`needs:` graphs that Sync will meet the moment it adds one.

Lines 83-89 (VERIFIED):

> GitHub propagates "skipped" TRANSITIVELY down the needs graph, so with `skip_tests=true`
> a skipped `test` skipped smoke and soak too — even though `build` overrode the same
> condition and succeeded. Nothing failed and nothing said so; the pipeline simply carried
> on toward publishing artifacts that had never been smoke-tested or soaked. Every job
> downstream of an optional phase needs this override, or the phase being optional
> silently makes the phases after it optional as well.

Lines 108-112 (VERIFIED):

> Requires smoke to have actually SUCCEEDED, not merely "not failed". The bare
> `!cancelled() && !failure()` form is fail-OPEN: a skipped smoke is neither cancelled nor
> failed, so a draft was one condition away from being cut from binaries nobody had run.

The fix is to name the result explicitly rather than rely on the absence of failure:

```yaml
if: >-
  ${{ !cancelled() && !failure()
  && needs.smoke.result == 'success'
  && (needs.soak.result == 'success' || needs.soak.result == 'skipped') }}
```

Sync's `ci.yml` has no `needs:` anywhere — three fully independent jobs — so it is immune
today. That immunity ends with the first `needs:`.

### 2.4 The aggregate gate

`codebase-memory-mcp/.github/workflows/pr.yml:150-165` (VERIFIED) defines one job, `ci-ok`,
whose `needs:` names every other job in the workflow, runs `if: always()`, and calls
`scripts/ci/require-all-green.sh` with `RESULTS: ${{ toJSON(needs) }}`. The script is 31
lines and its whole logic is:

```python
bad = {k: v['result'] for k, v in needs.items() if v['result'] not in ('success', 'skipped')}
if bad:
    print('CI NOT OK:', bad); sys.exit(1)
```

The header comment (lines 1-4, 150-153) states the purpose: branch protection requires
`dco` + `ci-ok` and nothing else, so "matrix renames can never silently deadlock merges",
and `skipped` counts as OK because path-gated jobs skip by design.

This solves a problem Sync has right now. Sync's three jobs — `test`, `serial`, `web` —
each have to be named individually in branch protection. A fourth job added next month
gates nothing at all until somebody remembers to edit a setting that lives outside the
repository. With `ci-ok`, adding a job to `needs:` is a reviewable diff.

### 2.5 Cross-language agreement — the mechanisms, ranked

This is the section the console problem needs. Five distinct approaches appear.

**(a) Scrape both sides and compare — `code-review-graph`.** The direct hit.
`code-review-graph/.github/workflows/ci.yml:52-72` (VERIFIED) is a standalone job named
`schema-sync` with no build, no install and no dependencies. It extracts the Python
schema version by regex-parsing `code_review_graph/migrations.py` (whose `MIGRATIONS` dict
is at line 245 and `LATEST_VERSION = max(MIGRATIONS.keys())` at line 256), extracts
`SUPPORTED_SCHEMA_VERSION` from `code-review-graph-vscode/src/backend/sqlite.ts` (line 215,
where it is a `const` inside a function body), and:

```bash
if [ "$PY_VER" != "$TS_VER" ]; then
  echo "::error::Schema version mismatch! Python=$PY_VER, VSCode=$TS_VER"
  exit 1
fi
```

Cost: one runner, one checkout, no dependency install — a few seconds. This is the only
job in the corpus whose sole purpose is "two languages must agree about a constant".

Its weaknesses matter for how Sync should copy it. It *re-implements* the Python semantics
(`max(MIGRATIONS.keys())`) inside a shell heredoc rather than importing the module, so the
gate and the code can diverge in a third way. And it scrapes a TypeScript `const` by
regex, so a refactor that changes the declaration form breaks the extractor. INFERENCE:
under the Actions default shell (`bash -e`), a failed `grep` aborts the assignment and the
step goes red, so a rename fails loudly rather than passing silently — but that is a
property of the default shell, not of the design, and it would flip the moment someone
adds `shell: bash {0}`.

**(b) Generate, then diff against what is committed — `open-code-review`.** The stronger
idiom, applied in that repository to a single language.
`open-code-review/.github/workflows/ci.yml:39-45` (VERIFIED):

```yaml
- name: Check go.mod is tidy
  run: |
    go mod tidy
    if ! git diff --exit-code -- go.mod go.sum; then
      echo "::error::go.mod/go.sum are not tidy. Run 'go mod tidy' and commit the diff above."
      exit 1
    fi
```

Run the generator, diff the result against the committed file, fail on any difference.
INFERENCE, and it is the central recommendation of this note: this idiom generalises to
the polyglot constant problem and is strictly better than scraping, because the generator
names the symbols it emits. A rename on the Python side changes the generated output, the
diff is non-empty, and the gate fails — there is no configuration under which it silently
matches nothing against nothing.

**(c) Make the other language a build input — `codebase-memory-mcp`.** The C binary embeds
the TypeScript graph UI: `scripts/build.sh --with-ui` appears at `_build.yml:100, 176, 247,
319` and `_test.yml:550` (VERIFIED), and `_test.yml:548-549` explains it builds the
frontend with npm and embeds it. There is no separate frontend job to forget, because a
broken frontend fails the C build. `_security.yml:20-21` then runs `scripts/security-ui.sh`
over the built assets, checking (per its header, lines 4-11) that the HTTP server binds
127.0.0.1 only and that no wildcard CORS header ships. INFERENCE: elegant where one
artifact genuinely contains the other; not applicable to Sync, where the console is a
separately-served SPA.

**(d) Differential testing between two implementations — `codegraph`.** The most
sophisticated cross-language mechanism in the corpus and the one nobody runs.
`codegraph/scripts/kernel-parity.mjs` (VERIFIED, 60+ lines read) runs both the Rust native
kernel and the TypeScript/wasm walker over the same files and diffs the per-file
`ExtractionResult` as canonicalised sets of nodes, edges and refs; exit 0 is parity, 1 is
diffs, 2 is a setup error. Fourteen suites under `__tests__/kernel-*-parity.test.ts` cover
one language family each. It runs at `release.yml:179-195` with
`CODEGRAPH_KERNEL_EXPECT=1` turning a missing binary into a failure — and, because
codegraph has no PR workflow, **only there**. A parity regression is discoverable no
earlier than the release that ships it.

The header comment at `kernel-parity.mjs:15-20` is worth reading for a different reason: it
records that the `--max-deferral` threshold was calibrated per language family from
measured incidence (git 19%, protobuf 26%, fmt 42% for C/C++ against 0–0.4% for
ts/java/py/go), and explains why one global number would fail healthy sweeps. That is the
same argument `2026-07-27-sync-benchmark-gates.md` makes, reached from a different
direction.

**(e) Structural parity of prose across locales — `open-code-review`.**
`translation-sync.yml:39-40` (VERIFIED) blocks when the five `README*.md` translations
stop sharing an identical level-2 section structure. Not a code constant, but the same
class of problem — N artifacts that must stay isomorphic and have no compiler between them.

### 2.6 Coverage thresholds

Three distinct positions (all VERIFIED):

- `open-code-review/.github/workflows/ci.yml:60-68` — hard 80% Go floor, computed by
  piping `go tool cover -func` through awk, blocking.
- `code-review-graph/.github/workflows/ci.yml:88` — `--cov-fail-under=65`, blocking, on a
  four-version Python matrix (3.10–3.13).
- Sync — records, deliberately does not gate, and argues the position in 26 lines of
  comment at `ci.yml:86-121`.

Neither reference documents where its number came from. INFERENCE: 80 and 65 are both
round numbers chosen once and never revisited, which is precisely the failure mode
`2026-07-27-sync-benchmark-gates.md` predicts. Sync's position is better argued than
either, and the `status > 1` discrimination at `ci.yml:118-121` — distinguishing "a number
moved" from "no number was produced" — has no analogue anywhere in the corpus.

### 2.7 Versioning and release

| Repository | Trigger | Version source | Auto-publishes? | Guarded by |
|---|---|---|---|---|
| `skills` | push to main (`release.yml:3-6`) | changesets; 10 pending `.changeset/*.md` in the clone | No — opens a version PR a human merges | Nothing; there is no CI in this repo |
| `code-review-graph` | `release: published` (`publish.yml:3-5`) | git tag / setuptools | Yes, PyPI | `environment: pypi`; **static `PYPI_API_TOKEN`** (line 31) |
| `open-code-review` | tag push `v*` (`release.yml:3-5`) | `GITHUB_REF_NAME`, ldflags-injected (47) | Yes, GitHub Release + 7 npm packages | **Nothing.** `build → release → npm-publish`; no job runs `go test` |
| `codegraph` | `workflow_dispatch` only (23-24) | `package.json` version (144-146) | Yes, GitHub Release + npm | Kernel contract suite (179-195) only; no general test run |
| `codebase-memory-mcp` | `workflow_dispatch` with a version input (8-38) | dispatch input | Yes, npm + PyPI + MCP Registry | The full lint→test→build→smoke/soak→security chain |

Three details worth lifting out.

**`open-code-review` publishes from a red commit.** VERIFIED: `release.yml` has three jobs
and none of them depends on `ci.yml` or runs a test. A `git tag v1.2.3 && git push --tags`
on a commit whose suite is failing ships six platform binaries and seven npm packages.

**`codegraph` uses npm OIDC trusted publishing and has no `NPM_TOKEN`** (`release.yml:18-22,
249-254`, VERIFIED). It also verifies after the fact (273-287), with the justification
"npm publish can print success without persisting" — a retry loop that polls
`npm view "$name@$V"` up to six times before declaring the release shipped. INFERENCE: this
is the strongest supply-chain posture in the corpus for a small project, and it costs
nothing but registry configuration. `code-review-graph` is the only reference still holding
a long-lived registry token where OIDC exists.

**`codebase-memory-mcp` releases draft-first.** The GitHub release is created as a draft
(`release.yml:184-185`) and un-drafted by a terminal job only after npm and PyPI both
succeed (`release.yml:394-409`), so a half-shipped state is never user-visible. The chain
also runs `cosign sign-blob` over every artifact (156-160), attests an SBOM (147-151), and
gates on a zero-tolerance VirusTotal scan (`release.yml:252-261`) whose comment says false
positives are resolved upstream with Microsoft, "never by loosening this gate".

### 2.8 Matrices, caching, wall clock

**Matrices.** `code-review-graph/ci.yml:76-78` is a 4-way Python version matrix plus a
dedicated `windows-native` job (90-119) that names 15 specific test files — Windows daemon
and file-handle behaviour. `open-code-review/ci.yml:89-115` cross-compiles 5 GOOS/GOARCH
pairs to `/dev/null` — a build-only smoke that costs almost nothing.
`Understand-Anything/ci.yml:22-26` is 2 OSes. `codebase-memory-mcp/_test.yml:27-91`
computes its matrices as JSON in a `setup-matrix` job so that a `broad_platforms` input can
swap the whole platform set without editing the matrix, and so that shards are "minted HERE
from one expansion" (line 75) rather than configured per leg.

**Caching.** `codebase-memory-mcp` is the only reference that reasons about cache
*correctness* rather than just cache hits. `_test.yml:114-135` (VERIFIED):

> Verified compiler cache: `CCACHE_COMPILERCHECK=content` keys every entry on the
> compiler-binary CONTENT plus the fully preprocessed input, so a hit is provably the
> identical compilation — a stale or foreign cache can only miss, never return wrong
> output.

That content-keying is what makes the cross-ref restore-key fallback safe, and the comment
quantifies the win: "~8-12 minutes on every first-of-ref build". It also ships
`cache-warm.yml`, a nightly build-only job whose header (lines 1-11) explains that GitHub's
cache isolation meant PRs could only restore caches written by their own ref or the base
branch, and nothing was writing test caches in main's scope — so every fresh PR built cold
until this job existed. INFERENCE: this is a real and non-obvious GitHub behaviour that
will bite Sync's `uv` and `npm` caches the same way, though at a far smaller magnitude.

**Wall clock.** `timeout-minutes` is set on every job in `codebase-memory-mcp` and
`open-code-review`, on two jobs in `code-review-graph` (20 and 45), and **nowhere at all**
in `claude-cookbooks`, `Understand-Anything`, `codegraph`, `skills` or `superpowers`
(VERIFIED by grep across all 55 workflow files). The declared budgets reveal the intended
shape: `open-code-review` 15 minutes for the whole Go suite; `code-review-graph` 20;
`codebase-memory-mcp` 240 per test leg, 560 for a soak, with `release.yml:34-38` offering a
`skip_tests` input because "re-running ~2h of tests adds no information".

Sync sets no `timeout-minutes` on any job. The GitHub default is 360 minutes.

## 3. What Sync should adopt

Each item names the repository and file that proves it works, and where it lands in Sync.

### 3.1 A generated-constants parity gate (the headline)

**Proof it works:** `code-review-graph/.github/workflows/ci.yml:52-72` proves a
Python↔TypeScript constant gate is a viable, cheap, standalone job. `open-code-review/
.github/workflows/ci.yml:39-45` proves the generate-then-`git diff --exit-code` idiom.
Combine them; do not copy the scraping half.

**The gap it closes, concretely.** `web/src/api/types.ts:9-11` says in its own docstring
"Mirrors `FindingRung` in `sync.core.models`". The truth is `src/sync/core/models.py:33`:

```python
BindingRung = Literal["static", "resolved", "observed", "unresolved"]
```

and line 37, `FindingRung = BindingRung | Literal["unattributed"]`. The second mirrored
union is `WorkflowOutcome` at `web/src/api/types.ts:154`. Sync's `web` job runs
`npm run build`, which is `tsc -b && vite build` (`web/package.json:8`) — and `tsc` cannot
see Python. Adding a fifth rung on the Python side leaves every check in the repository
green while the console silently renders it as an unhandled case. (VERIFIED: all four file
references read this session.)

**Where it lands.** A script `scripts/emit_web_constants.py` that imports
`sync.core.models` and writes `web/src/api/generated-constants.ts`; `types.ts` then derives
its unions from that file instead of restating them. Then a job in
`.github/workflows/ci.yml`:

```yaml
  constants:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --dev
      - run: uv run python scripts/emit_web_constants.py
      - run: git diff --exit-code -- web/src/api/generated-constants.ts
```

No Postgres, no Node, no npm install — seconds, and it fails on a rename because the
generator names the symbols. INFERENCE: this is the single highest-value change in this
note.

### 3.2 An aggregate `ci-ok` job

**Proof:** `codebase-memory-mcp/.github/workflows/pr.yml:150-165` plus
`scripts/ci/require-all-green.sh` (31 lines, read in full).

**Where it lands.** One job in `.github/workflows/ci.yml` with
`needs: [test, serial, web, constants]`, `if: always()`, calling a Sync equivalent of
`require-all-green.sh`. Then branch protection names one required context instead of four,
and adding a fifth job is a reviewable diff rather than a settings change nobody sees. This
matters more for Sync than for cbm, because Sync has one maintainer and therefore nobody
who would notice a required check quietly missing from the list.

### 3.3 Self-tests on the gates that have never gone red

**Proof:** `codebase-memory-mcp/.github/workflows/_security.yml:32-33` runs
`scripts/license-gate.sh --selftest` — "a planted violation must be detected" — *before*
running the real gate on line 35. `open-code-review/.github/workflows/translation-sync.yml:34-35`
does the same thing more simply: it runs `check-translation-sync.test.js` before running
`check-translation-sync.js`.

**Why Sync specifically needs this.** Sync's own `ci.yml:136-141` records the exact failure:

> With nothing staging it, `score_corpus.py` refused every time it was reached … so the
> binding gate below has never once run on a runner. The step before this one was failing
> for longer, which is what hid it.

A gate whose failure path has never executed is Sync's own "a test that has never failed"
rule applied one level up, and Sync has already paid for the lesson once.

**Where it lands.** A `--selftest` flag on `scripts/gate_corpus.py` that feeds a
synthesised below-floor score and requires exit 1, invoked as its own step immediately
before the real "Binding floors over the frozen corpus (gated)" step at `ci.yml:170-171`.
The same for `scripts/lint_dead_links.py`.

### 3.4 `timeout-minutes` on every job

**Proof:** every job in `codebase-memory-mcp` and `open-code-review` carries one; the four
repositories with no CI worth the name carry none. Sync carries none. A hung pytest or a
`curl` that stalls fetching the oasdiff tarball burns 6 hours of the free allowance. For a
self-funded project that is a real cost, and the fix is one line per job. Something like 20
for `test`, 20 for `serial`, 10 for `web`, 5 for `constants`.

### 3.5 Path filters, but only together with §3.2

**Proof:** `open-code-review/.github/workflows/pages-ci.yml:4-7` and `vscode-ext.yml:4-7`.

Sync's `web` job currently runs on every INDEX/SIGNAL/DETECT change, installing Node and
1,000 npm packages to prove that Python-only edits did not break React. `paths: ['web/**']`
fixes that.

**The trap, and who solved it.** A path-filtered job that is also a required status check
never reports on a PR that does not touch its paths, and GitHub then blocks the merge
forever waiting for a check that will never arrive. `codebase-memory-mcp/pr.yml:45-66`
solves it: a lightweight `changes` job queries the PR's file list through
`gh api --paginate "repos/$REPO/pulls/$PR/files"` and emits a boolean output, downstream
jobs gate on that output rather than on `paths:`, and `require-all-green.sh` counts
`skipped` as OK. That is why §3.2 and §3.5 are one change, not two. (Its comment at line 58
also records a real constraint: "the full `.diff` endpoint rejects large-but-valid PRs at
20k lines", so the filename-only paginated endpoint is used instead.)

### 3.6 A test step for the console

`web/package.json:6-11` has `dev`, `build`, `lint`, `preview` — and **no `test` script**
(VERIFIED). Sync's `web` job therefore lints and typechecks a React console that has no
tests at all. `open-code-review/vscode-ext.yml:49-50` runs `yarn test`;
`Understand-Anything/ci.yml:57-61` runs vitest on two packages. Whether the console should
have tests is a product question, not a CI one — but the CI note should record that the
gate currently proves compilation and nothing about behaviour.

### 3.7 Verify a publish actually landed

If Sync ever publishes `sync.core` to PyPI so third parties can write adapters — which the
import-boundary rule exists to make possible — copy `codegraph/release.yml:273-287`: after
publishing, poll the registry until the version appears, with a bounded retry, and fail if
it never does. And copy `codegraph/release.yml:18-22`: OIDC trusted publishing, no
long-lived token. `code-review-graph/publish.yml:31` is the counter-example.

## 4. Where Sync is already ahead, and where a reference would be a step backwards

### 4.1 Ahead

**The coverage argument.** `ci.yml:86-121` is the most carefully reasoned position on
coverage in the entire corpus, and the only one that distinguishes "the number moved" from
"no number was produced" (`status > 1` at lines 118-121). `open-code-review`'s 80 and
`code-review-graph`'s 65 are undefended constants. Do not replace Sync's argued non-gate
with either of them.

**A test that asserts on the CI configuration.** `tests/test_ci_runs_the_serial_scheduler.py`
refuses a `SYNC_DSN` pin in the `serial` job (`ci.yml:185-191`). Nothing else in the corpus
tests its own workflow file. The nearest relative is
`codebase-memory-mcp/_lint.yml:20-21`, `scripts/check-no-test-skips.sh` — "tests must pass
or fail — no SKIPs" — which polices tests rather than workflows, and is itself worth
stealing as a smaller idea.

**Verifying a pinned tool against its pin.** `ci.yml:58-62` runs `tools/oasdiff --version`
and fails unless the string equals the version read from `.oasdiff-version`. Several
references pin action SHAs thoroughly — `codebase-memory-mcp` pins every single one — but
nobody else checks that a downloaded binary is the binary they asked for. The comment
(46-49) names why: "a version that is only echoed is a version nobody checks".

**A ratchet with a shrinking baseline.** `ci.yml:80-81`, `lint_dead_links.py --baseline`,
where "an entry that no longer violates fails here until it is deleted". No reference has a
one-way ratchet. `codebase-memory-mcp`'s license gate is zero-tolerance, which is stricter
but only workable because they started from zero.

**The `serial` job.** `ci.yml:192-247` re-runs the whole suite under the opposite scheduler
because the defect class is one test breaking a later test in the same process. The nearest
analogue is `codebase-memory-mcp`'s shard-completeness (`_test.yml:484-503`,
`scripts/ci/verify-shard-union.sh`), which proves the union of shard slices equals the full
suite list — a different guarantee, and worth knowing about if Sync ever shards, but not a
substitute.

### 4.2 Step backwards, with the cost named

**Self-hosted runners.** `open-code-review` runs everything on `runs-on: self-hosted` in
containers capped at `--cpus=2` (`ci.yml:18-22`). For a solo founder that is a machine to
patch, monitor and pay for, and a single point of failure for every merge. GitHub's hosted
free tier is enough for a pipeline Sync's size.

**240-minute jobs and 560-minute soaks.** `codebase-memory-mcp/_test.yml:102` and
`_soak.yml`. Its 22 workflows are proportionate to a C codebase shipping signed binaries to
six platforms through three registries. Sync ships a Python service and an SPA. Adopting
the *patterns* (`ci-ok`, gate self-tests, reusable workflows when there are three entry
points) is right; adopting the *scale* would cost more maintenance than the whole pipeline
is worth.

**LLM-as-gate.** `claude-cookbooks/claude-model-check.yml` invokes a model on every PR to
review changed files, and cannot fail. It costs money per PR and produces a green check
that means "the action ran". If Sync wants model-assisted review, keep it out of the gate
path entirely — the failure mode here is not that it is useless, it is that it *looks* like
a gate in the checks list.

**Regex-scraping constants across languages.** `code-review-graph`'s `schema-sync` is the
right *idea* implemented the fragile way: it re-implements `max(MIGRATIONS.keys())` in a
shell heredoc and pattern-matches a `const` declared inside a TypeScript function body.
Copy the job's existence, not its extraction method — §3.1 says why.

## 5. Open questions only the project's owner can settle

1. **Should the console's constants be generated or asserted?** Generation
   (`emit_web_constants.py` writing a TypeScript file) makes drift impossible but puts a
   generated artifact in `web/src/`, which the console's authors have to accept. Assertion
   (a parity check that reads both sides) keeps `types.ts` hand-written but can only catch
   the mismatches it was told to look for. This note recommends generation; the cost is a
   committed generated file and a regeneration step in the local loop.

2. **Should the frozen-corpus gate move off the PR path?** `ci.yml:132-171` fetches a
   corpus, stages pinned Stripe specifications through `gh`, stages a symbol map, creates a
   second database and scores a benchmark — on every pull request, including
   documentation-only ones. `codebase-memory-mcp` puts work of this weight behind a
   `changes` job (`pr.yml:45-66`) or moves it to `nightly-soak.yml`. Whether the binding
   floors are a merge gate or a nightly signal is a product judgement about how fast the
   binding measurement can regress unnoticed.

3. **Is `web` allowed to be red while `main` is green?** Right now the three jobs are
   independent, and nothing says whether a console build failure should block a graph-layer
   merge. `open-code-review` says yes-by-default (separate required checks);
   `Understand-Anything` says no (one job, one verdict). The answer determines whether §3.2
   lists `web` in `needs:` or leaves it out.

4. **How much CI budget is this worth?** Sync's pipeline is short today. Every item in §3
   adds runner minutes: §3.1 adds a job, §3.2 adds a job, §3.3 adds two steps, §3.5 *saves*
   time. On the free tier this is free for a public repository and metered for a private
   one, and I do not know which Sync is.

5. **Does anything publish yet?** Sync has no release workflow at all. The whole of §2.7 is
   forward-looking. If `sync.core` is going to PyPI so third parties can write adapters,
   the decisions to make early are OIDC versus a stored token, and whether a tag can ever
   publish without a green suite — `open-code-review` shows what the second one costs when
   you get it wrong.

---

**Coverage honesty.** I read every workflow file in all nine clones —
`open-code-review` (8), `PageIndex` (6), `codebase-memory-mcp` (22), `code-review-graph` (5),
`codegraph` (2), `Understand-Anything` (2), `superpowers` (0), `skills` (1),
`claude-cookbooks` (9) — plus `require-all-green.sh`, `verify-shard-union.sh`,
`kernel-parity.mjs` (first 60 lines), `security-ui.sh` (header), and
`superpowers/.pre-commit-config.yaml`. I read `_test.yml` (561 lines) in full via targeted
extracts rather than one pass, and `_build.yml`, `_smoke.yml` and `_soak.yml` only through
greps for gate structure, matrices and `continue-on-error` — so my account of those three
files' internals is partial, and any claim about them here is scoped to what the grep
showed. I did not examine `bug-repro.yml`, `fast-repro.yml`, `dry-run.yml`, `stale.yml`,
`issue-labeler.yml`, `label-actions.yml`, `pr-acknowledgement.yml`, `pages.yml`,
`scorecard.yml`, or any of the four repositories' CodeQL configurations beyond noting they
exist. I did not read `Makefile`, `tox.ini` or `pyproject.toml` test configuration in the
references, so claims about what a referenced `make check` or `npm test` actually runs are
INFERENCE from the workflow call site alone.

**One correction to the brief.** The brief states Sync's console "has no CI gate
whatsoever: Node is never installed on a runner and the frontend is never built there".
That was true when the brief was written and is no longer true: commit `0902571`
("ci: add a build gate for the operator console") added a `web` job at
`.github/workflows/ci.yml:249-285` which installs Node 22.22.0, runs `npm ci`, `npm run
lint` and `npm run build` (VERIFIED, read this session). The gate exists. What does **not**
exist is anything that could notice Python↔TypeScript drift — `tsc` proves the TypeScript
is self-consistent and is blind to `sync.core.models` by construction — so the specific
defect the brief names is still entirely unguarded, and §3.1 is the fix.
