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

## The console renders the product position, so its interface rules are not taste

Sync's argument is that competing tools present a black box and a result and ask a reviewer to
trust it. The operator console exists to show the system's reasoning instead. Three authorities
bind it and none of them is this document:

- **The hierarchy comes from the specification**, never from a plan.
  `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md:427-445` is the
  authoritative block. Three plans built a different one and nobody noticed until a reconciliation
  on 2026-08-05 found three of eleven routes matched, four levels invented and two reparented.
  `.claude/rules/console-hierarchy.md` holds it.
- **`DESIGN.md` is the token contract** — every colour, size, space and elevation, with the
  arithmetic that proves each contrast, against a 5.05:1 floor. Dark-only as of 2026-08-05.
  `.claude/rules/console-surface.md` carries what binds while a screen is open.
- **The interface is ours.** `.claude/rules/interface-originality.md`.

**One rule sits here rather than in a path rule, because it binds a Python view model exactly as
much as a React component: no composite score, no health figure, no traffic light, no green dot,
no liveness pulse.** Rejected on the record three times. A scalar that averaged three gates would
collapse "we could not check" onto the same axis as "we checked and it passed", which is the
failure this console exists to replace.

That refusal is not conservatism, and the strongest form of the argument is worth carrying because
it is the form that survives a sceptic. A mature control plane ships all three patterns — a status
dot, a gauge, a coloured badge — and documents a precondition for each. Its dot requires a stored
state transition inside one closed lifecycle; nothing in our data tells a run parked on the
customer's CI from one that has died. Its gauge requires a 0–100 ratio against a fixed maximum,
with breakpoints that already exist elsewhere in the product; a composite health figure has
neither. Its badge — a recorded value from a closed vocabulary, legible without its colour — is
permitted, and **Sync already permits exactly that**: run outcome, error state, absence. **We are
not stricter than a mature control plane. We have data that fails its own published tests, and we
said so.** (`docs/superpowers/plans/2026-08-05-sync-console-architecture.md`, section 19.)

Four distinctions follow from the same position, and each is rendered rather than assumed:
provenance at two levels, absence apart from zero, staleness apart from liveness, and
never-measured apart from nothing-here. Twenty-four sentences on screen carry them, reproduced with
file and line in that plan's *Establish 2* (`:102-207`). **Restyling one is allowed. Deleting one,
shortening one, collapsing one behind a disclosure, or moving one into a tooltip is not.**

## Toolchain

| | |
|---|---|
| Python | 3.12. The interpreter is `python`. **Never `python3`** — that is a Microsoft Store shim on this machine and it will not run. |
| Packages | `uv` only (`uv add`, `uv run`). Poetry is not installed; do not introduce it. |
| Database | Postgres 16 on **port 5433**, not 5432. **This machine has no admin rights, so Docker, WSL2 and every VM-backed runtime are unavailable** — measured 2026-08-18, and `docker compose up -d` is for machines that have it. Here the database is the embedded cluster at `~/.sync-postgres` (portable 16.4 binaries, user space): `npm run no-admin` adopts or starts it and hands over to `dev_up.py`. It does not survive a reboot unattended (B191); after one, `npm run no-admin` again, or `~\.sync-postgres\pgsql\bin\pg_ctl.exe -D ~\.sync-postgres\data -o "-p 5433" start`. |
| TypeScript | via `npx`; the repo does not vendor a compiler. |
| Package managers | Sync installs a customer project's dependencies before typechecking, using whichever manager that project's lockfile names. **That manager must be on `PATH` or the run abandons** — `deps.py` deliberately refuses to substitute one for another, because a different manager resolves a different tree. `npm` and `pnpm` are present here; `yarn` is not, and `corepack enable` needs administrator rights on this machine. The shims are installed unelevated instead: `corepack enable --install-directory "$(pwd)/tools/shims"`, with `tools/shims` prepended to `PATH` for the run. `tools/` is gitignored. `shutil.which` resolves the `.CMD` form, which is the one Windows can execute. |
| GitHub | the `gh` CLI, already authenticated. |
| Shell | command snippets are POSIX, written for Git Bash. PowerShell 5.1 here has no `&&` — chain with `; if ($?) { }`. |

Git warns `LF will be replaced by CRLF` on every commit. That is expected. Do not add a `.gitattributes` or rewrite line endings to silence it.

