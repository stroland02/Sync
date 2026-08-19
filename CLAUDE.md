# Sync — working conventions

Read this before writing code. It is what every agent in this repository gets; briefs and plans
layer on top, never against it.

**Rewritten 2026-08-19.** The previous version is on `backup/pre-claudemd-rewrite-2026-08-19`. It
was 318 lines of mostly prose and it was slowing the work down measurably — 42% of the Python in
this repository is comments, 25% of the console, because it asked for an argument in the file
rather than a check in the pipeline. This version keeps every fact that has cost real time to
learn and drops the ceremony around them.

## The governing principle

**Encode a rule where it fails, not where it is read.**

A rule in prose is enforced by whoever remembers it. A rule in a test, a type, a lint or a schema
constraint is enforced always. Every convention below that could become a check has become one,
and anything new should arrive the same way.

This is not a style preference — it is measured. The conventions that held in this repository are
the ones a machine enforced: `tests/test_import_boundary.py`, the required `bindingNullLabel` prop,
`insert_finding` refusing an unattributed rung, `scripts/lint_encoding.py`. The conventions that
quietly decayed were prose in files somebody later deleted — seven of the twenty-four "protected"
console sentences cited files that no longer exist, and nothing noticed for two weeks.

So: **if you find yourself writing a paragraph asking the next agent to remember something, write
the check instead.** If a check is genuinely impossible, one sentence, and move on.

## What this project is

Sync watches the third-party APIs a codebase calls and opens verified pull requests when one
breaks, drifts, or wastes money.

**The binding is the product** (`specs/2026-07-25-sync-positioning-and-open-core.md`, Decision 1).
The API Dependency Graph — static call sites joined against vendor changes and runtime telemetry —
is what customers pay for. Repair is a feature that proves the binding was right, not the spine.
Detectors query the graph and all emit one `Finding` into one remediation pipeline. If you are
building something that neither reads from nor writes to that graph, question whether it belongs.

Design: `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`.

## Non-negotiables

These four are enforced by tests. Breaking one fails the build, not a review.

- **`sync.core` imports nothing from any sibling package.** A third party writing a vendor adapter
  depends on `sync.core` alone; one sibling import drags Postgres into their tree.
  `tests/test_import_boundary.py`.
- **Nothing reaches a pull request unverified.** Every patch passes `tsc`, then the customer's CI.
  A path that skips the gate is a bug in your approach.
- **Vendor-specific knowledge lives in adapters, never in core.** The moment core knows a vendor's
  name, the plugin story is dead.
- **We never hold customer secrets.** Unqualified.

Two honest qualifications on verification, both measured:

- **`tsc` verifies the tree a push would carry.** `static_verify` holds untracked and ignored paths
  out of the clone before compiling. Installed dependencies stay, because the customer's CI
  installs its own — `sync.index.dependency_edits` compares mtimes against the install and fails
  the gate naming the path. A file the patch creates ships only if the agent staged it.
- **"We never execute customer code" is the intent, not the invariant.** `run_tsc` prefers the
  clone's own `node_modules/.bin/tsc`. Installs pass `--ignore-scripts`, so no lifecycle script
  runs, and Sync never runs the customer's application — but it does run their toolchain. Say that,
  not the stronger sentence.

## Pipeline rules

`specs/2026-07-27-sync-pipeline-discipline.md` carries the argument. Four bind everywhere:

- **Declare a table's grain as a comment in `schema.sql` before adding a column.** One
  `migration_outcome` row is one *attempt*, not one finding. A query counting findings by counting
  rows is wrong, and wrong quietly.
- **Every stage is idempotent.** Re-running INDEX, SIGNAL or DETECT on one input converges. Every
  table gets a natural key and an explicit conflict clause. `efcc19d` was this bug. **One
  exemption:** oasdiff-derived `vendor_change` rows do not converge — treat that source as
  at-least-once and never read a row count from it as a measurement.
- **Every binding carries its rung** — `static`, `resolved`, `observed` — and so does every artifact
  derived from it. Enforced: the rung is a column, and `insert_finding` refuses an unattributed
  finding.
- **Abandoned runs are data.** `abandon_reason` stays queryable; abandoned attempts are where
  routing learns which change kinds are not mechanically safe.

**Latency is a design constraint** (`specs/2026-07-25-sync-latency-architecture.md`). Every agent
must shorten the critical path or improve a result. One consequence fails silently and so is
repeated here: **any state key written by parallel branches must declare a reducer**, or concurrent
writes are dropped with no error.

## The console

The product's argument is that competitors show a black box and a result and ask you to trust it.
The console shows the reasoning instead. Three things follow, and only the third is a refusal.

**Show the work.** Provenance, scope, and what was not measured are part of every answer.

**Say which nothing it is.** Absence is not zero; staleness is not liveness; never-measured is not
nothing-here. This is the rule that matters, and it survives the 2026-08-19 simplification below.

