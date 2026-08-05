# M4 Slice 3 — Dogfooding, and the loop that makes the console a test surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one command drive the shipped pipeline against a pinned fixture repository, all the
way to the last node before anything touches a remote, writing real findings and real checkpoints
into the real database — so the console shows a real run instead of rows somebody typed in by hand,
and so a failure in the pipeline is *seen* rather than inferred from a log.

Everything below is grounded in a file that exists. Where a claim could not be checked, it says so.

---

## 1. What dogfooding means here, decided

### The hollow reading, rejected

The obvious reading is "point Sync at the Sync repository". It is close to worthless, and the
reasons are structural rather than incidental:

- **The language does not match.** Sync's tree is Python. The static verification gate is `tsc`
  (`.claude/rules/remediate-stage.md`, *Nothing reaches a pull request unverified*), and
  `PythonAdapter` declares itself unverifiable (`src/sync/index/python_lang.py:177,179`).
  `route_after_prepare` routes an unverifiable language to `report` rather than `patch`
  (`src/sync/remediate/nodes.py:188-190`), so a Sync-on-Sync run cannot reach the patch node at
  all, by design and correctly.
- **The run would not start.** A run is anchored on a registry vendor and
  `select_language_adapter` refuses a repository whose manifest does not declare that vendor's SDK
  (`src/sync/cli.py:216-248`, `src/sync/index/python_lang.py:290-309`). Sync's `pyproject.toml`
  declares no registry vendor's package (`pyproject.toml:23-48`), so the run exits 2 before
  indexing anything.
- **The one signal that could bite is not wired to Python.** Sync genuinely depends on a third-party
  API whose vendor publishes retirements: it pins `claude-agent-sdk` (`pyproject.toml:25`) and
  `CLAUDE.md` mandates the literal `model="claude-opus-5"` at every call site. `ANTHROPIC` is a
  shipped deprecation source (`src/sync/signals/deprecations/adapter.py:62-70`, in
  `DEPRECATION_SOURCES` at `:117`). But the pass that indexes model-id literals walks `*.ts` only
  (`src/sync/cli.py:732`), so it finds none of Sync's own.

So "run the indexer on ourselves" would produce a clean scan, and a clean scan there means the
indexer found nothing to find. A green result would prove nothing. **Rejected.**

### The reading this plan adopts

**Dogfooding here is using the console — our own product's operator surface — as the instrument
that observes our own pipeline running, on every rehearsal, instead of reading a terminal.**

The product's claim is that competing tools present a black box and a result and ask a reviewer to
trust it, and that Sync shows its reasoning instead. Right now we do not use that surface on
ourselves. Every UI check to date has been performed against checkpoint rows inserted by hand into
Postgres — three separate sessions each retyped
`tests/test_dashboard_queries.py:184-210`'s helper against a live database and then tore it down
(`.superpowers/sdd/2026-07-30-sync-m4-dashboard/workflow-stale-state-report.md:31-36`,
`task-4-report.md:767-790`, `progress.md:98,131-135`). Task 4's own report names the consequence:
*"The populated view was proven against hand-inserted checkpoint rows, never against a real run"*
(`task-4-report.md:325-334`), with named uncertainty about the real shapes of `replay_evidence`,
`attempt_strategy` and `attempt_ci_result`.

That is the concrete pain. We are asserting that a screen renders the pipeline correctly using data
we invented about the pipeline. Dogfooding ends that.

### The three candidates, ranked

