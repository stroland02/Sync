# Competitor interfaces — what an operator console in this space actually looks like

Audited 2026-08-04 by driving a real browser against six live products. Screenshots referenced
below live in `docs/superpowers/references/screenshots/` in this worktree and are the durable
record; every claim carries a source URL or a screenshot filename and one of three labels.

**VERIFIED** means I loaded the primary source in this session and read it.
**REPORTED** means a secondary source asserts it and I did not confirm it against the product.
**INFERENCE** means it is my own reasoning from what I saw.

---

## 1. What this reference actually is

This is not one reference but a survey of six shipping products whose interfaces a reviewer will
compare Sync's operator console against: CodeRabbit and Greptile (AI pull-request review),
Devin (autonomous coding agent), Stage (a code-review reading surface), Superlog (agentic
observability that turns incidents into fix PRs), Pentagon (a canvas for coordinating agent
teams), and Ara (a session-and-automation platform for agent-authored changes). Three of them —
CodeRabbit, Greptile, Superlog — ship an artifact that is structurally the same thing Sync's
Finding and Solution Workflow views are trying to be: a machine-produced claim about a codebase
with evidence attached and a repair proposed. The survey answers one question: when a competing
tool has to convince a human that its claim is true, what does it actually put on the screen.

The short answer, which the rest of this note substantiates: **all six ask for more trust than
Sync intends to ask for, and none of them renders its own agent's trajectory as a sequence with
per-step state and per-step evidence.** Greptile renders a sequence diagram, but of the
*customer's* code, not of its own run. Superlog names its run states in documentation but exposes
them as a single field, not a walkable path. That gap is real and it is Sync's stated
differentiator, so it is worth being precise about where it actually lies.

---

## 2. What Sync should adopt

### 2.1 A confidence scale defined in terms of the kind of evidence found — Superlog

Superlog's `rootCause.confidence` is a 0–10 number, and the docs define the endpoints by evidence
class rather than by feeling: "10 means the agent found direct, verbatim evidence (a line of code,
a matching stacktrace, a clear log message), and 0 means the finding is largely speculative. Treat
scores below 4 as hypotheses to verify, not conclusions."
(VERIFIED — https://docs.superlog.sh/concepts/agent-runs, captured in
`superlog-02-agent-run-states-and-result-fields.png`.)

This is the same idea as Sync's binding rungs — `static`, `resolved`, `observed` — but expressed
as an operator-facing threshold rule. Sync's rung is stronger as a data model, because it is a
column the write path refuses to omit (`.claude/rules/graph-grain.md`, `CLAUDE.md`), where
Superlog's is a number an LLM emits. What Sync is missing is Superlog's *sentence*: a plain-English
line in the interface telling a reviewer what to do differently at each rung. Where it lands: the
findings table in the console, as a legend or a hover on the rung chip — "a `static` binding means
the call site was matched by source analysis alone and nobody has watched it run."

### 2.2 Machine-readable abandonment reason codes, surfaced by name — Superlog