**No composite score, health figure, traffic light or liveness pulse.** Rejected three times on the
record. A scalar averaging "we could not check" with "we checked and it passed" collapses the exact
distinction the product exists to make. A *badge* is permitted — a recorded value from a closed
vocabulary, legible without its colour — and Sync already uses them for run outcome, error state and
absence. We are not stricter than a mature control plane; we have data that fails its own published
tests and we said so.

**Amended 2026-08-19, by the owner.** The console used to protect twenty-four specific sentences
from being shortened or moved into a tooltip. That rule blocked ordinary cleanup, and seven of the
sentences cited deleted files. The replacement:

> **The claim stays visible in the fewest honest words. The argument moves behind the ⓘ.**

A reader who never hovers must still be able to tell what a figure covers and whether it was
measured — "not measured yet", "all workspaces", "static evidence", "no source attached". Why that
distinction exists belongs in the hover. Rendering one nothing as another is still refused.

**A chart must be able to draw its own data.** Learned expensively: the provenance panel shipped as
a donut over a set where four of five members were measured zeros, and a donut cannot draw a zero —
it rendered as a closed ring and read as broken. Check the real payload before choosing a form.

Interface authorities: `.claude/rules/console-hierarchy.md` (levels come from the spec, not a plan),
`.claude/rules/console-surface.md` (`DESIGN.md` is the token contract),
`.claude/rules/interface-originality.md` (the interface is ours).

## Toolchain

Every line here has cost someone hours.

| | |
|---|---|
| Python | 3.12, interpreter is `python`. **Never `python3`** — Microsoft Store shim, will not run. |
| Packages | `uv` only. Poetry is not installed. |
| Database | Postgres 16 on **port 5433**. **No admin rights on this machine, so Docker and WSL2 are unavailable.** The cluster is embedded at `~/.sync-postgres`; `npm run no-admin` adopts or starts it. It does not survive a reboot (B191) — run it again, or `~\.sync-postgres\pgsql\bin\pg_ctl.exe -D ~\.sync-postgres\data -o "-p 5433" start`. |
| TypeScript | via `npx`; no vendored compiler. |
| Package managers | Sync installs a customer's dependencies with whichever manager their lockfile names, and **refuses to substitute** — a different manager resolves a different tree. `npm` and `pnpm` are here; `yarn` is not, and `corepack enable` needs admin. Unelevated: `corepack enable --install-directory "$(pwd)/tools/shims"`, prepend `tools/shims` to `PATH`. `shutil.which` resolves the `.CMD` form. |
| GitHub | `gh`, authenticated. |
| Shell | Snippets are POSIX for Git Bash. PowerShell 5.1 has no `&&` — chain with `; if ($?) { }`. |

`LF will be replaced by CRLF` on commit is expected. Do not add `.gitattributes`.

**Always pass `encoding="utf-8"`** to `read_text`, `write_text`, `open`, **and
`subprocess.run(..., text=True)`**. On Windows all default to cp1252, so any non-ASCII byte
corrupts or raises — and **every fixture here is ASCII, so no test will ever catch it.** It fails
first against real vendor data. For bytes that are not text use `read_bytes`/`write_bytes`.

`subprocess` fails worst: a decode error is raised on the reader thread and never propagates —
`stdout` comes back `None` and the next line raises `TypeError` somewhere unrelated. **Also set
`PYTHONIOENCODING=utf-8` in the child's environment**, because `encoding=` says how to decode the
bytes, not which bytes arrive; a Python child on this machine emits cp1252 regardless. Pass
`errors="replace"` where output is diagnostic. Enforced by `scripts/lint_encoding.py`.

**Never `git stash` when another worktree may be active.** `refs/stash` is one ref shared across
every worktree — measured 2026-08-16, two agents each popped the other's stash. Use `git diff` or a
scratch branch.

**Never detect a write by comparing against a live mtime.** Filesystems record mtimes far more
coarsely than the clock: 184 of 200 identical-byte rewrites left `st_mtime_ns` untouched. Backdate
the baseline first, or make the content differ.

## Model configuration

Always `claude-opus-5`, adaptive thinking, `xhigh` effort. **The two surfaces spell it differently.**

Messages API — nested, takes a ceiling:

```python
model="claude-opus-5"
thinking={"type": "adaptive"}
output_config={"effort": "xhigh"}
max_tokens=64000
```

Agent SDK (`ClaudeAgentOptions`) — flat, **no** `output_config`, **no** `max_tokens`:

```python
ClaudeAgentOptions(cwd=..., model="claude-opus-5", thinking={"type": "adaptive"},
                   effort="xhigh", allowed_tools=[...], disallowed_tools=["WebSearch", "WebFetch"])
```

Three facts about containment, checked against the installed package (`0.2.128`, 45 fields):

- **`disallowed_tools` is a real block. Omitting from `allowed_tools` is not.**
- **A `can_use_tool` callback is shadowed by a whole-tool `allowed_tools` entry** — the SDK's own
  `_get_can_use_tool_shadowed_warning` says so. Use a `PreToolUse` hook. `hooks` works with a
  one-shot prompt; `can_use_tool` requires streaming.
- **The hang is a property of the default permission mode**, not headless mode. `PermissionMode`
  includes `dontAsk`.

