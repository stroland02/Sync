# Documentation and onboarding across four engineering references

Audited 2026-08-04 against clones under
`C:/Users/strol/AppData/Local/Temp/claude/C--Users-strol-orca-Sync-Sync/b4674d1e-f115-48c1-ab2c-dab217d86019/scratchpad/engrefs/`.
Examined for this note: `superpowers`, `claude-cookbooks`, `skills`, `open-code-review`. Every
claim is labelled VERIFIED (I opened the file this session and, where a command is quoted,
checked it against the repository rather than assuming it works), REPORTED (a document asserts it
and I did not independently confirm), or INFERENCE (my reasoning from what I read).

## 1. What this dimension covers, and why it matters here

Documentation is the interface between a codebase and everyone who was not in the room when it was
written — a new contributor, a future session of the same agent, the project's own owner six months
later. For Sync specifically this is not a nice-to-have: the project's binding rules live in prose
(`CLAUDE.md`, `.claude/rules/*.md`, `docs/superpowers/specs/*.md`), and the working method
(`.claude/rules/autonomous-development.md`) requires an agent executing a plan to decide against a
written authority rather than ask a question. If that authority drifts from the code, or is never
read, the entire "decide and continue" model degrades into agents guessing. The question this note
asks of each reference is not "is there a README" but "does anything stop the documentation from
becoming fiction."

## 2. The comparison

### 2.1 Quickstart commands checked against the repository, not assumed

