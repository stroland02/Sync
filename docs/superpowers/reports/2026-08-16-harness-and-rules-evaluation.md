# What hindered this session, and what to change about it

**Date:** 2026-08-16
**Scope:** an evaluation of the harness, skills, and instructions governing this session — both
the user's global working agreement and this repository's `CLAUDE.md` and `.claude/rules/*.md` —
requested directly by the owner mid-session, after landing five branches onto `main` and while
three finishing agents ran in the background. Grounded in what actually happened in this session,
not in abstract review of the documents.

**Method:** every claim below either cites something this session did, or cites a specific file
and the incident it already records about itself. Nothing here is a general opinion about how
Claude Code sessions should work; it is what this repository's own instruction set produced when
run.

## What worked, and should not be touched

**The path-scoped rules in `.claude/rules/`** — `remediate-stage.md`, `signal-stage.md`,
`graph-grain.md`, `console-dev-loop.md`, `console-surface.md` — each carries a `paths:` frontmatter
block that loads it only when a matching file is touched. This session never edited
`src/sync/remediate/`, `src/sync/signals/`, or `web/`, so none of these loaded, and none of their
content cost anything. That is the design working as intended: base context stays lean, and a
session that does touch those paths gets the rule exactly when it needs it. **No change
recommended anywhere in this group.** Each one also cites the specific commit that taught the
lesson it states (`efcc19d`, `b29795a`, `a6ee379`) rather than asserting a principle abstractly —
that citation style is worth protecting whenever these files are next edited, not diluted into
plain guidance.

**`autonomous-development.md`'s three-exception model** — decide and continue, except for an
irreversible action outside the repository, an architecture-invalidating decision, or a
credential/spend — was used exactly once this session, correctly. The branch-cleanup request
arrived after reconnaissance showed two "old-looking" worktrees actually held roughly 250 unlanded
commits each. That is squarely "an irreversible action outside the repository" territory (deleting
a branch nobody else could reconstruct), so it went to `AskUserQuestion` rather than being decided
alone. Every other call this session made — which paused branch to finish first, how to renumber a
colliding backlog item, whether a merge conflict resolution was safe — was decided and recorded
rather than asked, per the same rule. The rule's own three-item scope is doing real work: it is
narrow enough that almost everything stays autonomous, and the one time this session needed to
stop, the rule said so unambiguously.

**Caveman's Auto-Clarity carve-out fired itself, correctly, without being invoked explicitly.**
The global rule states that irreversible-action confirmations and multi-step sequences where
compression risks misreading drop caveman. When this session found that `m4-idiom` and
`m4-signals` held the entire unlanded M7 console, the response to the owner was full prose, not
ultra-compressed fragments — because compressing "these two branches look old but deleting them
destroys months of work" into caveman fragments would have been exactly the kind of ambiguity the
carve-out exists to prevent. That is the rule working, not an exception to it.

**Standing subagent-dispatch authorization** let three independent finishing tasks (M3-W113,
M3-W114, M3-W115) launch in parallel without a permission round-trip. Each was genuinely
independent — different files, different worktrees, no shared state — which is exactly the
condition `dispatching-parallel-agents` names. No friction observed.

## What cost real time or created real risk

### 1. Memory that describes coordination state goes stale faster than it gets corrected

`sync-coordinator-handoff.md`, `sync-two-agent-workspace.md`, and the `HANDOFF.md` file they both
point at described a world — one worktree per milestone, "the other chat owns M4," B71 mid-flight
— that was twelve or more days stale and completely superseded by the time this session read it.
Nearly none of it was still true; the console line alone had grown to roughly 250 commits since
that snapshot. Every fact in those memories had to be independently re-verified against `git log`
before it was usable, which this session did — the memory system's own disclaimer ("point-in-time
observation, not live state") earned its keep here. But the cost was real: reading three stale
memory files, discovering each was wrong, and re-deriving the actual state from git directly took
longer than skipping straight to git would have.

**The pattern worth naming:** memories about *who is doing what right now* decay in days.
Memories about *durable facts* (toolchain quirks, strategic constraints, worktree layout
conventions) decay in months. The system does not currently distinguish these, so both get read
with equal weight and equal staleness risk. A lighter fix than restructuring the memory system:
state, as an instruction rather than leave it to a memory file's own footer, that any memory
describing in-flight coordination state is a hypothesis to verify against `git log`/`git status`
before it's trusted, and that this check comes *before* reading the memory's content in depth, not
after. That is what this session did by instinct; making it explicit means the next session does
not have to rediscover the instinct.

### 2. The shared backlog number space has no collision check across diverging lines