**Never `git stash` when another worktree of this repository might be active.** `refs/stash` is one ref shared across every worktree of one repository, not per-worktree — a stash pushed from `b126-t5` and a stash pushed from `b126-t7` land on the same LIFO stack, and `git stash pop` in either worktree pops whatever is on top regardless of which worktree pushed it. Measured 2026-08-16: two parallel agents each ran `git stash` to compare against a clean base, and each popped the other's stash into its own working tree — every file involved was real and correctly written, just briefly living in the wrong worktree. `git fsck --unreachable --dangling` recovers a lost stash by commit hash (`git stash apply <hash>`) even after it falls off the visible `git stash list`, which is what closed this out, but the fix is not to need it: use `git diff`/`git stash show` read-only, or a scratch branch, instead of stashing in a worktree that isn't provably alone.

**Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, **and `subprocess.run(..., text=True)`**. On Windows all of these default to the locale codepage — cp1252 here — so any non-ASCII byte corrupts or raises, and only on this platform. Every fixture in this repository is ASCII, which means **no test will ever catch it**; it fails first against real vendor data or a real customer repository. When handling bytes that are not text, use `read_bytes`/`write_bytes` and do not decode at all.

`subprocess` is the easy one to forget, and it fails worse than the others. A decode error there is raised on the reader thread and never propagates: the call returns with `stdout` set to `None`, and the next line that concatenates it raises `TypeError` somewhere unrelated. Task 6 shipped exactly this — one accented identifier anywhere in a typechecked project crashed the verification gate instead of failing it. Task 4 hit the plain `read_text` form twice.

**`encoding="utf-8"` on the call is not enough when the child chooses its own encoding.** It says how to decode the bytes, not which bytes arrive. Run a Python child on this machine and it emits cp1252, so `subprocess.run(..., text=True, encoding="utf-8")` still raises `UnicodeDecodeError` on the reader thread the moment the child prints a non-ASCII byte — an em dash in a source line pytest echoes back is enough. Set `PYTHONIOENCODING=utf-8` in the child's environment as well, and pass `errors="replace"` where the output is diagnostic rather than data. Measured while mutation-testing two modules whose docstrings carry em dashes: the run returned exit 1 with no output at all, which a harness reads as either a survival or a kill depending on how it counts, and neither is true.

## How we work

**Test first, always, in both languages.** Write the failing test, run it, watch it fail for the reason you expect, then implement. A test that has never failed has never been shown to test anything.

**TypeScript is test-first too, as of 2026-08-06.** The console has a runner: `cd web && npm test` is `vitest run` over jsdom, wired into CI's `web` job beside `lint` and `build`. Its scope is Decision 6's and it is deliberately narrow — **classification, derivation and structural invariants; never class names, never snapshots.** A snapshot test in a console being actively restyled fails on every correct change and gets deleted within a week by whoever it blocks. Anything about rendered pixels is measured in Chrome and written into `DESIGN.md` instead, which is a different discipline with a different gate. Where a rule *belongs* is a separate question from where it is tested, and `.claude/rules/console-dev-loop.md` carries it: a rule the payload can answer still belongs in the payload, so two screens cannot disagree about one fact.

**Executing a plan, decide rather than ask.** `.claude/rules/autonomous-development.md` carries the rule and the three exceptions that are still the human's. It exists because one blocking question idled a milestone for three hours; a ruling recorded in the plan's ledger costs a fix round to reverse, and waiting costs the afternoon.

**A memory that describes who is doing what right now is a hypothesis, not a fact.** `HANDOFF.md`, a coordinator's memory of which worktree owns which milestone, a note about which chat is mid-task — all of it decays in days, because several sessions push to this repository concurrently. A memory about a durable fact (a toolchain quirk, a strategic constraint, a worktree-layout convention) does not carry this risk and can be trusted as read. A memory about live coordination state can be a fortnight stale and read as current, which is worse than no memory at all — it is confident and wrong rather than absent. Verify it against `git log`, `git status`, or `orca worktree ps` before reading deeper into its content, not after acting on it. Measured 2026-08-16: three memory files describing a workspace split and an in-flight task were each independently confirmed stale and fully superseded, only after the check ran.

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