**1. The full pipeline against the existing fixture repository, watched through the console.**
Highest value, and the only one that exercises INDEX, SIGNAL, DETECT and the first two-thirds of
REMEDIATE together. The fixture already exists and is already pinned: `furever` is
`stripe/stripe-connect-furever-demo` at commit `5114c968`, materialised into the gitignored
`.cache/corpus/furever` by `scripts/fetch_corpus_repositories.py`
(`benchmark/corpus/repositories.yaml`, and the script's `ROOT`/`CHECKOUTS` at `:54-56`). It is the
same repository the M0 acceptance test forks (`docs/superpowers/plans/2026-07-25-sync-m0-vendor-change.md:3565`).
**This is what the plan builds.**

**2. The console as the observation surface for a repeated run.** Not a separate candidate — it is
the *point* of (1), and it is the half that has never been done. Ranked with it.

**3. Sync watching the vendor APIs Sync itself depends on.** Genuinely non-hollow, unlike the
repository reading, and worth something: if Anthropic retires `claude-opus-5`, every agent in this
system stops working. But reaching it through the *pipeline* needs two changes — the literal pass
extended past `*.ts` (`cli.py:732`) and a way to anchor a run that is not "the manifest declares a
registry vendor's SDK" (`cli.py:216-248`). The second is an architecture decision, not a task.
**Ranked third, and taken only in its cheap form:** a standing watch that uses the shipped
`DeprecationAdapter` directly against the model ids this repository mandates. Task 7. Hours, not
days, and it is the one place Sync's own signal stage protects Sync.

---

## 2. New milestone, or folded in — folded in, as M4 Slice 3

**Decision: this is M4 Slice 3, sequenced after slice 2. It is not a new milestone.**

The argument, against what is in flight:

- **Milestones here are named for product capability**, from M0 "walking skeleton, one real PR" to
  M6 "show it rather than describe it" (`docs/superpowers/BACKLOG.md`, milestone table). Dogfooding
  is a practice. A milestone whose deliverable is "we used the thing" has no shippable artifact and
  no closing evidence, which is exactly the shape `BACKLOG.md`'s own rule rejects: *"An item that
  cannot say what evidence closes it is not ready to dispatch."*
- **The expensive deliverable here is already M4's debt.** A repeatable way to populate the database
  with real pipeline output is the verification step slice 1 owed and paid by hand, and the step
  slice 2's Task 3 still specifies by hand (*"against a running API with checkpoint rows inserted by
  hand"*, `2026-08-04-sync-m4-slice-2.md`, Task 3 verification). Filing it under a new milestone
  would put two milestones on the same Postgres, the same console and the same solo attention for
  the same reason.
- **The existing improvement tick already assumes it.** `docs/superpowers/loops/console-improvement-tick.md`
  step 4 tells a tick to *run the API and look* — against a database that is empty, so the looking
  establishes nothing about any populated screen. The rehearsal is what makes that step real. A tick
  and the thing it verifies belong to one milestone.

**One carve-out.** The CI-resident half (Task 6) is not console work and lands beside the existing
corpus gate in `scripts/` and `.github/workflows/ci.yml`. It is in this slice because it is the same
decision — what can honestly be asserted about a pipeline run — but it does not touch `web/`.

---

## 3. The architectural spine, before any file

### 1. The safety boundary is an absent object, not a flag

`push_branch`, `await_ci`, `open_pull_request` and `delete_branch` are the only four operations that
reach a remote, and all four are methods on the `Forge` protocol
(`src/sync/remediate/nodes.py:19-29`). The mutations themselves are three lines:
`git push` at `src/sync/forge/github.py:213`, `gh pr create` at `:565`, and the remote delete at
`:297-301`. Nothing else in `src/` pushes anything.

`sync.mcp.propose` already established the right form of guarantee, and its docstring states it
plainly: *"The clearest guarantee that this cannot write is structural rather than asserted:
`push_branch`, `await_ci`, `open_pull_request` and `delete_branch` are all methods on `Forge`, and
this driver never accepts a `Forge`. There is nothing here to call them with."*
(`src/sync/mcp/propose.py:14-20`; the signature at `:52-60` takes no forge, and
`tests/test_mcp_propose_patch.py:234` asserts that by introspection.)

**The rehearsal inherits that guarantee and adds three more layers.** A flag would be one layer, and
the wrong one.

### 2. But a driver with no checkpointer is useless to the console, so the graph must still run

`sync.mcp.propose` composes node factories linearly and writes no checkpoint. That is right for an
MCP preview and wrong here: the console's only window onto a run is the `checkpoints` table
(`src/sync/dashboard/queries.py:181-197`), so a rehearsal that writes no checkpoint is invisible to
the thing it exists to feed.

So the rehearsal runs the real `StateGraph` with the real `PostgresSaver`. The required property is
therefore stronger than "pass no forge to the driver": **`build_graph` must accept `forge=None` and,
when it does, not add the `push_branch`, `await_ci` or `open_pr` nodes at all.** A graph with no
push node cannot push regardless of what any router decides. `build_graph`'s signature today takes
`forge` positionally and required (`src/sync/remediate/graph.py:18`), and wires it into four nodes
(`:38-42`).

**That change belongs to `sync.remediate`, which this session does not own.** It is Task 2, handed
over, with a stated fallback.

### 3. A halted run terminates as `reported`, and says so in its reason

A rehearsal that simply stops leaves a checkpoint with `push_branch` pending and no outcome —
indistinguishable on screen from a run that died, which is precisely the confident-wrong-verdict
failure the console exists to prevent (slice 2's architectural decision 4).

The cheapest honest terminal is the `report` node, which already exists and already fits:
`make_report` touches nothing outside the process, writes no corpus row, and returns
`{"outcome": "reported", "report_reason": ..., "pr_url": None}` (`src/sync/remediate/nodes.py:594-638`,
return at `:636`; the no-corpus-row property is stated at `:611-616`). Slice 2's Task 4(a) landed
(`ed32e22`) so the console already renders `report_reason` verbatim.

**Ruling: a forge-less graph routes `route_after_replay`'s `push_branch` decision to `report`, with
`report_reason` naming the halt.** Rejected alternative: a new `"halted"` member on
`Outcome` (`src/sync/remediate/state.py:14`). It would require changes in four places that must
agree — `Outcome`, `_FINISHED` (`queries.py:58`, filtered at `:209`), `isRunTerminal`
(`web/src/api/queries.ts:75`), and slice 2's pinned outcome tuple — to record a fact about the
harness in the product's state machine.

**The cost of the reuse, stated:** any aggregate count of `reported` runs now mixes tier -1 "no
patch warranted" with "the harness stopped this". The mitigation is the thread id: a rehearsal
passes `--run-id rehearsal-<date>`, which lands as the second colon-delimited segment of the thread
id (`src/sync/cli.py:1054-1056`), and slice 2's `runs` view model already splits on that delimiter.

### 4. A test that asserts and a run that produces data are different things, and the split is not close

This is the requirement most likely to be got wrong, so it is decided here rather than per task.

**Almost nothing new is honestly assertable.** Three reasons, each citable:

- **`oasdiff` does not converge.** CLAUDE.md's named exemption: *"oasdiff-derived `vendor_change`
  rows do not converge, because `oasdiff breaking` returns a different answer every run over
  identical bytes on both pinned versions... do not read a row count from it as a measurement."*
  A rehearsal anchored on Stripe derives its vendor changes from oasdiff (`cli.py:1048`,
  `load_catalogue` at `:114-124`). **So no assertion may be made on the number of vendor changes,
  the number of findings, or anything derived from either.**
- **The patch node is a model call.** `TerminalTier(AgentRemediator())` is unconditional
  (`cli.py:154-163`), so any rehearsal that reaches `patch` on a finding no codemod handles spends
  `xhigh` model time, and its output is not deterministic. Nothing about it can be a CI gate.
- **What *is* deterministic is already gated.** Binding precision and recall over the frozen corpus,
  at floors that were each proved able to fire (`scripts/gate_corpus.py` docstring;
  `.github/workflows/ci.yml:170-171`). Re-asserting binding from a rehearsal would be a second
  measurement of a gated axis.

**So the split is:**

| | What it is | Asserts | Costs | Cadence |
|---|---|---|---|---|
| **Rehearsal (free)** | `locate → prepare → report`, no remediator invoked | Nothing about quality. One smoke property: every selected finding reaches a terminal checkpoint. | Postgres and cached specs only | Every tick; CI-able (Task 6) |
| **Rehearsal (paid)** | the whole graph minus the remote third | Nothing. It produces data for a human to look at through the console. | One agent run per finding | On demand, `--limit 1` by default |
| **B7, the acceptance run** | the whole pipeline including the PR | The milestone's definition of done | A real PR, real CI, real tokens | Once, when the owner says |

Conflating rows one and two is how a suite stops meaning anything. The paid rehearsal is **not a
test** and must not be given a `test_` name or a pytest marker, because a thing that lives in
`tests/` and cannot fail is worse than no test (`.claude/rules/test-discipline.md`).

### 5. The console needs one thing beyond slice 2, and it is not a new view

Slice 2 delivers `/api/runs`, the runs table, and the corpus summary
(`2026-08-04-sync-m4-slice-2.md`, Tasks 1–3). Without it there is no across-everything view and a
rehearsal can only be inspected by already knowing a finding id and typing a URL. **That is a
sequencing dependency, not a duplicated task — nothing in this plan rebuilds it.**

What slice 2 does not give, and this plan adds, is one sentence and one filter: a run halted by the
harness must read as halted rather than as an unexplained `reported`. That is Task 5 and it is
hours.

The debugging affordance is already there and is not duplicated: the central error surface
(`819ce2c`) raises every non-404 API failure into a persistent counted overlay
(`web/src/lib/query-client.ts:25-30`, `web/src/components/error-surface.tsx:71`,
mounted at `web/src/layouts/app-shell.tsx:16`), while a 404 meaning "that finding is not open" stays
silent by returning `null` from `describeFailure` (`web/src/lib/describe-failure.ts:19-20`). A
rehearsal watched through the console gets that for free.

---

## Global Constraints

- `CLAUDE.md` is binding. Test-first with a proven RED; explicit `encoding="utf-8"` on every
  `read_text`/`write_text`/`open`/`subprocess.run(text=True)`, and `PYTHONIOENCODING=utf-8` in any
  child environment; comments state constraints rather than narrating edits.
- **No task in this plan may cause a `git push`, a `gh pr create`, or a remote branch deletion.**
  The enforcement is architectural decision 1 and it is tested in Task 4.
- **The API stays read-only.** Nothing here adds a route that triggers a run. The behavioural
  read-only test (`tests/test_api_routes.py:313-396`) continues to cover every route.
- **`src/sync/mcp/tools.py` is frozen.** Nothing here touches it. `sync.mcp.propose` is read as a
  precedent and not imported — the rehearsal must not put `sync.mcp` on its import graph.
- **No assertion downstream of `oasdiff`.** Architectural decision 4.
- **`.claude/rules/interface-originality.md` binds Task 5.** The one console change is a sentence
  and a label, both written from Sync's own vocabulary.
- **Grain, everywhere.** One `migration_outcome` row is one attempt; one checkpoint thread is one
  run, not one finding. A rehearsal re-run against the same fixture head produces a *new generation*
  of the same thread base (`cli.py:1054-1056`, `_thread_to_invoke` at `:340-368`), which is a
  feature: it gives slice 2's grain test its first real multi-generation case.
- **Nothing in `.cache/` is committed.** It is gitignored and the fixture is derived from a manifest,
  not checked in.

---

## What the data can and cannot answer

### Answerable once the rehearsal runs

- **The real shape of a checkpoint mid-run**, which no session has ever seen. `task-4-report.md:325-334`
  names three fields whose real values are unknown: `replay_evidence`, `attempt_strategy`,
  `attempt_ci_result`. The first rehearsal answers all three or proves the console renders them
  wrongly. This is the single highest-value output of the whole slice.
- **Whether the console's node sequence matches the graph that ships.** `WORKFLOW_NODES`
  (`queries.py:37-40`) is hand-mirrored from `sync.remediate.graph` rather than imported (`:34-36`),
  and B7 records that the graph now has **ten** nodes where an earlier reading said eight
  (`BACKLOG.md:139-142`).
- **Whether a real `abandon_reason` renders.** Every abandon reason the console has displayed was
  typed by a human.

### Not answerable, and the screen must not pretend

- **Anything the corpus table would show about an early failure.** `_record` returns `False` when
  `static_attempts < 1` (`src/sync/remediate/corpus.py:260`), so a run abandoned at `locate` or
  `prepare` writes no `migration_outcome` row, and `make_report` never calls `record` at all
  (`nodes.py:611-616`). **The free rehearsal terminates at `report`, so it writes zero corpus rows
  by construction.** A corpus summary populated from rehearsals would be empty and must say why.
- **Cost per run.** Same table, same gap.
- **Liveness.** No heartbeat exists; slice 2's decision 4 stands unchanged.
- **Could not verify:** what `_repo_id` (`cli.py:255-277`) returns for a local filesystem path. It
  strips a scheme, a port and a userinfo, then partitions on the first `/` — a Windows path is not a
  shape it was written for, and `repo_id` is hashed into every `call_site` id. **Task 1 must
  determine this empirically and pin it**, because two rehearsals that disagree about `repo_id`
  write two disjoint graphs.
- **Could not verify:** which `VendorChange` kinds the `v2320..v2330` Stripe window actually
  produces against `furever`, and therefore how many findings route to a codemod versus the agent.
  That number decides what the paid rehearsal costs. Task 3 measures it and records it; it is not
  guessed here.
- **Could not verify:** nothing in this worktree was executed. No database was queried, no run
  performed. Every claim above is read from source.

---

## File Structure

```
src/sync/rehearse/
  __init__.py
  fixture.py          new — materialise the fixture as a local git repository
  driver.py           new — compose the shipped graph with no forge, run it, report
src/sync/cli.py       one new subparser: `sync rehearse`
src/sync/remediate/graph.py   Task 2 — HANDED OVER, forge=None
tests/test_rehearse_fixture.py     new
tests/test_rehearse_boundary.py    new — the four safety layers
.importlinter                      new contract — sync.rehearse must not import sync.forge
scripts/rehearse_smoke.py          new — Task 6, the one CI-able claim
scripts/watch_own_deprecations.py  new — Task 7
web/src/features/fleet/runs-table.tsx   Task 5 — depends on slice 2 Task 3
docs/superpowers/loops/console-improvement-tick.md   Task 5 — step 4 becomes real
```

`sync.rehearse` is named for what it does — perform the whole thing with the remote absent — rather
than for the practice. A package called `sync.dogfood` would name a habit, and the next reader would
not know from the name that it must never push.

---

## Who owns what

`docs/superpowers/ORCHESTRATION.md:117-120` puts `web/` with the console lead and `src/`, `tests/`
with the second terminal. This plan crosses that line, so the split is stated per task rather than
assumed:

| Task | Paths | Owner |
|---|---|---|
| 1 Fixture | `src/sync/rehearse/fixture.py`, `tests/` | Second terminal |
| 2 Forge-less graph | `src/sync/remediate/graph.py` | **Second terminal — the other agent's half** |
| 3 Driver and CLI | `src/sync/rehearse/driver.py`, `src/sync/cli.py` | Second terminal |
| 4 Boundary tests | `tests/`, `.importlinter` | Second terminal |
| 5 Halted reads as halted | `web/`, `docs/superpowers/loops/` | Console lead |
| 6 CI smoke | `scripts/`, `.github/workflows/ci.yml` | Second terminal |
| 7 Own-deprecation watch | `scripts/` | Either |

**Tasks depending on the other agent's half: Task 2 outright (it is theirs), and Tasks 3, 4, 5 and 6
transitively — none of them can be finished until a forge-less graph exists.** Task 1 and Task 7 are
independent and can start today.

---

### Task 1: A fixture that is a git repository and has no remote

**Files:** Create `src/sync/rehearse/fixture.py`, `tests/test_rehearse_fixture.py`.

`scripts/fetch_corpus_repositories.py` materialises `furever` into `.cache/corpus/furever` verbatim
**minus `.git`** (`benchmark/corpus/repositories.yaml` header; `materialise` at
`fetch_corpus_repositories.py:103-121`). `cli.run` clones its target
(`cli.py:280-286`, `_clone` calls `git clone --depth 50`), so the fixture must be a git repository
before a run can reach it.

```python
def prepare_fixture(name: str = "furever", *, root: Path = Path(".cache/rehearse")) -> RepoRef
```

- [ ] **Step 1:** Failing tests. Required properties, each a way this can be wrong:
  - The fixture is a git repository with exactly one commit and **zero remotes** — assert
    `git remote -v` is empty output, not that it lacks a particular name.
  - Re-running `prepare_fixture` converges: same `head_sha`, same `repo_id`, no second commit.
    Idempotence is CLAUDE.md's pipeline rule and the fixture is a pipeline input.
  - The tree digest matches `repositories.yaml` before the `git init`, so the fixture is provably
    the pinned corpus tree and not a drifted copy.
  - `repo_id` is a stable, non-empty string that contains no filesystem drive letter and no
    backslash. **Pin the actual value in the test after measuring it** — do not assert a guess;
    `_repo_id`'s behaviour on a local path is the open question named above.
  - The commit is authored with an explicit name and email passed via `-c`, the way
    `GitHubForge.push_branch` does (`github.py:190-194`), so the fixture does not depend on the
    developer's global git config.
  - A missing `.cache/corpus/furever` raises naming the fetch script rather than producing an empty
    repository. An empty fixture would index cleanly and report a clean scan — the exact failure
    `select_language_adapter`'s docstring argues against (`cli.py:226-228`).
- [ ] **Step 2:** RED for the right reasons.
- [ ] **Step 3:** Implement. `subprocess.run` with `encoding="utf-8"`, `text=True`, and
  `PYTHONIOENCODING=utf-8` in the child environment — `tests/test_e2e_stripe.py:16-29` carries the
  full argument for why the last one is not optional.
- [ ] **Step 4:** Gates: `uv run pytest tests/test_rehearse_fixture.py`, `uv run lint-imports`,
  `uv run python scripts/lint_encoding.py src scripts tests`.
- [ ] **Step 5:** Commit.

**Verification a reviewer can run:** `uv run pytest tests/test_rehearse_fixture.py -q`, then
`git -C .cache/rehearse/furever remote -v` and confirm it prints nothing. Then add a remote by hand
and watch the no-remote test go red. **A safety assertion that has never failed has not been shown
to assert anything.**

**Cost: hours.**

---

### Task 2: `build_graph` accepts no forge, and then has no node that can push

**Files:** Modify `src/sync/remediate/graph.py`, `tests/test_remediation_graph.py`.

**This task belongs to the session that owns `src/sync/remediate/`. It is the dependency every other
task sits behind.** It is written here as the property required, not as an instruction — the owning
session decides the implementation.

Required property: `build_graph(store, adapter, remediator, forge=None, checkpointer, catalogue)`
must, when `forge is None`, **not add the `push_branch`, `await_ci` or `open_pr` nodes** (today added
at `graph.py:38-40`) and must construct `abandon` without a forge (today `graph.py:42`;
`make_abandon` deletes a branch at `nodes.py:661` only when `state["branch"]` is set, which it can
never be with no push node). `route_after_replay`'s `"push_branch"` destination
(`nodes.py:489`, wired at `graph.py:78-82`) maps to `report` instead, and `route_after_static`'s
`"push_branch"` continues to map to `replay` unchanged (`graph.py:69-73`).

Why this shape rather than `interrupt_before=["push_branch"]`: an interrupt leaves the run
resumable and the node present, so a later caller with a forge in hand resumes it straight into a
push. Absence is not resumable.

- [ ] **Step 1:** Failing test: a graph built with `forge=None` reports `push_branch`, `await_ci`
  and `open_pr` **absent from `get_graph().nodes`**, and a run over a finding that would have pushed
  ends `outcome == "reported"` with a `report_reason` naming the halt.
- [ ] **Step 2:** Failing test: a graph built with a forge is byte-for-byte the graph that ships —
  same ten nodes, same edges. This task must not narrow what a real run does.
- [ ] **Step 3:** RED, implement, green.
- [ ] **Step 4:** Full suite. `build_graph` is on the acceptance path (`BACKLOG.md:127-155`) and this
  is the one file where a regression costs B7.
- [ ] **Step 5:** Commit.

**Verification a reviewer can run:** build a forge-less graph in a REPL and print
`graph.get_graph().nodes`; confirm the three names are absent. Then pass a `StubForge` and confirm
all ten return. **Fallback if this task is declined:** `sync.rehearse.driver` composes the node
factories linearly the way `sync.mcp.propose` does (`propose.py:71-107`) and writes checkpoints
through `PostgresSaver` itself. The cost is a second assembly of routing logic that will drift from
the graph it claims to rehearse — which `propose.py:9-12` argues against by name, and which would
make the rehearsal's own output untrustworthy. **Take the fallback only if Task 2 is refused, and
record the ruling in the ledger.**

**Cost: hours for the graph change; the risk is in the regression surface, not the diff.**
**Depends on: nothing. Blocks: 3, 4, 5, 6.**

---

### Task 3: One command that runs the pipeline against the fixture and stops

**Files:** Create `src/sync/rehearse/driver.py`. Modify `src/sync/cli.py`,
`tests/test_rehearse_driver.py`.

This is the deliverable that ends hand-inserted checkpoint rows.

```
sync rehearse --depth prepare|full [--limit N] [--vendor stripe]
              [--from-version v2320] [--to-version v2330] [--dsn ...]
```

`--depth prepare` is the free rehearsal: the remediator is never invoked, so no model call happens
and no `migration_outcome` row is written. `--depth full` reaches `replay` and stops. **Neither
depth can push, because neither constructs a `Forge`** — the depth argument selects how far routing
goes, and is not what makes the run safe. That distinction must be in the module docstring, because
a reader who believes `--depth` is the safety mechanism will eventually add `--depth push`.

- [ ] **Step 1:** Failing tests, with a stub store and a stub adapter — no Postgres, no network, no
  model:
  - `run_rehearsal`'s signature accepts **no** parameter named `forge` and none annotated `Forge`,
    asserted by `inspect.signature`. This mirrors `tests/test_mcp_propose_patch.py:234`.
  - `--depth prepare` invokes the remediator zero times.
  - `--run-id` defaults to `rehearsal-<ISO date>`, and the resulting thread base is
    `{finding_id}:rehearsal-...` so a rehearsal is separable from a real run by thread id
    (`cli.py:1054-1056`).
  - A rehearsal over a fixture with zero findings exits 0 and prints that it found none —
    distinguishable from a failure, which is the confusion `_scan`'s per-detector counts exist to
    end (`cli.py:852-887`).
- [ ] **Step 2:** RED, implement.
- [ ] **Step 3:** Reuse `cli.py`'s existing assembly rather than restating it: `prepare_vendor`,
  `select_language_adapter`, `_detector_suite`, `_scan`, `build_remediator`, `load_catalogue`. A
  second copy of detector wiring is how a detector ends up running in one path and not the other —
  `_detector_suite`'s docstring records that exact failure (`cli.py:806-824`).
- [ ] **Step 4:** Run it for real. `docker compose up -d` (Postgres on **5433**), then
  `uv run python -m sync.cli rehearse --depth prepare`. **Record in the report:** how many findings,
  which detectors produced them, how many threads were written, and the actual values of
  `attempt_strategy`, `replay_evidence` and `attempt_ci_result` where present. Those three are the
  open questions from `task-4-report.md:325-334` and answering them is this task's real output.
- [ ] **Step 5:** Then `--depth full --limit 1` once, and record what it cost and how many findings
  reached the agent tier versus a codemod. That number is the input to any future decision about
  cadence and it does not exist today.
- [ ] **Step 6:** Full gates; commit.

**Verification a reviewer can run:** `uv run python -m sync.cli rehearse --depth prepare`, then
`psql` the checkpointer and confirm one thread per selected finding, each newest checkpoint carrying
`outcome = "reported"`. Then run it a second time and confirm generation `:1` threads appear beside
`:0` rather than the first run being overwritten.

**Cost: days. This is the largest task in the plan and the one that pays for the rest.**
**Depends on: Task 1, Task 2.**

---

### Task 4: The boundary, made structural and proved able to fail

**Files:** Create `tests/test_rehearse_boundary.py`. Modify `.importlinter`.

Four independent layers. Any one of them alone is a promise; four is a boundary.

1. **No push node exists.** Asserted on `get_graph().nodes` of the graph the driver builds.
2. **The driver takes no forge.** `inspect.signature`, per Task 3 Step 1.
3. **`sync.rehearse` cannot import `sync.forge`.** A `forbidden` contract in `.importlinter`,
   enforced by `uv run lint-imports`, which already runs in CI (`.github/workflows/ci.yml:73-74`)
   and is already the mechanism behind `sync.core`'s non-negotiable boundary.
4. **The fixture has no remote.** Task 1's assertion, re-run as part of this suite.

- [ ] **Step 1:** Write all four.
- [ ] **Step 2: break each one deliberately and watch it go red, then restore.** Add `push_branch`
  back to the forge-less graph. Add a `forge` parameter to the driver. Add
  `from sync.forge.github import GitHubForge` to `sync/rehearse/driver.py`. Add a remote to the
  fixture. **Record all four RED outputs in the task report.** `.claude/rules/test-discipline.md`
  requires this for anything asserting on an external tool, and every layer here does.
- [ ] **Step 3:** A paragraph in `.claude/rules/remediate-stage.md` under *Nothing reaches a pull
  request unverified*, stating that a forge-less graph is the supported way to run the pipeline
  without a remote and that adding a push node back to it is a change to a safety property.
- [ ] **Step 4:** Commit.

**Verification a reviewer can run:** the four break-and-restore cycles above, from the report's
recorded commands.

**Cost: hours. Do not cut this one; it is the plan's single most important safety property.**
**Depends on: Tasks 2, 3.**

---

### Task 5: A halted run reads as halted, and the tick's verification step becomes real

**Files:** Modify `web/src/features/fleet/runs-table.tsx` (slice 2, Task 3),
`web/src/features/workflows/run-outcome.tsx`,
`docs/superpowers/loops/console-improvement-tick.md`.

Two small things, both console-side.

**(a) A rehearsal is labelled as one.** A run whose thread id's second segment begins `rehearsal-`
is a rehearsal, and the runs table says so in a column rather than leaving the reader to infer it
from a reason string. This needs the thread id's run segment in the payload; if slice 2's `runs`
view model does not already carry it, that is one field on a view model this plan may change — not
a frozen surface. **Check before building.**

**(b) The improvement tick stops verifying against an empty database.**
`docs/superpowers/loops/console-improvement-tick.md` step 4 currently says *run the API and look*.
Replace the setup block with `sync rehearse --depth prepare` before `npm run dev`, so every tick
looks at real data. This is the change that turns the existing loop from an improvement loop into a
loop that also observes the pipeline.

`.claude/rules/interface-originality.md` binds: the column label and the sentence come from Sync's
own vocabulary — "rehearsal", "halted before the remote" — and from nowhere else.

- [ ] **Step 1:** Confirm slice 2's runs payload carries the run segment; if not, add it to the view
  model with a test.
- [ ] **Step 2:** The column and the sentence. `npm run build` clean, `npm run lint` with no new
  error-level violations.
- [ ] **Step 3:** The tick edit.
- [ ] **Step 4:** Drive it: `sync rehearse --depth prepare`, then the API and `npm run dev`, and look
  at the fleet screen. Record what was seen — a screenshot description, the row count, and whether
  the halted runs are distinguishable at a glance.
- [ ] **Step 5:** Commit.

**Verification a reviewer can run:** run a rehearsal, load `/`, and confirm the rehearsal rows are
labelled and terminal. Then load a hand-inserted `reported` row from a non-rehearsal thread and
confirm it is *not* labelled — the label must discriminate, not decorate.

**Cost: hours.**
**Depends on: slice 2 Tasks 1–3, and Task 3 of this plan.**

---

### Task 6: The one claim CI can honestly assert

**Files:** Create `scripts/rehearse_smoke.py`, `tests/test_rehearse_smoke.py`. Modify
`.github/workflows/ci.yml`.

Architectural decision 4 rules out asserting anything downstream of `oasdiff`, which is nearly
everything a rehearsal produces. What remains is a smoke property, and it should be stated as
narrowly as it is true:

**"A `--depth prepare` rehearsal against the fixture completes, and every finding it selected
reached a terminal checkpoint."** Not a count, not a quality figure. It catches the failure that has
actually happened on this project — a pipeline that stopped composing after a change landed
underneath it, which is B7's entire premise (`BACKLOG.md:129-136`).

- [ ] **Step 1:** Failing test: the smoke script exits non-zero when a thread's newest checkpoint
  carries no terminal outcome, and zero when every one does.
- [ ] **Step 2:** Implement, reading `checkpoints` the way `queries.py:185-197` does, including the
  `to_regclass` guard at `:185` so an unmigrated database is an honest skip rather than a crash.
- [ ] **Step 3:** Wire into CI as its own job with the Postgres service, beside the corpus job. It
  needs `fetch_corpus_repositories.py` and the pinned specifications, which the corpus job already
  stages (`.github/workflows/ci.yml:132-153`) — reuse those steps rather than writing a second
  staging path.
- [ ] **Step 4:** Break it: point the smoke run at a thread with `push_branch` pending, watch it exit
  non-zero. **A gate that has never rejected anything has not been shown to gate.**

**Verification a reviewer can run:** `uv run python scripts/rehearse_smoke.py` after a rehearsal;
then delete the terminal checkpoint row and watch it fail.

**Cost: half a day. Rank this last and cut it first.** Its assertion is genuinely thin, and if CI
turns out to need network access to stage the fixture it is not worth the runner minutes. The value
is in Task 3, not here.

---

### Task 7: Sync's own signal stage, watching Sync's own vendor

**Files:** Create `scripts/watch_own_deprecations.py`.

The one honest form of "Sync watches the APIs Sync depends on". `CLAUDE.md` mandates
`model="claude-opus-5"` at every call site, `pyproject.toml:25` pins `claude-agent-sdk`, and
`ANTHROPIC` is a shipped deprecation source whose adapter already fetches, caches and parses that
vendor's page (`src/sync/signals/deprecations/adapter.py:62-70`, used through
`model_deprecation_sources()` at `:127`).

The script reads the model ids this repository actually mandates — parsed out of `CLAUDE.md` and any
`src/` literal, not restated in the script — and reports whether any vendor's own page lists one as
retired, with the date.

**This is a run that produces data, not a test.** It reaches a vendor's network endpoint, which
`.claude/rules/test-discipline.md` forbids in the suite outright, so it is a script invoked
deliberately and never a pytest test. It is also the cheapest genuinely-dogfooding thing in this
plan: it uses our signal stage, against our dependency, to protect our own build.

- [ ] **Step 1:** Write it. Reuse `DeprecationAdapter` whole; construct nothing that parses a vendor
  page here.
- [ ] **Step 2:** Prove it can report something: run it against a locally-modified cached page that
  lists a model this repository names, and confirm it says so. Then restore.
- [ ] **Step 3:** A line in the improvement tick pointing at it, so it is run occasionally rather
  than never.

**Verification a reviewer can run:** `uv run python scripts/watch_own_deprecations.py` and read the
output; then edit the cached page under `.cache/specs/anthropic-deprecations.md` to retire
`claude-opus-5` and confirm the script says so.

**Cost: hours. Independent of every other task — it can be done first, and it is the only thing here
that would have told us something on the day it landed.**

---

## What dogfooding will not catch

This section exists because a green rehearsal is exactly the kind of result that gets over-read.

**The most important thing, first: the rehearsal stops before `push_branch`, so it never exercises
the third of the pipeline B7 exists to exercise.** B7 lists eight changes that landed on the
acceptance path since it last ran — the push guard over the discarded-commit range, branch deletion
on abandonment, checkpoint serialiser registration, the dependency-edit guard, staged-new-file
support, dependency-tree discarding, the tier cascade and the property-omit codemod
(`BACKLOG.md:129-136`). Several of those live in `push_branch`, `await_ci` and `open_pr`, which a
forge-less graph does not contain. **A green rehearsal reduces the need for B7 by nothing at all,
and reading it as partial credit is the mistake this paragraph exists to prevent.** The safety
property that makes the loop acceptable is the same property that makes it incomplete.

The rest:

- **One repository, one vendor, one language, one version window.** `furever` is TypeScript and
  Stripe at `v2320..v2330`. It says nothing about Twilio, nothing about the Python adapter's path,
  nothing about a repository whose manifest is shaped differently. `.claude/rules/test-discipline.md`
  names this class directly, and the corpus exists precisely because one repository is not evidence.
- **No encoding defect will surface.** Every fixture in this repository is ASCII and the corpus
  scorer already skips what it cannot decode. The lint is what catches these
  (`scripts/lint_encoding.py`), not any run.
- **No quality axis moves.** Merge rate, routing accuracy and cost per merged patch have never had a
  sample (`BACKLOG.md:115-117`), and a rehearsal that never opens a PR cannot give them one.
- **The corpus stays empty.** The free rehearsal writes zero `migration_outcome` rows by
  construction (`corpus.py:260`, `nodes.py:611-616`).
- **A wrong finding still looks like a right one.** The rehearsal proves the pipeline *ran*. Whether
  what it produced is correct is the corpus gate's question, and that gate covers binding only.
- **`oasdiff` non-convergence means a rehearsal's finding count differs run to run over identical
  bytes.** A reader who watches the number move and concludes something changed will be wrong, and
  the console must not invite that reading.

---

## Deferred, deliberately

| Deferred | Condition that retires it |
|---|---|
| A scheduled rehearsal | Two things: a rehearsal that costs no model tokens *and* a scheduler that outlives a session. `ORCHESTRATION.md:30-33` records that ticks die with the session that scheduled them, so "automatic" today means "a live session's tick" or "a CI job". Task 6 is the CI half; the schedule is not buildable. |
| Triggering a rehearsal from the console | The API is read-only and a trigger route is a spend and a subprocess behind an unauthenticated HTTP surface bound to 127.0.0.1 (`src/sync/api/__main__.py:35-36`). It needs its own authorization design. Proposing it here would be proposing a security hole. |
| Rehearsing every corpus repository, not just `furever` | The first rehearsal has produced a report. Five repositories is five times the runtime and the same one question until the first one is answered. |
| Sync indexing Sync's own tree | Two named blockers: the literal pass walks `*.ts` only (`cli.py:732`), and a run must anchor on a registry vendor the manifest declares (`cli.py:216-248`). The second is an architecture decision, not a task. |
| A frontend test runner | Unchanged from slice 2. Nothing here adds console logic that needs one. |

## What I am not proposing, and what decided it

- **Any automatic pull request.** Not deferred — ruled out. The rehearsal has no push node.
- **Reviving `tests/test_e2e_stripe.py` under a different marker, or unmarking it.** It opens a real
  PR (`tests/test_e2e_stripe.py:38-67`) and it is the owner's call by name
  (`BACKLOG.md:150-152`). Nothing here touches that file.
- **A new `Outcome` member.** Architectural decision 3, with the four-place agreement cost stated.
- **A `--dry-run` flag on `sync run`.** A flag on the command that *does* push is one edit away from
  not being checked. The rehearsal is a different command building a different graph.
- **Changing `src/sync/mcp/tools.py`.** Frozen. Nothing in this plan needs it.
- **A second checkpoint writer.** Only via `PostgresSaver`, through `build_graph`. The alternative is
  a private reimplementation of a table shape langgraph owns.
- **Asserting a finding count anywhere.** CLAUDE.md's oasdiff exemption forbids it and this plan
  treats that as binding rather than as advice.

## Questions only the owner can settle

1. **Task 2 is in the other session's paths — will they take it, and when?** Everything except Tasks
   1 and 7 sits behind it. *Recommendation: hand it over as a written property (this document's
   Task 2) rather than as a patch, and start Tasks 1 and 7 meanwhile.*
2. **Does `--depth full` run at all before B7 runs?** It spends real model time on a fixture and
   produces no pull request. *Recommendation: run it exactly once, to answer the three unknown
   checkpoint field shapes, and then stay on `--depth prepare` until B7 has run. One paid rehearsal
   is a measurement; a habit of them is a bill.*
3. **Is Task 6 worth its half day and its CI minutes?** Its assertion is thin by construction.
   *Recommendation: yes but last, and cut it first if the slice runs long.*
4. **B7 itself — is now the time?** Not this plan's to decide, and this plan does not advance it.
   The honest position is that a rehearsal makes B7 *cheaper to debug when it fails*, because the
   first two-thirds will already have been watched through the console — and nothing more than that.

## Verification

- Python: `uv run pytest`, `uv run lint-imports` (which now carries the `sync.rehearse` contract),
  `uv run python scripts/lint_encoding.py src scripts tests`.
- The suite needs `scripts/bootstrap_tools.sh` to have run in this worktree, or 38 tests and 9
  errors fail on an absent `oasdiff` — established as the single cause and not a regression
  (`.superpowers/sdd/2026-07-30-sync-m4-dashboard/progress.md:296-299`).
- Web: `npm run build` clean, `npm run lint` with no new error-level violations.
- **The four safety layers are each proved able to fail, with the RED output recorded** (Task 4
  Step 2). This is the verification that matters most in this plan; a slice that ships without it
  has shipped a promise.
- **The fixture is proved to have no remote**, and that assertion is proved able to fail.
- The rehearsal's own report records what was actually seen in the database and on the screen — not
  that it ran. `superpowers:verification-before-completion` applies: evidence before assertions.
