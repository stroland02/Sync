# M4 and the reference research: where everything is

Written 2026-08-04 to replace a scattered set of artifacts with one account. A session arriving cold
should be able to read this file and know what exists, what is decided, what is open, and what to do
next, without reconstructing anything from a transcript.

**Reconciled 2026-08-05 against `a87cbf3`.** Forty-plus commits landed on this branch after the first
draft, including the fleet screen this file originally called an open gap. Every claim below was
re-checked against `git log` and the tree rather than carried forward.

## The honest summary of how this went

The console was built well and the reviews caught real defects. The research around it was run badly:
too many agents fanned out at once, a fourteen-agent workflow was relaunched into an exhausted
account limit and burned 618,000 tokens in seventy seconds for one usable note, and the output landed
in five directories with no index. Two audits are still incomplete and one was stopped deliberately.

None of that changes the findings, which are good. It changes how the next round should be run, and
`docs/superpowers/ORCHESTRATION.md` now carries that rule: width is the most expensive choice an
orchestrator makes, and it costs the same whether or not it works.

## The branch

`m4-dashboard`. A raw commit count goes stale by the next tick — it already has once, from sixteen to
fifty-one — so this names what the branch contains instead of counting it.

The first slice (Tasks 1–4: the `web/` scaffold, the console's first three graph levels, the Solution
Workflow view, the CI gate) went through a merge gate that returned **ready to merge** after one
Critical and three Important findings were fixed and independently verified, then a second slice
added the fleet screen and a design-system pass, and both slices' open questions have since been
ruled. Nothing in this branch has gone back to main yet — that step is the human's.

| Commit | What |
|---|---|
| `eabc20f`, `98ba8e3` | Task 1 — the `web/` scaffold |
| `5aae9c9` | merge of `main`, bringing in Task 2's HTTP transport (`8e6d3b0`, landed by the other session) |
| `2a4c5f4` | Task 3 — the console's first three graph levels |
| `f6e6a1c`, `897d182` | Task 4 — the Solution Workflow view |
| `0902571` | the console's CI gate |
| `259906b` | the fix wave answering the first slice's final review — the run-state Critical (a live run reading as terminal) |
| `0a1c8bc` | the two follow-ups that review named, closed: the pagination clamp's floor, and the docstring-parsing mirror test replaced with one that parses an exported const |
| `b4b488d` | the run-state and abandonment specification, proposed |
| `e7ee2b7` | a CI gate against unqualified test skips |
| `7f8661d`, `f6fbc93`, `12cbaf0`, `7535fbf` | the fleet screen — `sync.dashboard.fleet` and its three read-only view models, the routes over them, the screen itself as the console's new index route, and the fix that made it render `abandon_reason` |
| `1ef6103`, `83f64a6` | the design system's five open questions, ruled — dark mode ships, the brand hue is a blue-violet near 265°, 14px body text |
| `ff41faa` | slice 2's five open questions, ruled — including overturning a recommendation to delete `@react-three/fiber`, `three`, `drei` and `react-grid-layout`, because the owner had since asked for those capabilities by name |
| the remaining ~30 | rules, loops, further specifications, and the reference research described below |

## What was decided, and where each decision lives

Rules bind every session and load automatically. Specifications are proposals until accepted.

| Decision | File |
|---|---|
| While executing a plan, decide and record the ruling; three things only are still the human's | `.claude/rules/autonomous-development.md` |
| The interface is ours; competitors give concepts and workflows, never screens | `.claude/rules/interface-originality.md` |
| Who owns which paths, how to reach the other agent, and why the orchestration board cannot be bound from a tool call | `docs/superpowers/ORCHESTRATION.md` |
| Model tier per role, width discipline, and never re-dispatching into a limit | `docs/superpowers/ORCHESTRATION.md` |
| How a console improvement tick decides its work | `docs/superpowers/loops/console-improvement-tick.md` |
| Run states, the abandonment vocabulary, and why no confidence score — **accepted** (`ff41faa`); the `Disposition` move and the sixteen codes still need to land in `src/sync/remediate/`, unblocked but not yet done | `docs/superpowers/specs/2026-08-04-sync-run-state-and-abandonment-vocabulary.md` |
| The design system's five open questions — dark mode ships, brand hue ~265°, 14px body text, the two 3D/grid packages stay installed unimported | `docs/superpowers/plans/2026-08-05-sync-console-design-system.md` (ruled in `1ef6103`, `83f64a6`) |
| Slice 2's five open questions, including the fleet keyed by run rather than repository and the overturned package-deletion recommendation | `docs/superpowers/plans/2026-08-04-sync-m4-slice-2.md` (ruled in `ff41faa`) |

## The research, and what each piece answers

Everything is under `docs/superpowers/references/`. Read the one whose question you have; nobody
reads a reference set end to end.

**`notes/` — one file per reference, rewritten from cloned source rather than documentation.**