Passing the Messages-API shape to `ClaudeAgentOptions` does not work, and this document previously said otherwise.

**It said something else wrong, and the correction matters because it is load-bearing for the patch agent's containment.** It listed seven fields as the verified surface. The installed package (`0.2.128`) declares **45**, and the ones this project cares about were all missing from that list: `hooks`, `can_use_tool`, `tools`, `sandbox`, `env`, `max_budget_usd`.

Three facts about restricting what the agent may do, all checked against the installed package rather than inferred:

- **Listing a tool in `disallowed_tools` is a real block. Omitting it from `allowed_tools` is not.** That much was right.
- **A `can_use_tool` callback is shadowed by a whole-tool `allowed_tools` entry.** The SDK's own
  `types._get_can_use_tool_shadowed_warning` says a whole-tool allow auto-approves *before* the
  callback is consulted, and directs you to a `PreToolUse` hook to gate every call. Every entry in
  the patch agent's allow-list is a whole-tool entry, so a `can_use_tool` gate there would have been
  consulted for nothing and looked like it was working. `hooks` also works with a one-shot string
  prompt; `can_use_tool` requires streaming mode and raises without it.
- **The hang is a property of the default permission mode, not of headless mode.** `PermissionMode`
  includes `dontAsk` — deny anything not pre-approved — alongside `default`, `acceptEdits`, `plan`,
  `bypassPermissions` and `auto`.

`sandbox` accepts network `deniedDomains` and is **macOS and Linux only**, so it is not available on
this machine. That is the mechanism B97 needs to actually close, and knowing it is unavailable here
is why the gate that shipped is a `PreToolUse` hook instead
(`docs/superpowers/specs/2026-07-25-sync-threat-model.md`).

`temperature`, `top_p`, and `budget_tokens` return HTTP 400 on this model on either surface. Steer with prompting instead. Thinking is on by default, and on the Messages API `max_tokens` caps thinking plus output together, which is why that ceiling is generous.

## Technical debt is the scaling constraint, and it is paid down continuously

This is the platform's integrity condition, not a preference. A product stops scaling when the cost
of the next change is set by the accumulated shape of the last hundred, and that is what debt is.
Sync is built by one person; there is no team here to absorb an interest payment later. So the
standing instruction is to keep debt near zero as the work happens, rather than to schedule paying
it down.

What that means concretely, and each of these has cost this repository time:

- **Factor at the second use, not the third.** The third is where the two copies have already
  drifted, and reconciling drift is a different and more expensive job than extracting a function.
- **Delete rather than deprecate.** A dead path still typechecks, still gets read, still gets
  maintained by someone who cannot tell it is dead. `retracted_at` survived removal from the payload
  because a TypeScript type kept describing it and the build stayed green.
- **A fact written twice will disagree with itself.** This is the same rule as *prefer a pointer to
  a copy* in *Where a convention goes*, and it is the most expensive form of debt here because the
  disagreement is silent.
- **Build for the case that exists.** An abstraction, a flag, or a hook added for an anticipated
  second caller is debt with no asset behind it. Wait for the caller.
- **A workaround ships with a backlog entry naming what retires it, or it does not ship.** The
  oasdiff idempotency exemption is the model: written down, scoped, with the condition that ends it.

The counterweight, because this instruction can be over-applied: the test is whether the debt would
make a later change slower or a defect quieter. Work that fails that test is polish, and polish
competes with the milestone. Nine ticks went to design-system refinement while two specified levels
of the console did not exist.

## Code style

Comment to state a constraint the code cannot show — never to narrate what the next line does, where something came from, or why a change is correct. That last one is talking to a reviewer, and it becomes noise the moment the pull request merges.

Prefer small, focused modules over large ones. A file that has grown past one clear responsibility is a signal, not a style preference.

Do not add error handling, fallbacks, or validation for conditions that cannot occur. Validate at system boundaries — user input, vendor responses, subprocess output — and trust internal code.

## Where a convention goes

Three tiers, and they cost very different amounts. Put a convention in the narrowest tier that
still catches its failure.

**Every turn, for every agent:** this file, and any file in `.claude/rules/` with no `paths:`
frontmatter. Two rules load that way today and both are deliberate — `autonomous-development.md`,
because plan execution is not predicted by any path, and `interface-originality.md`, because the
directory of competitor screenshots it fences off can be opened from anywhere. **Adding a rule file
without `paths:` promotes it to the most expensive tier in the repository.** Do that on purpose or
not at all.

