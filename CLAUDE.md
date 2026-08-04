# Sync — working conventions

Read this before writing code. It is the shared context every agent working in this repository gets; briefs and plans layer on top of it, never against it.

## What this project is

Sync watches the third-party APIs a codebase calls and opens verified pull requests when one of them breaks, drifts, or wastes money. Design: `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`.

The load-bearing idea is the **API Dependency Graph**: static call sites joined against vendor changes and runtime telemetry. Detectors query it, and all of them emit one `Finding` type into one remediation pipeline. If you are adding something that does not read from or write to that graph, question whether it belongs.

## Latency is a design constraint, not a later optimisation

`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md` is binding on pipeline design. Read it before changing the shape of any pipeline, adding an agent, or introducing a stage.

The rule it exists to enforce: **every agent must shorten the critical path or improve a result. An agent that does neither is latency and cost with extra steps.**

One consequence binds everywhere, because breaking it fails silently: any state key written by parallel branches **must** declare a reducer. Without one, concurrent writes are dropped — no error, no warning, missing results.

Two more, both scoped to the remediation pipeline and both in `.claude/rules/remediate-stage.md`: the critical path is dominated by the customer's CI run, and `locate → patch → verify` is a data dependency rather than an ordering accident.

## This is a data pipeline, and it obeys data-pipeline rules

`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` carries the argument and names what deliberately does not apply. Two of the six rules are purely about vendor adapters — keep `VendorChange.raw`, and a signature proves origin rather than correctness — and live in `.claude/rules/signal-stage.md`. The four that bind every session:

- **Declare a table's grain as a comment in `schema.sql` before adding a column.** One `migration_outcome` row is one *attempt*, not one finding. A query that counts findings by counting rows is wrong, and wrong quietly.
- **Every stage is idempotent.** Re-running INDEX, SIGNAL, or DETECT on the same input converges on the same rows. Every table gets a natural key and an explicit conflict clause. `efcc19d` was this bug. **One named exemption:** oasdiff-derived `vendor_change` rows do not converge, because `oasdiff breaking` returns a different answer every run over identical bytes on both pinned versions. Treat that source as at-least-once and do not read a row count from it as a measurement. Nothing else is exempt — INDEX, DETECT and the rest of SIGNAL are bound as written. `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` carries what retires it.
- **Every binding carries the rung it came from** — `static`, `resolved`, or `observed` — and so does every artifact derived from it. A false positive that cannot be attributed to a rung cannot be fixed. This is enforced rather than asked for: the rung is a column, not a join, and the write refuses an unattributed finding. `.claude/rules/graph-grain.md` carries where that check sits and why.
- **Abandoned runs are data.** `abandon_reason` stays queryable; abandoned attempts are where routing learns which change kinds are not mechanically safe.

## Non-negotiables

**`sync.core` imports nothing from any sibling package.** Not `sync.graph`, not `sync.signals`, not anything. A third party writing a vendor adapter depends on `sync.core` alone; a single sibling import drags Postgres into their dependency tree. `tests/test_import_boundary.py` enforces this and it is not advisory.

**Nothing reaches a pull request unverified.** Every patch passes `tsc` and then the customer's own CI. If you find yourself adding a path that skips the gate, you have found a bug in your approach, not a shortcut.

Two honest qualifications on that, both measured rather than theorised:

- **`tsc` verifies the tree a push would carry.** `static_verify` holds every untracked and every ignored path out of the clone before it compiles, so the verdict describes the branch `push_branch` creates and not whatever the agent left behind — `sync.index.shipped_tree` carries why that is done in place rather than against a second checkout. Installed dependencies are kept, because the customer's CI installs its own; an edit inside one would satisfy a gate their CI will not, so `sync.index.dependency_edits` compares mtimes against the install and fails the verification naming the path, before the compiler runs. A file the patch creates ships only if the agent staged it: `git add -u` refreshes what the index already holds and never reads the working tree for a path the index does not know, so a staged addition is carried and an unstaged one is held out and fails the gate. That staging is the agent asserting the patch needs the file, and it is deliberately the only such route — nothing here can separate a module a fix requires from a byproduct sitting beside it, and a rule keyed on names or extensions would be wrong on somebody's repository and wrong silently.
- **"We never execute customer code" is the intent, not yet the invariant.** `run_tsc` prefers the clone's own `node_modules/.bin/tsc`, resolved through the customer's `.npmrc`, and the patch agent holds `Bash` inside the clone. Dependency installs pass `--ignore-scripts`, so no lifecycle script runs, and Sync never runs the customer's application — but it does execute their toolchain. Say that, rather than the stronger sentence.

We never hold customer secrets. That one is unqualified.

**Vendor-specific knowledge lives in adapters, never in core.** Stripe's URL conventions, its `operationId` scheme, its SDK naming — all of it belongs to `sync.signals.stripe`. The moment core knows a vendor's name, the plugin story is dead.

## Toolchain

| | |
|---|---|
| Python | 3.12. The interpreter is `python`. **Never `python3`** — that is a Microsoft Store shim on this machine and it will not run. |
| Packages | `uv` only (`uv add`, `uv run`). Poetry is not installed; do not introduce it. |
| Database | Postgres 16 in Docker on **port 5433**, not 5432. `docker compose up -d`. |
| TypeScript | via `npx`; the repo does not vendor a compiler. |
| Package managers | Sync installs a customer project's dependencies before typechecking, using whichever manager that project's lockfile names. **That manager must be on `PATH` or the run abandons** — `deps.py` deliberately refuses to substitute one for another, because a different manager resolves a different tree. `npm` and `pnpm` are present here; `yarn` is not, and `corepack enable` needs administrator rights on this machine. The shims are installed unelevated instead: `corepack enable --install-directory "$(pwd)/tools/shims"`, with `tools/shims` prepended to `PATH` for the run. `tools/` is gitignored. `shutil.which` resolves the `.CMD` form, which is the one Windows can execute. |
| GitHub | the `gh` CLI, already authenticated. |
| Shell | command snippets are POSIX, written for Git Bash. PowerShell 5.1 here has no `&&` — chain with `; if ($?) { }`. |