| File | The question it answers |
|---|---|
| `impeccable-interface-quality.md` | What to check when improving the console's interface quality |
| `competitor-interfaces.md` | How six shipping products present a finding, evidence, a run in progress, and a refusal |
| `alibaba-open-code-review.md` | How a large company's review pipeline is actually wired, stage by stage |
| `code-graph-and-memory.md` | How four projects represent a codebase as a queryable graph, and how two of them draw one |
| `pageindex-retrieval.md` | Whether an index would help the console's paging or the frozen MCP surface |
| `system-design-and-scalability.md` | Which scaling material applies to a pipeline whose critical path is a customer's CI run |
| `roadmap-frontend-skills.md` | Which frontend concept the console needs next |
| `public-apis-and-hosting.md` | How to prioritise the next vendor adapter, and what hosting a solo founder can afford |

**`engineering/` — one file per engineering dimension, read across all nine repositories at once.**
All eleven dimension notes have landed: repository layout and boundaries, testing strategy, CI and
release engineering, error handling and failure, observability, data modelling and persistence, API
and interface design, dependencies and packaging (`f98bc64`), plus the final three — configuration
and secrets, documentation and onboarding, and LLM engineering practice (`eb59a73`), which is also
where the prompt-injection finding below came from. **Still missing:** the synthesis and the
completeness critic. Neither has a file in this repository; nothing has resumed that work since
`f98bc64` stopped on a session limit.

**`screenshots/` — twenty-two captures of six competitors' interfaces.** A research artifact, and
explicitly **not** a design target. `.claude/rules/interface-originality.md` says so and says why.
`notes/competitor-interfaces.md` interprets them.

## The three findings worth acting on first

Each is stated as a problem before it is a feature, which is the test the originality rule sets.

**An operator cannot tell why a run gave up, in aggregate.** `abandon_reason` is free text, so
"which change kinds do we abandon most, and at which node?" can only be answered by reading strings
by hand. `CLAUDE.md` promises abandoned runs are data and that abandoned attempts are where routing
learns which change kinds are not mechanically safe; the schema behind that promise cannot keep it.
The specification, accepted in `ff41faa`, proposes sixteen codes derived from the routing predicates
that actually reach `abandon`. The shape came from a competitor; every value came from Sync's own
code. The codes have not yet been written into `src/sync/remediate/`.

**Nothing said what states a run can be in, so three modules held three partial answers.** That is
the root cause of the Critical, and the fix filtered the symptom. The specification moves the list to
`sync.core.models` and deletes `running` from it, since a run is live exactly when its checkpoint
carries no outcome.

**A run blocked on something outside Sync's control looks identical to one grinding.** Waiting on a
customer's CI is not Sync working. The specification declines to add a state for it, because the
graph compiles with no interrupts and no checkpoint could carry one, and proposes deriving it from
the current node instead.

## What is open

**Needing the project owner:**

- Nothing left in the run-state and abandonment specification — it was accepted in `ff41faa`. What
  remains is implementation, not a ruling: the `Disposition` move and the sixteen abandonment codes
  still need to land in `src/sync/remediate/`, and no commit on this branch has touched that
  directory.
- The same two contradictions in `src/sync/remediate/`, still unresolved because nothing has changed
  there: `state.py` and `tiered.py` cite the same rule and disagree about whether `NoPatchWarranted`
  should reach `abandon_reason`; and `sync.mcp.propose` writes five values into `RunState["outcome"]`
  that are not in the `Outcome` literal, which the console now filters to null, so such a run would
  read as permanently in flight. Both are handed to the session that owns that code.
- B7, the M0 acceptance run, which opens a real pull request and therefore is not an agent's call.

**Unfinished research:**

- The engineering audit's three missing dimensions have landed (`eb59a73`) — see above. What is
  still unfinished is the synthesis and the completeness critic; neither has resumed.
- The deeper interface pass — **stopped deliberately.** Driving a browser is the most expensive kind
  of agent here: every navigation captures a screenshot, the full DOM, the page as markdown and the
  console log, and the agent then reads the markdown. The project's owner is taking these captures
  by hand instead, which is both cheaper and better targeted.

**Follow-ups the merge gate named** are closed, both in `0a1c8bc`: a floor on the pagination clamp,
because `?limit=-1` had returned the whole page minus one row and the report wrongly called that
harmless; and the mirror test that parsed prose in a docstring, replaced with one that binds an
exported const by name, so a renamed node is a build failure rather than a blank line.

## Two facts that will otherwise cost somebody an afternoon

**The 38 local test failures are not a regression and not `yarn`.** `oasdiff` is not installed in
every worktree — `tools/` is gitignored and `scripts/bootstrap_tools.sh` has not been run there — so
`sync.signals.oasdiff._binary()` raises `FileNotFoundError`. All 38 failures and all 9 errors trace
to that single missing binary. CI installs it from `.oasdiff-version` and is green. Run the bootstrap
before reading a red suite as breakage.

**The orchestration board cannot be bound from inside a tool call.** `orca orchestration run-use`
refuses with `legacy_read_only`, because it wants the identity of the terminal it is binding and a
command issued through a tool carries none. Plan state therefore lives in the SDD ledger at
`.superpowers/sdd/<plan>/progress.md`, which is also what survives a compaction.