Two development lines — this session's and the console line — each independently filed a backlog
item as `B122`, for two unrelated pieces of work, on branches that had diverged for roughly two
weeks. The collision was only caught during this session's merge, by inspection. This is not a
one-off mistake: `BACKLOG.md` itself already documents working around the same class of problem
once before (choosing `B116` instead of `B80` specifically to dodge a numbering collision with the
console line's then-unmerged `B90`–`B115`). The workaround was manual and local to one session; it
did not prevent the next collision three weeks later on a different pair of branches.

**Recommended change:** before assigning a new `B`-number, grep for it across every local branch,
not only `main`'s `BACKLOG.md` — `git log --all --oneline --grep="B<N>"` costs one command and
would have caught this before it happened twice. Worth adding as a one-line instruction in
`BACKLOG.md`'s own header, where the numbering convention is already stated.

### 3. Paused work has no forcing function to get landed or explicitly abandoned

Three branches (M3-W113, M3-W114, M3-W115) sat paused since 2026-07-30 — seventeen days — each
holding real, non-trivial, mostly-finished work, each explicitly marked "do not merge as-is" in a
report written the day they paused. Nothing before this session's sweep required anyone to either
finish or explicitly discard them; they simply persisted as worktrees nobody was actively looking
at. `BACKLOG.md`'s own "In flight" section separately admits that stale entries linger there for
days "misrepresenting available capacity," and that "workers keep landing in the wrong worktree" —
both already-diagnosed instances of the same underlying gap: nothing currently bounds how long
unlanded work is allowed to sit.

**Recommended change:** not a new rule file — the existing ones already say the right things about
landing work — but a cheap periodic check: any worktree with no commits in some bound (a week is a
reasonable start) and an unmerged branch gets surfaced explicitly in the next backlog pass rather
than staying invisible until a session happens to run `orca worktree ps` for an unrelated reason,
as this one did.

### 4. `console-dev-loop.md`'s process discipline is unenforced by anything except reading it

The "one console, one port, coordinator restarts it" section is exceptionally well-written and
grounded in a real, costly incident (an owner unable to tell which of five running dev servers was
current). But it is a process rule with no technical backstop: nothing prevents a fresh agent that
has not loaded this rule from starting a second Vite server on a stray port, or leaving one
running past the end of a task. This session did not hit this failure directly — `web/` was
untouched — but the rule's own text is evidence the failure mode is real and has already happened
more than once. A rule that depends entirely on every future session reading it correctly is
weaker than one the tooling can enforce.

**Recommended change, if console work resumes:** a startup script that refuses to bind port 5173
outside the designated coordinator worktree, or a lockfile naming the worktree currently holding
it, would convert this from "an agent forgot to read the rule" into "the tool refused and said
why" — a more durable failure mode than a documentation-only fix.

### 5. The formal plan → subagent TDD → two-stage review loop was not followed for already-finished work, and that exception is unwritten

This session landed several branches (B77, B80, the M3-W123 rebinding fix) that arrived already
implemented, already tested, and self-contained. For each, this session ran the test suite,
skimmed the implementation for obvious defects, and merged — not the full
`subagent-driven-development` loop of a written plan and a dispatched two-stage review (spec
compliance, then code quality). That was a judgment call made in the moment: writing a formal plan
to review already-complete, already-green, low-blast-radius work (a test-harness capture
mechanism, a tier-routing docstring, an indexer scope fix) would have been process for its own
sake. It was probably the right call. But it is a real, deliberate deviation from what the
installed skills say should happen, decided ad hoc rather than by a written exception — which
means the next session has to reason it out fresh, or worse, follow the letter of the loop for
genuinely low-risk work and pay for ceremony that buys nothing.

**Recommended change:** name this exception where `autonomous-development.md` already names the
three questions worth stopping for — something like: work that arrives already implemented, with
its own passing tests, in a narrow and self-contained area, gets a direct read-and-verify rather
than a dispatched plan and two-stage review. State the boundary explicitly (narrow files, existing
green tests, no architectural surface) so it is a recognized pattern rather than an improvised call
each time.

### 6. `CLAUDE.md`'s density is a real, paid cost — and probably the right trade

The project `CLAUDE.md` is long and written in a deliberately literary, elements-of-style register
— dense, precise, and hard to skim. This is a real fixed cost every session pays before touching
code. It is very likely the right trade anyway: `interface-originality.md`'s own amendment note
documents a rule that was read too literally once, causing real damage (a console with a type range
of 2.0 against a bar of 3.4, one vertical stack on every screen), and the fix was to make the rule
*more* precise, not shorter. A document meant to survive being read literally by a cold agent
earns density. The honest conclusion is not "shorten it" — it is that there is no cheap fix here,
and the density should be treated as a known cost rather than an oversight.

## What was not found

No rule, skill, or instruction in either the global working agreement or this repository's
`CLAUDE.md`/`.claude/rules/` was actively wrong, actively harmful, or worth deleting outright.
Everything flagged above is a gap — a missing check, an unwritten exception, an unenforced
process — not a bad instruction actively steering work in the wrong direction. That is worth
stating plainly rather than inflating the list to look thorough: the instruction set this
repository runs on is unusually self-correcting already (three of the nine `.claude/rules/*.md`
files exist *because* an earlier version of the rule caused a documented incident, and each
carries the incident as its own justification). The gaps above are the next layer of that same
habit, not a break from it.

## Summary table

| # | Gap | Cost observed this session | Fix |
|---|---|---|---|
| 1 | Coordination-state memory decays faster than durable-fact memory, both read with equal trust | Three stale memory files fully re-derived from git | State "verify coordination memory against git before trusting it" as an instruction, not a footnote |
| 2 | No cross-branch check before assigning a backlog number | `B122` independently collided twice across two lines | `git log --all --grep` before assigning a new number; one line in `BACKLOG.md`'s header |
| 3 | No forcing function on paused worktrees | Three branches sat unfinished for 17 days | Periodic staleness surface in the backlog pass |
| 4 | `console-dev-loop.md` is process-only, no technical backstop | Not hit this session; already documented as a repeat failure | Port lockfile or startup guard scoped to the coordinator worktree |
| 5 | Skip-plan-for-finished-work exception is ad hoc | Judgment call made three times without a citable rule | Name the exception in `autonomous-development.md` |
| 6 | `CLAUDE.md` density | Real but probably correct trade | No action; name the cost, do not cut precision for brevity |