Superlog closes an incident with either `noiseClassification` (values such as `cosmetic_log_only`,
`expected_third_party`) or `resolutionClassification` (`fixed_in_current_code`,
`transient_condition_cleared`), and the incident status moves to `autoresolved_noise` or `resolved`
with the reason code `agent_classification`.
(VERIFIED — https://docs.superlog.sh/concepts/agent-runs, same screenshot.)

This is direct external precedent for Sync's "abandoned runs are data" rule, and it goes one step
further than Sync currently does by making the reason a small closed vocabulary rather than free
text. Where it lands: `abandon_reason` should render in the Solution Workflow view as the literal
code plus a one-line gloss, and the vendor findings table should be filterable by it. A reviewer
who can filter to "everything we abandoned for reason X" is doing the routing analysis the pipeline
discipline spec says abandoned attempts exist to enable.

### 2.3 A run-state vocabulary that includes waiting on a human — Superlog

Superlog's agent run states are `queued`, `running`, `awaiting_human`, `complete`, `failed`
(with a `failureReason`), and resumes are counted in `resumeCount` with
`cumulativeRuntimeMinutes` tracking total compute across all segments.
(VERIFIED — https://docs.superlog.sh/concepts/agent-runs.)

Two things worth taking. First, `awaiting_human` is a state Sync's node vocabulary does not have
and probably needs: a run that is neither running nor abandoned but blocked on a decision reads as
"stuck" today. Second, `resumeCount` validates the attempt counter Sync's workflow view already
shows for the `patch` node — Superlog independently concluded that a re-entered run must display
how many times it re-entered, because otherwise the reader mistakes a loop for progress.

### 2.4 A finding row that is file path + category + a one-sentence claim, and nothing else — Greptile

Greptile's public examples grid renders each finding as: repository header (stars, forks, repo
count), the file path, a single category tag (`GPU`, `LOGIC`, `SECURITY`, `PERFORMANCE`,
`CONCURRENCY`, `DATA INTEGRITY`), the agent name, a one-line title such as "Unbalanced CUDA release
wipes context", and a "SEE PR" link. No severity number, no confidence, no snippet.
(VERIFIED — https://www.greptile.com/examples, captured in `greptile-02-examples-index.png`;
row composition confirmed by reading the card DOM text in-session.)

The titles are the lesson. Every one is a verb phrase asserting a consequence — "Undefined method
breaks every step()", "Mid-loop overflow leaves orphaned keys", "O(1) optimization is a silent
no-op". None is a category restated ("possible null dereference"). Where it lands: Sync's vendor
findings rows should carry a generated consequence sentence, not the detector name. A row reading
`response-property-removed` tells an operator nothing; "Stripe stopped returning `charge.outcome`
and three call sites read it" tells them whether to click.

### 2.5 A provenance block that names which knowledge source fired and which file it hit — CodeRabbit

Under a collapsible "📜 Review details", CodeRabbit lists: the configuration used ("CodeRabbit UI"),
the review profile ("CHILL"), the plan tier ("Pro"), which knowledge-base sources were *disabled*
and why ("Linear integration is disabled by default for public repositories"), the exact commit
range reviewed (`b7d3f5a` to `008a990`), the files selected for processing with hunk counts, then
"Additional context used" broken into "Path-based instructions (3)" — each naming the rule file it
came from, e.g. `.cursor/rules/building-bun.mdc` — and "Learnings (4)", each with the source PR,
the source file, an ISO timestamp, the learned rule, and an "Applied to files" list.
(VERIFIED — https://github.com/oven-sh/bun/pull/23053, captured in
`coderabbit-03-inline-finding-and-review-details.png`.)

This is the single best evidence surface in the survey, and it is worth studying closely because it
is *not* a confidence score. It is a list of inputs with their origins, which lets a reviewer
reconstruct why the tool said what it said and, critically, notice when a relevant source was
switched off. Where it lands: the Finding detail view. Sync's equivalent list is the vendor change
that triggered detection with its `raw` payload and signature origin, the call sites with their
rungs, the telemetry window that produced the `observed` rung, and — the part nobody else does —
which detectors did *not* run and why. Disabled sources being stated explicitly is the detail to
steal.

### 2.6 Progress steps that are clickable and bound to the tool state at that moment — Devin

Devin's docs state: "You can find Devin's tools in the sidebar or by clicking any progress steps in
the session." Its January 2025 release note describes a Follow-Devin tab showing "each action Devin
took (e.g. 'Edited github.py')", "Devin's thoughts explaining why the action was taken", and "any
editor diagnostics errors present after the action was taken (in red)", with up/down arrow keys to
step through the sequence.
(VERIFIED — https://docs.devin.ai/get-started/devin-intro and
https://docs.devin.ai/release-notes/2025, read in-session; the docs page is captured in
`devin-02-docs-interface-progress-steps.png`.)

This is the interaction model for Sync's Solution Workflow view: the node list is not a static
summary, it is an index into recorded state. Clicking `static_verify` should show the compiler
output that node produced; clicking `await_ci` should show the CI run it waited on. Sync already
stores this — the checkpointer holds it — so the work is exposing it, not capturing it.

### 2.7 A finding detail that opens with why-this-exists, not with the diff — Stage

Stage's PR view opens with a "Prologue" section whose sub-headings are, verbatim: WHY THIS PR? /
ROOT CAUSE / WHAT IT DOES / KEY CHANGES / REVIEW FOCUS. The Review Focus items each name a file and
state a consequence — "RBAC middleware rewrites the auth path · `rbac-middleware.ts` · In-flight
sessions need to be backfilled into the new role table before deploy, or requests will 403."
Only below that come numbered Chapters with their own `+214 −63` counts.
(VERIFIED — https://stagereview.app/, captured in `stage-02-pr-prologue-chapters.png`; full
section text read from the extracted page markdown.)

Where it lands: Sync's Finding detail. The natural instinct is to lead with the vendor spec diff.
Stage's ordering is better for an operator who has fifteen findings to triage: root cause first,
consequence second, evidence third. "ROOT CAUSE" and "REVIEW FOCUS" map almost exactly onto "which
vendor change" and "which call sites are dangerous".

### 2.8 A one-line human-memorable name for every finding — Superlog

Every Superlog incident carries a `codename`, described as an "auto-generated human-friendly name
(e.g. `squishy-narwhal`)" alongside its `title`, `status`, `severity`, `service`, `environment`,
`firstSeen`, `lastSeen`, and `issueCount`.
(REPORTED — https://docs.superlog.sh/concepts/incidents, read via WebFetch rather than in the
browser; field names quoted from that fetch and not independently confirmed against the rendered
page.)

Small but load-bearing. Incidentally observed this session: Sync's own running console renders a
finding as its raw 32-hex identifier in both the page heading and the breadcrumb. Two people cannot
discuss `11111111111111111111111111111111` on a call. A codename column costs nothing and makes the
console usable in conversation.

### 2.9 An acceptance checklist stated as four things to look at — Ara

Ara's docs define a session as keeping "the prompt, conversation, commands, changed files, checks,
and change request together", and then state a literal checklist: "Before accepting a result,
check: changed files and the final diff / commands and test results / screenshots or other evidence
/ the pull request or merge request."
(VERIFIED — https://ara.so/docs/guides/overview, captured in
`ara-01-sessions-and-automations.png`.)

Where it lands: this is the spec for what the Solution Workflow view must be able to hand a
reviewer without leaving the page. Sync's eight nodes already produce three of these four
(`patch` → the diff, `static_verify` and `await_ci` → the checks, `open_pr` → the PR). The one
Sync has and Ara does not is the vendor evidence at `locate`. Worth checking each node against
this list and asking what a reviewer would still have to go elsewhere for.

---

## 3. What to deliberately skip

### 3.1 Pentagon's spatial canvas — skip, and it is the clearest skip in the survey

Pentagon is a workspace for coordinating teams of AI agents: a zoomable canvas where each agent is
a node with a "status ring" (green pulsing = active, no ring = idle), "sticky notes" connected by
dashed lines showing summary / task progress / blockers, and a `3/7` task-progress badge that only
renders at sufficient zoom.
(VERIFIED — https://docs.pentagon.run/agents/status, captured in
`pentagon-02-agent-status-rings-sticky-notes.png`; landing page in `pentagon-01-landing.png`.)

**This does not apply to Sync, because Sync's graph is a data lineage, not a social org chart.**
Pentagon's canvas answers "who on my team is busy right now"; Sync's console answers "which call
site depends on which vendor operation and how do I know". A zoomable free-position canvas is the
wrong primitive for a fixed eight-node linear pipeline, and the specific cost of adopting it is
high: canvas layout means a layout engine, pan/zoom state, and per-zoom-level content rules
(Pentagon's own docs admit sticky notes and badges disappear when zoomed out), all to render a
sequence that a plain vertical list renders perfectly. Take exactly one idea from Pentagon and
leave the rest: the *absence* of decoration on idle nodes. "Idle agents show no ring at all — they
fade into the background so active work stands out" is a good rule for a workflow view where five
of eight nodes are `not started`.

### 3.2 A single-number confidence score on the finding — skip

Devin shows a three-colour Confidence Score (🟢 🟡 🔴) at the start of a session, after creating a
plan, and whenever it answers a question about the code, and gates autonomous execution on it:
"When Devin doesn't have 🟢 confidence (i.e., 🟡 or 🔴), it will now wait for user approval before
proceeding with its plan."
(VERIFIED — https://docs.devin.ai/release-notes/2025, captured in
`devin-03-confidence-scores-release-note.png`.)
Greptile shows "Confidence Score: 1/5" with a one-line verdict ("Not safe to merge — `_apply_rubric`
is undefined and will crash every `step()` call at runtime"), a justifying paragraph, and the list
of files driving the score.
(VERIFIED — https://github.com/meta-pytorch/OpenEnv/pull/437, captured in
`greptile-03-pr-summary-confidence-score.png`.)

Greptile's version is defensible because the score is immediately followed by the three files that
caused it. Devin's is not: a 🟡 is an assertion with nothing behind it. The cost of adopting a
scalar confidence on a Sync finding is that it competes with the rung and loses — the rung is a
fact about how the binding was established and the write path enforces it, while a score is a model
output nobody can audit. Two numbers meaning roughly "how much should I trust this" on the same row
is worse than one. **Skip the score; keep the rung, and borrow only Greptile's habit of naming the
specific artifacts that drove the verdict.**

### 3.3 Greptile's per-PR Mermaid sequence diagram — skip for the customer's code, reject the temptation for Sync's own run

Greptile's summary comment ends with a `Sequence Diagram` heading whose body is a Mermaid
`sequenceDiagram` of the customer's runtime control flow, complete with `loop` and `alt` blocks and
six participants.
(VERIFIED as source text — the mermaid block is present in the page HTML I captured, beginning
`sequenceDiagram / participant User / participant LocalRLMRunner / ...`, from
https://github.com/meta-pytorch/OpenEnv/pull/437. **Could not verify visually**: the diagram did
not render for a signed-out viewer in my session, so
`greptile-04-comments-outside-diff-and-unrendered-sequence-diagram.png` shows the heading with an
empty canvas below it. That failure is itself a finding — the flagship visual asset of that comment
is invisible to anyone not logged in.)

The cost of a Mermaid render inside the console is a diagramming dependency and an auto-layout
engine, for a payload whose correctness nobody can check. More importantly it would be the wrong
diagram: Greptile draws the customer's code flow, which Sync has no claim to. Sync's sequence is
its own eight nodes, and eight nodes in fixed order want a list with per-node state, not a
generated graph. A list is also honest about retries in a way a sequence diagram is not — a node
visited twice is two rows, whereas a diagram either hides the loop or fakes it.

### 3.4 CodeRabbit's "Prompt for AI Agents" copy-block — skip for now

Each CodeRabbit inline finding ends with a collapsible "🤖 Prompt for AI Agents" containing a
prose instruction written for a coding agent to consume ("In `src/bun.js/VirtualMachine.zig` around
lines 1930 to 1933, the current guard uses the struct field `this.is_main_thread` which defaults to
false and is never set, so the cleanup for transpiler and auto_killer never runs; change the guard
to call `this.isMainThread()`…"), above a "📝 Committable suggestion" block with a one-click diff.
(VERIFIED — captured in `coderabbit-04-finding-severity-suggestion-agent-prompt.png`.)

This exists because CodeRabbit stops at the suggestion and hands the repair to somebody else's
agent. Sync does not stop there — it patches, typechecks, replays, pushes, waits on the customer's
CI, and opens the PR. Shipping a copy-a-prompt button would advertise the one thing Sync is
deliberately not: an advisor. The cost is not the button, it is the positioning.

### 3.5 The finding row that shows a severity word and hides everything else behind a click — skip

CodeRabbit's inline finding leads with `⚠️ Potential issue | 🟠 Major` and a bolded title
("`is_main_thread` guard never fires"), with the reasoning, the suggested diff, the committable
suggestion and the agent prompt all one click down.
(VERIFIED — `coderabbit-04-finding-severity-suggestion-agent-prompt.png`.)

The severity chip is fine. What is not worth copying is the depth: on that page, understanding one
finding required opening seven separate `<details>` elements, and the provenance block that
justifies the claim sits in a *different* collapsible from the claim itself, attached to the review
rather than to the finding. Sync's console is a page, not a comment thread crammed into GitHub's
markdown; it can put the rung on the row and the evidence beside the claim rather than under it.
The cost of copying the collapsible-everything pattern is that "we show our work" becomes "we show
our work if you click seven times", which is not a differentiator.

### 3.6 Login-gated surfaces I could not reach — stated, not smoothed over

**Could not verify:** CodeRabbit's own web dashboard (`app.coderabbit.ai`), Greptile's dashboard
(`app.greptile.com`), Devin's session UI (`app.devin.ai`), Stage's reviewer dashboard, and
Superlog's incident list are all behind authentication and I did not have accounts. Everything
above about those products comes from public PR output, marketing mockups, or vendor documentation.
The consequence: I can describe how CodeRabbit and Greptile present a finding *inside GitHub* with
high confidence, and how any of them presents a finding *inside its own console* with low
confidence. Where a claim rests on a marketing mockup I have said so.

`docs.coderabbit.ai/guides/reports-overview` contains no product screenshots at all
(VERIFIED — I queried the page for `main img` and got an empty list), so the reports UI could not be
inspected either.

---

## 4. Answers to the reconnaissance questions

**How each presents a finding.** CodeRabbit: severity chip + verb-phrase title on the surface,
reasoning + suggested diff + committable suggestion + agent prompt behind clicks, and the review
configuration behind a different click (`coderabbit-04-…png`). Greptile: file path + category tag +
one-sentence consequence, nothing else, with the whole finding behind a link
(`greptile-02-examples-index.png`); on the PR itself, a "Key issues found" bullet list where each
bullet already contains the file, the line numbers, the mechanism and the consequence
(`greptile-03-…png`). Stage: findings are "Review Focus" items — title, file, and a sentence about
what breaks if you skip it (`stage-02-…png`). Superlog: a structured record with `summary`,
`rootCause.text`, `estimatedImpact.text` and a `severity` of SEV-1/2/3
(`superlog-02-…png`). Never shown by anyone: which detectors ran and found nothing, and what the
tool chose not to look at.

**How each presents evidence.** CodeRabbit is the only one that itemises its inputs — commit range,
files processed, rule files consulted by path, prior learnings with timestamps and source PRs,
and which knowledge sources were disabled (`coderabbit-03-…png`). Greptile shows its work in prose:
it names line numbers, quotes the offending regex against the correct one, and keeps a "What is
fixed in this PR vs. prior threads" section that credits the author for earlier rounds
(`greptile-03-…png`). Devin and Pentagon ask for trust — a colour and a status ring respectively.
Ara asks the *human* to check four things rather than showing them
(`ara-01-…png`). Superlog is the only one that publishes what its confidence number means in terms
of evidence class. **Nobody shows an attempt that failed.** Greptile comes closest by referencing
prior threads, and CodeRabbit by showing a failed pre-merge check with an Explanation and a
Resolution column (`coderabbit-02-…png`), but neither keeps a discarded repair visible with the
reason it was discarded.

**How each presents a multi-step process.** The honest answer is: barely. CodeRabbit's pre-merge
checks table is the best per-step rendering in the survey — a real table with columns
Check name / Status / Explanation / Resolution, split into "❌ Failed checks (1 warning)" and
"✅ Passed checks (2 passed)", where the failing row carries both why it failed and what to do
(`coderabbit-02-walkthrough-premerge-checks.png`). That is a set of independent gates, not a
sequence. Devin is the only product that renders an agent trajectory as a walkable sequence — action,
the thought explaining it, and the diagnostics after it, steppable with arrow keys — but that lives
behind login and I could only read its description. Superlog names five run states in a table but
exposes one at a time. Greptile renders a sequence diagram of the customer's code, not of its own
run. Ara says "Automation activity lists every execution. Select a row to open the session behind
it", which is a list-to-detail drill, not a per-step view.

**Provenance and confidence.** CodeRabbit: provenance yes (sources named by path), confidence no.
Greptile: confidence yes (1/5 with justification and driving files), provenance partial (it names
the commits and files but not which rules or memories fired). Devin: confidence yes (🟢🟡🔴),
provenance no. Superlog: both, as typed fields — `rootCause.confidence` 0–10 with an evidence-class
definition, plus `pr.validationPassed` as a boolean asserting local checks ran before the PR opened.
Stage: neither, but its assistant is described as citing "the exact files and lines they came from".
Pentagon: neither; status rings are liveness, not epistemics.

**Layout and density.** Two shapes dominate. CodeRabbit and Greptile inherit GitHub's single
column and pay for it with nesting — CodeRabbit's finding needed seven `<details>` expanded before
it was legible. Stage and Devin use a three-region app shell: a narrow icon rail, a navigable
middle column (Stage's Chapters, Devin's session list), and a wide evidence pane, with a breadcrumb
across the top (`Dashboard / billing-service / Add subscription billing and RBAC #842`) and status
pills beside the title (`Open`, `Ready to merge`, `12/12 Checks`) — see `stage-02-…png` and the
hero in `devin-01-landing.png`. Density is high in the middle column and low in the evidence pane;
nobody uses a data grid. What everyone chose to leave off screen: timestamps (except Superlog's
`firstSeen`/`lastSeen`), cost, model identity, and any indication of what the tool declined to
examine.

**Concretely, for Sync's console.** Adopt: the evidence-class definition of a confidence level
(§2.1); named abandon reason codes with a filter (§2.2); an `awaiting_human` state and a visible
attempt count (§2.3); consequence-sentence finding titles (§2.4); an explicit inputs-and-disabled-
sources provenance block on the Finding detail (§2.5); clickable workflow nodes that reveal the
evidence that node produced (§2.6); root-cause-first ordering on the Finding detail (§2.7); a
codename per finding (§2.8). Reject: a spatial canvas (§3.1); a scalar confidence score competing
with the rung (§3.2); a generated Mermaid diagram (§3.3); a copy-this-prompt-to-your-agent block
(§3.4); collapsing evidence behind a chain of disclosure triangles (§3.5).

---

## 5. Which milestone or subsystem should consult this

**M4, the operator console — specifically the Solution Workflow view and the Finding detail.**
Read §2.6, §2.7 and §3.5 before deciding what goes on a workflow node and what goes behind a click,
and §3.1 and §3.3 before anyone proposes a canvas or a generated diagram. The question this note
answers for M4 is: *given that the product claim is "we show the remediation graph as it happened",
what does the competition actually show, and therefore what has to be on screen for the claim to
land?* Answer: a walkable per-node sequence with the evidence each node produced, and abandoned
attempts kept visible with their reason — because on the evidence gathered here, no competitor
renders either, and the two that come closest (Devin's steppable action list, CodeRabbit's
pre-merge checks table) do so for a different object.

**Secondary: whoever owns the `Finding` type and `abandon_reason`.** §2.2 and §2.3 are data-model
observations, not layout ones. If `abandon_reason` is free text today, the console cannot offer the
filter that makes abandoned runs useful, and Superlog's closed vocabulary is a working example of
the alternative.

**Not relevant to:** the signal stage, vendor adapters, or the latency architecture. Nothing in
this survey bears on those; the products examined either do not have vendor adapters or do not
publish anything about their pipeline shape.
