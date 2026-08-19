# Sync

Sync watches the third-party APIs a codebase calls and opens verified pull requests when one
breaks, drifts, or wastes money.

**The binding is the product.** The API Dependency Graph — static call sites joined against vendor
changes and runtime telemetry — is what customers pay for. Repair is a feature that proves the
binding was right, not the spine. Detectors query the graph and all emit one `Finding` into one
remediation pipeline. Building something that neither reads nor writes that graph? Question it.

Design: `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`.
Positioning: `specs/2026-07-25-sync-positioning-and-open-core.md`.

## The governing principle

**Encode a rule where it fails, not where it is read.** A rule in prose is enforced by whoever
remembers it; a rule in a test, type, lint, schema constraint or hook is enforced always.

Measured in this repository: the conventions that held were machine-enforced. The ones that decayed
were prose — seven of twenty-four "protected" console sentences cited deleted files and nothing
noticed for two weeks. If you are about to write a paragraph asking the next agent to remember
something, write the check instead.

## Environment — these will break your session

| | |
|---|---|
| Python | 3.12. The interpreter is `python`. **Never `python3`** — a Microsoft Store shim that will not run. |
| Packages | `uv` only. Poetry is not installed. |
| Database | Postgres 16 on **port 5433**. **No admin rights: Docker and WSL2 are unavailable.** Embedded cluster at `~/.sync-postgres` — `npm run no-admin` starts it. Does not survive a reboot (B191). |
| Shell | Snippets are POSIX for Git Bash. **PowerShell 5.1 has no `&&`** — chain with `; if ($?) { }`. |
| GitHub | `gh`, already authenticated. |
| TypeScript | via `npx`. No vendored compiler. |

**Never `git stash` when another worktree may be active.** `refs/stash` is one ref shared across
every worktree — two agents each popped the other's stash (2026-08-16). Use `git diff` or a scratch
branch.

`LF will be replaced by CRLF` on commit is expected. Do not add `.gitattributes`.

## Non-negotiables

Enforced by tests. Breaking one fails the build, not a review.

- **`sync.core` imports nothing from a sibling package.** One sibling import drags Postgres into
  the dependency tree of anyone writing a vendor adapter. `tests/test_import_boundary.py`.
- **Nothing reaches a pull request unverified** — `tsc`, then the customer's own CI.
- **Vendor-specific knowledge lives in adapters, never core.** The moment core knows a vendor's
  name, the plugin story is dead.
- **We never hold customer secrets.** Unqualified.

Two qualifications on verification, both measured, both worth stating accurately: `tsc` verifies the
tree a *push* would carry (untracked and ignored paths are held out); and **"we never execute
customer code" is the intent, not the invariant** — installs pass `--ignore-scripts` and Sync never
runs the customer's application, but it does run their toolchain.

## How we work

**Decide rather than ask.** Executing a plan, pick what a careful engineer here would pick, record
the ruling in the plan's ledger, keep going. Three exceptions stay the human's: an irreversible
action outside the repository, a decision that invalidates the plan's architecture, and anything
needing a credential or a spend. One blocking question once idled a milestone for three hours.
`.claude/rules/autonomous-development.md`.

**When one of the three does arrive, ask it as multiple choice.** Owner instruction, 2026-08-19.
Options with the trade-off spelled out, a recommendation first, and enough context to rule without
opening the code. This is a rule about *form*, not frequency -- it does not license asking more, and
an open-ended "what would you like?" is the shape it replaces, because it hands the work of framing
the decision back to the person with the least context loaded.

**If no answer comes, take your own recommendation and keep going.** Owner instruction, and it is
what makes the rule safe rather than a new way to stall: mark the option you would pick, and on
silence proceed as if it had been chosen -- record it as a ruling in the plan's ledger, name it as
reversible in the next report, and carry on. A question asked and then waited on is the three-hour
milestone stall wearing a nicer interface.

The two genuine stops are unchanged, and silence is not consent for either: **an irreversible action
outside the repository, and anything spending money or needing a credential.** Those wait. Everything
else proceeds on the recommendation, which is why the recommendation has to be the one you would
actually defend.

**Test first, and watch it fail for the reason you expect.** A test that has never failed has never
been shown to test anything. When a test asserts on a subprocess, an exit code or an external tool,
break it deliberately and watch it go red before trusting it — the import-boundary test's original
form exited 0 without parsing its argument.

**Ship the smallest complete change.** Done means it works, it is tested, and the gate is green.

**A memory describing who is doing what right now is a hypothesis.** Several sessions push here at
once. Verify against `git log` before acting on it.

## Comments

**Budget, enforced by `scripts/lint_comments.py` as a ratchet.** Write a comment for exactly three
things: a constraint the code cannot show; a defect this line prevents, with what it cost; a
decision with a live alternative, in one sentence.

Never: what the next line does · where something came from · why a change is correct (that is
talking to a reviewer, and it is noise the moment the PR merges) · a restatement of the signature ·
an argument for a rule a test already enforces.

**A docstring is one to three sentences.** More belongs in `docs/`, with the docstring pointing at it.

## Code style

Small, focused modules. **Validate at system boundaries** — user input, vendor responses, subprocess
output — **and trust internal code.** No handling for conditions that cannot occur.

**Factor at the second use.** **Delete rather than deprecate.** **Build for the case that exists** —
an abstraction for an anticipated second caller is debt with no asset behind it. **A workaround
ships with a backlog entry naming what retires it.**

Counterweight: the test is whether the debt makes a later change slower or a defect quieter.
Anything else is polish, and polish competes with the milestone.

## Where a convention goes

Narrowest tier that still catches the failure.

- **Every turn:** this file. **Adding to it is the most expensive change you can make.**
- **While a matching file is open:** `web/CLAUDE.md`, `src/sync/CLAUDE.md`, and `.claude/rules/*.md`
  with `paths:` frontmatter. Most conventions belong here.
- **On request:** a skill, or a document under `docs/`.

**Prefer a pointer to a copy.** A fact written twice will disagree with itself.

## Landing work

**A worker branches from the integration branch, gates, pushes its own branch.** The coordinator
merges. A worker never opens a pull request and never merges into `main`.

**A fast-forward of a branch already containing `origin/main` is not a merge** — no commit, no
conflict, no lost work. `git merge-base --is-ancestor origin/main HEAD` is the proof. A worker may
push `main` when that passes and only then; if it fails, escalate rather than resolve.

**Do not gate a landing on CI.** Hosted runners report a job that never started as `failure` (B112),
so the local gate is the authority: `uv run pytest tests/ -q -n0`, then `npm run build`,
`npm run lint`, `npm test` from `web/`. Say which ran; never claim CI covered something it did not.

**Commits:** Conventional Commits, body explains why. Carry the work item:
`feat: CI-W503 provenance is bars`. Register is `docs/superpowers/WORKLOG.md`.

**Claim the worklog number immediately before committing, not when you start.** It is a shared
counter across concurrent sessions; claiming early guarantees a collision. One session hit three.