**Only while a matching file is in play:** a rule with `paths:` frontmatter. That is where a
convention scoped to a directory belongs, and where most of them are — `graph-grain.md`,
`signal-stage.md`, `remediate-stage.md`, `test-discipline.md`, `console-hierarchy.md`,
`console-surface.md`, `console-dev-loop.md`. A frontend convention loaded while somebody edits a
Python detector is pure cost.

**Only when something asks for it:** a skill, or a document under `docs/`. Specs and plans live
here. They are the authorities; the tiers above cite them.

Prefer a pointer to a copy. A fact written down twice is a fact that will disagree with itself, and
this repository has spent a week fixing exactly that. What earns a full restatement in the two
expensive tiers is what an agent must not be able to miss regardless of what it happens to be
editing — nothing else.

## Branches, and how work reaches `main`

**One integration branch at a time.** It is named in the milestone's plan — `console-identity`
during M7. Every worker branches from it, gates on it, and pushes its own branch. The coordinator
merges into the integration branch. **A worker never opens a pull request and never *merges* into
`main`.**

**Amended 2026-08-17 by the coordinator, and reversible.** That sentence used to end "and never
pushes `main`", which stopped a lane dead: it held a day of gated work locally while four other lanes
landed several units an hour, because it read the rule correctly and `autonomous-development.md`
lists pushing to `main` among the three things that stay the human's. The rule was written for one
integration branch and one coordinator, and it does not describe five lanes with disjoint file
ownership.

The distinction that survives both readings: **a fast-forward of a branch that already contains
`origin/main` is not a merge.** It creates no commit, resolves no conflict, makes no decision, and
cannot lose anybody's work — it is publication, not integration. `git merge-base --is-ancestor
origin/main HEAD` is the proof, and it is a command rather than a belief. **A worker may push `main`
when that check passes and only then; if it fails, the branch has diverged, the fast-forward
assumption is wrong, and it escalates instead of resolving.** Merging, pull requests, branch
deletion, credentials and spend are untouched.

**`main` catches up by fast-forward, on a schedule rather than at a milestone boundary.** The
integration branch is only ever ahead of `main`, never divergent, so landing it is
`git push origin <sha>:refs/heads/main` and nothing else — no merge commit, no conflict, no review
round. Do it at least daily.

The failure this exists to stop was measured on 2026-08-06: `main` sat 27 hours and 192 commits
behind while eighteen branches accumulated, and the owner could not tell which of five running dev
servers held current code. **Nothing had actually diverged** — fifteen of the sixteen work branches
were already ancestors of the integration branch, contributing zero unique commits. The mess was
entirely staleness plus uncleaned refs, and it read as merge debt. A stale `main` is expensive
because it makes everything downstream unprovable, not because it is hard to fix.

**Containment is a command, not a memory.** Before treating a branch as merged,
`git merge-base --is-ancestor <branch> <integration>`. Before landing,
`git merge-base --is-ancestor origin/main <integration>` — if that fails, the branch diverged and
the fast-forward assumption is wrong.

**A pull request is a record, not the merge mechanism.** Open one per milestone if the history is
worth annotating. Landing the integration branch closes it automatically, because its head is
already an ancestor. Do not gate a landing on CI: as of 2026-08-06 hosted runners acquire jobs
intermittently and report a job that never started as `failure` (B112), so **the local gate is the
authority** — `uv run pytest tests/ -q -n0`, then `npm run build`, `npm run lint`, `npm test` from
`web/`. Say which of those ran. Never say CI covered something it never executed.

## Commits

Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Write the body in normal prose explaining why, not what — the diff already says what.

**Carry the work item in the subject:** `feat: M4-W131 the expansion slice and four cold-start briefs`. The register is `docs/superpowers/WORKLOG.md`; take the next number, add the row before starting, and put the identifier on every commit belonging to that item. The sequence is one series across the whole project rather than one per milestone, so a number identifies work without its milestone having to disambiguate it — `M3-W125` and `M4-W126` are consecutive.

A work item is one reviewable unit: what a brief asks for, or what a tick takes. Several commits under one number is normal. Two numbers for one change is not.