**open-code-review's quickstart holds up.** `pages/src/content/docs/en/quickstart.md` gives four
numbered steps — `npm install -g @alibaba-group/open-code-review`, `ocr config provider`, `ocr llm
test`, `ocr review` — and separately `CONTRIBUTING.md:29-46` gives the contributor path: fork,
clone, `make build`, `make test`. VERIFIED: `Makefile:1` declares `.PHONY: build test clean run help
fmt vet check coverage ...` and lines 31 and 36 define `build:` and `test:` targets, so the two
commands the contributor doc tells a newcomer to run both exist. The architecture doc's function
references check out too: `pages/src/content/docs/en/architecture.md:30-31` names `Agent.Run` and
`Agent.dispatchSubtasks` as the two pipeline entry points, and VERIFIED, `internal/agent/agent.go:229`
defines `func (a *Agent) Run(ctx context.Context) (...)` and line 484 defines `func (a *Agent)
dispatchSubtasks(ctx context.Context) (...)`; the doc's five-gate filter description also matches
`internal/agent/preview.go:31`'s `func (a *Agent) whyExcluded(d model.Diff) ExcludeReason`. A
newcomer following this documentation reaches a running review in the time the doc claims ("a few
minutes"), and a reader who wants to understand the pipeline gets accurate file and function names
to open next.

**claude-cookbooks' real quickstart is not in the README.** `CLAUDE.md:5-14` gives `uv sync
--all-extras`, `uv run pre-commit install`, and `cp .env.example .env`. VERIFIED: `.env.example`
exists at the repository root, and `Makefile:35,45,50,54,60` defines `format`, `lint`, `check`,
`fix`, and `test` targets matching `CLAUDE.md:18-24` exactly. But `README.md` — the file GitHub
renders by default and the one a human newcomer opens first — contains none of this. Its own
"Prerequisites" section (line 5-9) says only "you'll need a Claude API key" and links to an external
fundamentals course; the actual `uv sync` / `.env.example` / `make test` sequence lives in a file
named for AI agents, not for people. INFERENCE: a human skimming this repository on GitHub is one
click away from a working dev setup and has no reason to look for it, because the file that has it is
addressed to something else.

**superpowers has no single quickstart because installation is inherently per-harness**, and it says
so: the README's "Quickstart" section (`README.md:6-8`) is a jump-table to eleven harness-specific
install blocks (Claude Code, Antigravity, Codex App/CLI, Cursor, Factory Droid, Gemini CLI, GitHub
Copilot CLI, Kimi Code, OpenCode, Pi), each a marketplace or plugin-manager command I cannot execute
or verify from this environment (they require a live marketplace registration). What I could check —
`docs/porting-to-a-new-harness.md` — states its own accuracy contract explicitly at line 17: "When
this guide and the code disagree, the code wins; fix the guide." That is a documented policy for
staying honest under drift, not a mechanism that enforces it, and is worth noting as the difference
between the two.

**skills (mattpocock/skills)'s quickstart is real but the newcomer path routes through a slash
command that configures itself.** `README.md:74-82` — install, then run `/setup-matt-pocock-skills`
once per repo, which the README describes as asking three questions (issue tracker, triage labels,
doc location) before anything else in the "Engineering" set is usable. VERIFIED via
`.agents/adr/0001-explicit-setup-pointer-only-for-hard-dependencies.md`: three skills (`to-tickets`,
`to-spec`, `triage`) are documented as "hard dependency" on that setup step and fail meaningfully
without it, while others degrade gracefully. That distinction being written down as an ADR, rather
than left implicit, is itself a good pattern — see 3.3.

### 2.2 Architecture documents and decision records

Three of the four keep a real decision record; one does not.

**open-code-review's `architecture.md`** (2.1 above) is the strongest example in the set: a mermaid
pipeline diagram, named files and functions, and a description of gate ordering
(`architecture.md:67-78`) that matches the code's actual gate sequence in `preview.go`. It reads as
written for a maintainer who needs to modify the pipeline, not for a visitor deciding whether to try
the product.

**skills keeps ADRs as a first-class artifact**, at `.agents/adr/000N-*.md`. Read in full:
`0001-explicit-setup-pointer-only-for-hard-dependencies.md` (11 lines, quoted above) states a design
tension (hard vs. soft dependency on setup config) and the reasoning for the split, not just the
decision. `0002-ship-as-a-claude-code-plugin.md` is referenced from the README itself
(`README.md:57`) as the live rationale for why a native Codex plugin is still on the roadmap rather
than shipped — the ADR is load-bearing documentation a reader is actually pointed at, not an archive
nobody opens.

**superpowers has no `docs/adr/` equivalent**, but its harness-porting guide functions as one for its
single largest architectural decision (skills are harness-agnostic; only a thin per-harness layer
translates). `docs/porting-to-a-new-harness.md:31-55` states the invariant and names the three
components (skills, tool mapping, bootstrap) precisely enough that Part 1 alone would let a reader
predict what changes and what doesn't when a twelfth harness is added.

**claude-cookbooks has no architecture document and does not need one in the same sense** — it is
not a single system, it is ~90 independent notebooks under topic directories. `registry.yaml` at the
root is the closest thing to a decision record, and it is generated/consumed data (a manifest of
notebooks with authors and paths) rather than prose reasoning. This is the correct absence for what
the repository is, and it would be a mistake to read it as a gap.

### 2.3 Docstrings: constraint versus narration

The house rule this note was asked to check each reference against is Sync's own: "Comment to state
a constraint the code cannot show — never to narrate what the next line does."

**open-code-review's `internal/session/manifest.go` and `internal/agent/agent.go` mostly pass this
test.** VERIFIED examples: `manifest.go:664-668` explains *why* a control byte is stripped before the
redaction regex runs ("an embedded control byte inside a token would [otherwise let] 'BBB' back in,
leaking part of the secret") — that is a constraint the code's five lines cannot show on their own.
`agent.go:146` on `RuntimeConfig` — "It deliberately excludes every secret: no token, and only the
endpoint host" — states what was left out and why, which is exactly the kind of fact a diff cannot
carry. Counter-example in the same file: scattered single-line comments like `// Layer 1: JSON config
file` immediately above `if configPath != "" {` in `telemetry/config.go:117` narrate rather than
constrain — a reader loses nothing if that comment is deleted, which is the test Sync's own style
rule implies.

**claude-cookbooks' notebooks are prose-heavy by design (they are teaching material, not library
code) and the one Python module reviewed for this note, `tests/notebook_tests/utils.py`, narrates
more than it constrains.** VERIFIED at `utils.py:193-222`, the `validate_uses_env_for_api_key`
function (already flagged in `docs/superpowers/references/engineering/testing-strategy.md` §2.5 as
an assertion-free check) carries the comment `# This is acceptable` on a dead `pass` branch — a
comment documenting an omission rather than a constraint, and in this case documenting an omission
that looks like a security check but performs none.

**superpowers' skill files are closer to specification than to code comments**, so the
constraint-vs-narration axis applies differently: `SKILL.md` bodies (e.g., the porting guide
excerpted in 2.1) are written entirely as constraints — "skills name actions, not tools" is a rule a
reader must hold to write a correct port, not a description of existing code.

### 2.4 Is documentation tested, generated, or left to drift

This is where the four references separate most clearly, and where the note's most useful finding
sits.

**claude-cookbooks link-checks its docs and notebooks in CI.** `.github/workflows/links.yml` runs
`lychee` (config at `lychee.toml`, VERIFIED: timeout, retry, and cache settings for exactly this
purpose) against the repository's links. A broken external link becomes a CI failure, not a slow
rot. This is a genuine documentation-testing mechanism, and it coexists with the testing-strategy
note's finding that the same repository's *notebook* tests are frequently assertion-free — link
integrity is verified; notebook correctness mostly is not.

**open-code-review runs a translation-sync check that is half-blocking by design, and says so in a
comment worth quoting in full.** `.github/workflows/translation-sync.yml:1-7`: "Content-validation
guardrails, kept out of ci.yml (which is build/test/lint): blocking: all README*.md translations
share the same ## section structure. non-blocking: warn when a docs/en page changes without its
zh/ja/ru counterpart." VERIFIED: the blocking step (`check-translation-sync.js readmes`, line 40)
enforces structural parity across five README languages; the non-blocking step (lines 47-49) is
explicitly `continue-on-error: true` with a comment explaining the choice was deliberate, not an
oversight. This is a rare case of a project stating exactly how much rigor it decided a documentation
check deserved, and why — structure is cheap and worth blocking on; content-freshness across
languages is not something CI can judge, so it warns instead of pretending to gate it.

**superpowers has a documented commitment to not letting the porting guide drift silently**
(`docs/porting-to-a-new-harness.md:17`, quoted in 2.1) but no automated check enforcing it — the
guide's accuracy rests on whoever edits the code remembering the sentence exists. INFERENCE: this is
a norm, not a mechanism, and is weaker than either of the two CI checks above.

**skills has no CI check tying `.agents/adr/*.md` or `README.md`'s skill list to the actual
`skills/` directory contents.** VERIFIED by inspection: `scripts/link-skills.sh` and
`scripts/list-skills.sh` (noted in the testing-strategy audit as asserting nothing) are the only
scripts touching the skill inventory, and neither diffs the README's descriptions against the
`SKILL.md` files they summarize. A renamed or removed skill would leave a stale README entry with
nothing to catch it.

## 3. What Sync should adopt

**A structural link/translation-parity check modeled on open-code-review's
`translation-sync.yml`, scoped to Sync's spec-and-rule set rather than to language translations.**
Sync doesn't translate docs, but it has the same shape of problem: `CLAUDE.md` references
`.claude/rules/autonomous-development.md`, `.claude/rules/interface-originality.md`, and several
`docs/superpowers/specs/*.md` files by path. A cheap CI job that greps every such reference and
fails if the target file is missing (open-code-review's *blocking* tier) would catch exactly the
failure mode the porting guide's honor-system sentence cannot: a rule file renamed or deleted while a
pointer to it survives. This is a half-day script, not a project.

**An architecture walkthrough in the shape of open-code-review's `architecture.md`, naming the
actual pipeline functions, for the remediation graph.** Sync already has the design spec
(`docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`) and the latency spec, both
of which argue architecture rather than narrate the current code. What's missing is the
`architecture.md` genre specifically: a doc that says "here is `Agent.Run`, here is
`dispatchSubtasks`, here is the order gates run in" for `sync.remediate`'s LangGraph — a reader
opening `src/sync/remediate/` cold today has the specs for *why* it's shaped this way but no single
page mapping graph node names to file and function, the way open-code-review's doc maps `whyExcluded`
to `preview.go`. Verified against 3.2's own reading: `docs/superpowers/references/engineering/`
itself is the closest analog Sync has to this genre, and it is reference material about *other*
projects, not a walkthrough of Sync's own pipeline.

**The hard-dependency/soft-dependency ADR pattern from `skills/.agents/adr/0001-*.md`**, applied to
Sync's own rule files. `.claude/rules/autonomous-development.md`, `.claude/rules/interface-
originality.md`, `.claude/rules/test-discipline.md`, `.claude/rules/signal-stage.md`, and `.claude/
rules/remediate-stage.md` all load conditionally ("loads whenever you touch `tests/`" per
`CLAUDE.md`'s own description of `test-discipline.md`), and it is not written anywhere which rules
are load-bearing for correctness (agents will get a wrong answer without them) versus advisory
(agents produce lower-quality but not wrong output). Naming that split, the way skills' ADR does for
its own setup dependency, would tell a new session which rule it cannot safely skip reading.

## 4. Where Sync is already ahead, and where a reference's approach is a step backward

**Sync's rule files already do what this note found only partially done elsewhere: state the
measured defect a rule exists to prevent.** `.claude/rules/autonomous-development.md`'s opening
section ("The failure this exists to prevent") names a concrete three-hour idle session and its
cause before stating the rule; `CLAUDE.md`'s Windows encoding section names two dated incidents
("Task 6 shipped exactly this," "Task 4 hit the plain `read_text` form twice") with enough specificity
to be falsifiable. Of the four references read for this note, only open-code-review's
`manifest.go:664-668` comment and the translation-sync workflow's own header comment reach that same
bar of naming the failure a mechanism exists to close; most documentation in the other three states
the rule without the incident behind it.

**claude-cookbooks' README as a marketing surface would be a regression if Sync's `docs/` folder
adopted its structure.** The README's "Table of recipes" (lines 29-63) is a curated, promotional
index — real content, arranged for browsing appeal rather than for getting someone to a running
environment — and the actual engineering path lives in a file (`CLAUDE.md`) addressed to an AI
agent rather than a human reader. Sync's `CLAUDE.md` already avoids this split: it is simultaneously
the binding instructions for an agent and the document a human maintainer would read to understand
the project's constraints, because the project treats "binding rather than advisory" as a property
of one document, not two. Splitting Sync's onboarding path the way claude-cookbooks has (marketing
README, real setup buried in an agent-facing file) would be the wrong direction to take from this
comparison.

**superpowers' "no automated check, just a stated norm" approach to guide/code drift is a real gap,
not a strength, despite the project's overall rigor** — its own `CLAUDE.md` describes a 94% PR
rejection rate and a demanding contribution bar (`CLAUDE.md:7,11-20`), which makes it notable that
the one drift-prevention mechanism for its most safety-critical doc (the porting guide) is a sentence
asking the editor to remember, rather than a test. Sync should not read superpowers' overall
rigor as covering this specific dimension; the porting guide is exactly the kind of document Sync's
own binding-CLAUDE.md philosophy would insist on protecting with more than a sentence.

## 5. Open questions only the project's owner can settle

**Should Sync's rule files declare hard- versus soft-dependency the way `skills`' ADR does?**
Section 3 names the candidate split. Deciding which of the five `.claude/rules/*.md` files are
hard-dependency is a judgment call about what an agent can safely proceed without — a call the
project owner is positioned to make and a fresh reader of this note is not.

**Is a Sync-specific `architecture.md` worth writing now, or does it drift faster than the specs
that already carry the same information?** open-code-review's version stayed accurate against a
stable pipeline; Sync's remediation graph is still under active development per the M4 dashboard
work in progress elsewhere in this repository. A walkthrough doc written today risks becoming exactly
the kind of documentation this note flags as untested if nothing checks it against the code — which
argues either for writing it once the graph stabilizes, or for pairing it immediately with the
link-check style guard from Section 3 so staleness is caught rather than assumed away.

**Does Sync want a link/reference-integrity CI job at all, given the project is solo and self-funded
and every CI minute has an opportunity cost against the customer-facing pipeline the latency spec
prioritizes?** The mechanism in Section 3 is cheap to write and cheap to run, but "cheap" is not the
same as "worth the maintenance," and only the owner can weigh a rule-reference-checker against
whatever else that CI minute would otherwise buy.