`sandbox` accepts network `deniedDomains` and is **macOS/Linux only**, so B97's mechanism is
unavailable here — which is why the gate that shipped is a `PreToolUse` hook.

`temperature`, `top_p` and `budget_tokens` return HTTP 400 on this model. Steer with prompting.

## How we work

**Decide rather than ask.** Executing a plan, pick what a careful engineer on this project would
pick, record the ruling in the plan's ledger, and keep going. Three exceptions stay the human's: an
irreversible action outside the repository, a decision that invalidates the plan's architecture, and
anything needing a credential or a spend. `.claude/rules/autonomous-development.md`. One blocking
question once idled a milestone for three hours.

**Test first, in both languages.** Write the failing test, run it, watch it fail *for the reason you
expect*, then implement. A test that has never failed has never been shown to test anything — and
when a test asserts on a subprocess, an exit code or an external tool, break it deliberately and
watch it go red before trusting it. The import-boundary test's original form exited 0 without
parsing its argument.

Console tests are `cd web && npm test`. Scope is deliberately narrow: **classification, derivation
and structural invariants. Never class names, never snapshots.** A snapshot in a console being
restyled fails on every correct change. Pixels are measured in Chrome and written into `DESIGN.md`.

**Ship the smallest change that is complete.** A feature is done when it works, is tested, and the
gate is green — not when its docstring explains itself to a future reader.

**A memory describing who is doing what right now is a hypothesis.** Several sessions push here
concurrently. Verify against `git log` or `git status` before acting on it. A memory about a durable
fact can be trusted as read.

## Comments

**Budget: comments earn their place or they go.** 42% of the Python here is comments and it is too
much — it slows writing, slows reading, and goes stale silently.

Write a comment for exactly three things:

1. **A constraint the code cannot show.** Why port 5433, why this must not be `python3`.
2. **A defect this line prevents**, with what it cost. `efcc19d`, the mtime rule, the stash rule.
3. **A decision with a live alternative** — what was chosen against, in one sentence.

Do not write: what the next line does · where something came from · why a change is correct (that
is talking to a reviewer, and it is noise the moment the PR merges) · a restatement of the type
signature · an argument for a rule that a test already enforces.

**A docstring is one to three sentences.** If a module needs more, the explanation belongs in
`docs/` and the docstring points at it.

## Code style

Small, focused modules. A file past one clear responsibility is a signal.

**Validate at system boundaries — user input, vendor responses, subprocess output — and trust
internal code.** No error handling for conditions that cannot occur.

**Factor at the second use.** The third is where the copies have already drifted, and reconciling
drift is more expensive than extracting a function.

**Delete rather than deprecate.** A dead path still typechecks and still gets maintained by someone
who cannot tell it is dead.

**Build for the case that exists.** An abstraction added for an anticipated second caller is debt
with no asset behind it. Wait for the caller.

**A workaround ships with a backlog entry naming what retires it.** The oasdiff exemption is the
model: written down, scoped, with the condition that ends it.

The counterweight, because this can be over-applied: the test is whether the debt would make a later
change slower or a defect quieter. Work that fails that test is polish, and polish competes with the
milestone.

## Where a convention goes

Narrowest tier that still catches the failure.

- **Every turn, every agent:** this file, and `.claude/rules/*.md` with no `paths:` frontmatter.
  Two load that way and both are deliberate. **Adding a third is the most expensive change you can
  make to this repository.**
- **While a matching file is open:** a rule with `paths:` frontmatter. Most belong here.
- **On request:** a skill, or a document under `docs/`. Specs and plans live here; the tiers above
  cite them.

**Prefer a pointer to a copy.** A fact written twice will disagree with itself, and this repository
has spent a week fixing exactly that.

## Branches and landing

**A worker branches from the integration branch, gates, and pushes its own branch.** The coordinator
merges. A worker never opens a pull request and never merges into `main`.

**A fast-forward of a branch that already contains `origin/main` is not a merge.** It creates no
commit, resolves no conflict and cannot lose work. `git merge-base --is-ancestor origin/main HEAD`
is the proof, and it is a command rather than a belief. **A worker may push `main` when that check
passes and only then**; if it fails the branch has diverged — escalate instead of resolving.

**`main` catches up by fast-forward, daily.** A stale `main` makes everything downstream unprovable.
Measured 2026-08-06: 27 hours and 192 commits behind, and nothing had actually diverged.

**Do not gate a landing on CI.** Hosted runners report a job that never started as `failure` (B112),
so the local gate is the authority: `uv run pytest tests/ -q -n0`, then `npm run build`,
`npm run lint`, `npm test` from `web/`. Say which ran. Never claim CI covered something it did not.

## Commits

Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Body explains why, not what.

**Carry the work item in the subject:** `feat: CI-W503 provenance is bars`. The register is
`docs/superpowers/WORKLOG.md`.

**Claim the number immediately before committing, not when you start.** Several sessions push here
at once and the number is a shared counter — claiming early guarantees a collision and a rebase.
This session hit three. Re-read the tail of the worklog, take the next number, write the row, commit.