Git warns `LF will be replaced by CRLF` on every commit. That is expected. Do not add a `.gitattributes` or rewrite line endings to silence it.

**Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, **and `subprocess.run(..., text=True)`**. On Windows all of these default to the locale codepage — cp1252 here — so any non-ASCII byte corrupts or raises, and only on this platform. Every fixture in this repository is ASCII, which means **no test will ever catch it**; it fails first against real vendor data or a real customer repository. When handling bytes that are not text, use `read_bytes`/`write_bytes` and do not decode at all.

`subprocess` is the easy one to forget, and it fails worse than the others. A decode error there is raised on the reader thread and never propagates: the call returns with `stdout` set to `None`, and the next line that concatenates it raises `TypeError` somewhere unrelated. Task 6 shipped exactly this — one accented identifier anywhere in a typechecked project crashed the verification gate instead of failing it. Task 4 hit the plain `read_text` form twice.

**`encoding="utf-8"` on the call is not enough when the child chooses its own encoding.** It says how to decode the bytes, not which bytes arrive. Run a Python child on this machine and it emits cp1252, so `subprocess.run(..., text=True, encoding="utf-8")` still raises `UnicodeDecodeError` on the reader thread the moment the child prints a non-ASCII byte — an em dash in a source line pytest echoes back is enough. Set `PYTHONIOENCODING=utf-8` in the child's environment as well, and pass `errors="replace"` where the output is diagnostic rather than data. Measured while mutation-testing two modules whose docstrings carry em dashes: the run returned exit 1 with no output at all, which a harness reads as either a survival or a kill depending on how it counts, and neither is true.

## How we work

**Test first, always.** Write the failing test, run it, watch it fail for the reason you expect, then implement. A test that has never failed has never been shown to test anything.

**Executing a plan, decide rather than ask.** `.claude/rules/autonomous-development.md` carries the rule and the three exceptions that are still the human's. It exists because one blocking question idled a milestone for three hours; a ruling recorded in the plan's ledger costs a fix round to reverse, and waiting costs the afternoon.

**A test that cannot fail is worse than no test.** It reports a component as covered while asserting nothing, and nothing downstream ever contradicts it — the import-boundary test's original form exited 0 without parsing its own argument. When a test asserts on a subprocess, an exit code, or an external tool, break the thing deliberately and watch it go red before trusting it.

The rest of the test discipline is in `.claude/rules/test-discipline.md`, which loads whenever you touch `tests/`: the no-vendor-API and no-model-API rule, why fixtures being ASCII means no test catches a missing `encoding="utf-8"`, and focused-while-iterating then full-before-committing.

**Never detect a write by comparing against a live mtime.** Filesystems record modification times
far more coarsely than the clock, so a write that changes no bytes usually leaves `st_mtime_ns`
untouched — measured here at 184 of 200 identical-byte rewrites. A check written that way fires
only when the write happens to land across a tick boundary, which reads as a flaky test and is
actually a detector that mostly does not detect. Either backdate the baseline before the operation,
so any write moves the timestamp forward from a value no write could have produced, or make the
content differ.

This rule is here rather than in a docstring because a docstring did not stop it. The same defect
shipped twice in one day — once in `sync.index.dependency_edits.mark_installed`, then hours later
in the adapter conformance check — by the same person, who had written the explanation the first
time.

## Model configuration

Always `claude-opus-5`, always adaptive thinking, always `xhigh` effort. **The two surfaces spell that differently, and they are not interchangeable.**

Messages API — nested, and takes a token ceiling:

```python
model="claude-opus-5"
thinking={"type": "adaptive"}
output_config={"effort": "xhigh"}
max_tokens=64000
```

Claude Agent SDK (`ClaudeAgentOptions`) — flat, and has **no** `output_config` and **no** `max_tokens`:

```python
ClaudeAgentOptions(
    cwd=...,
    model="claude-opus-5",
    thinking={"type": "adaptive"},
    effort="xhigh",
    allowed_tools=[...],
    disallowed_tools=["WebSearch", "WebFetch"],
)
```

Verified against the installed package: `ClaudeAgentOptions` exposes `cwd`, `model`, `thinking`, `effort`, `allowed_tools`, `disallowed_tools`, and `permission_mode`. Passing the Messages-API shape to it does not work, and this document previously said otherwise.

Restricting a tool means listing it in `disallowed_tools`. Merely leaving it out of `allowed_tools` is not a block — with no `can_use_tool` callback registered, an out-of-list call has no resolution path in headless mode, which inside an unattended pipeline is a hang rather than a refusal.

`temperature`, `top_p`, and `budget_tokens` return HTTP 400 on this model on either surface. Steer with prompting instead. Thinking is on by default, and on the Messages API `max_tokens` caps thinking plus output together, which is why that ceiling is generous.

## Code style

Comment to state a constraint the code cannot show — never to narrate what the next line does, where something came from, or why a change is correct. That last one is talking to a reviewer, and it becomes noise the moment the pull request merges.

Prefer small, focused modules over large ones. A file that has grown past one clear responsibility is a signal, not a style preference.

Do not add error handling, fallbacks, or validation for conditions that cannot occur. Validate at system boundaries — user input, vendor responses, subprocess output — and trust internal code.

## Commits

Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Write the body in normal prose explaining why, not what — the diff already says what.
