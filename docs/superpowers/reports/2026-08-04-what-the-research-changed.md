# What the research changed

Written 2026-08-04, closing the reference programme. It answers three questions the project's owner
asked: what was learned, what changed because of it, and whether it was worth the money.

**Reconciled 2026-08-05 against `a87cbf3`.** The findings and the cost accounting below are unchanged.
What changed is status: the design-system and slice-2 open questions have since been ruled, and the
fleet view named below as the biggest remaining gap has since shipped. The security finding has not
changed — it is still open, and still the most important row in this document.

## The verdict, first

**Worth it, but roughly half of what was spent was waste, and the waste was avoidable.** The research
produced four changes that reached the code, one security finding that has not been fixed yet and
should be, one design specification, and four process rules that will keep paying. It also cost
around 1.5 million subagent tokens, of which a conservative third bought nothing — one fan-out burned
618,000 in seventy seconds and returned a single usable note. The findings justify the programme; the
execution does not justify its price, and the fault was the orchestrator's design rather than the
research itself.

The sharpest thing to say about value is this: **the research's best single output was not a feature
idea. It was a security finding about Sync's own patch agent that nobody was looking for.**

## Why this research was commissioned

Restated from the original instructions, because a report that judges value has to judge it against
the goal that was actually set.

1. *"We are a solo dev trying to change the game"* — leverage what high-value companies already
   solved rather than rebuilding it.
2. *"Think about our processes as a benchmark that we need to CI"* — process quality as something
   measured, not asserted.
3. *"Embed this in the claude agent files so it is a hard-wired mindset"* — durable, not a document
   nobody reopens.
4. *"Add these resources into when we are building in milestones, so we look at them when needed and
   not all now"* — consulted per milestone.
5. *"Figure out what important features from each of these codebases we could utilise to make our
   product more efficient, higher quality and more extensive"*, and *"what is either nonsense or does
   not comply"* — adopt selectively, reject explicitly.
6. Later, and binding: **the interface is ours.** Concepts, ideas and efficient workflows transfer;
   screens do not.

Scored against those six: (1) met, (2) partly met, (3) met, (4) met, (5) met, (6) met and written
down as a rule. The gap is (2), and it is the most interesting gap in this report — see *Where the
position is not yet earned*.

## What was learned, and what changed

Every commit below was verified against `git log main..HEAD`.

| Finding | Source | What changed in Sync | Commit |
|---|---|---|---|
| A value two components must agree on needs one source of truth, and **no reference solves this** — `codebase-memory-mcp` carries the identical defect, a port duplicated between a C header and a Vite config | `engineering/configuration-and-secrets.md` | `DEFAULT_PORT` extracted in `src/sync/api/__main__.py`; a mirror test binds it to the target parsed from `web/vite.config.ts`, proven able to fail by mutating one side to 9999 | `ffdabfb` |
| Confidence is more honest when defined by the class of evidence behind it than by a feeling | `notes/competitor-interfaces.md` (Superlog's 0–10 scale, defined by evidence class) | **Nothing, deliberately.** The specification argues Sync's provenance rung already *is* the evidence-class claim, and is enforced where Superlog's number is only emitted. A numeric score would be false precision and would collapse `replay_outcome`'s deliberate three-way split | `b4b488d` |
| A reason for giving up should be a closed vocabulary, because free text cannot be aggregated | `notes/competitor-interfaces.md` (Superlog's `noiseClassification` / `resolutionClassification`) | Specification proposing sixteen codes, **derived from Sync's own routing predicates, not borrowed** — the shape transferred, the values did not. Awaiting the owner's ruling | `b4b488d` |
| A run-state vocabulary should distinguish liveness from disposition | `notes/competitor-interfaces.md` + the Critical's root cause | Specification moving `Disposition` to `sync.core.models` and deleting `running` from it. The instance was already fixed in `259906b`; the specification closes the class | `b4b488d` |
| Untrusted text reaching a model that can write needs a defence | `engineering/llm-engineering-practice.md` (PageIndex's three-layer defence) | **Not yet fixed.** Handed to the session that owns `src/sync/remediate/`. See below — this is the most important row in the table | — |
| A markup convention nobody validates drifts | `engineering/documentation-and-onboarding.md`, and two independent reviews | The evidence `<dl>` on the workflow view given a valid HTML5 content model, verified by rendering three payloads through an SSR entry and walking the emitted tree against the spec rule | `b553bd9` |
| A polyglot repository needs a gate on both languages, or the constants mirrored between them rot silently | `engineering/ci-and-release-engineering.md` | A `web` CI job pinning Node to the lockfile's exact `engines` floor, running `npm ci`, lint and build — `web/` previously had **no gate of any kind** | `0902571` |
| A test that has never been shown to fail has not been shown to test anything | `engineering/testing-strategy.md`, and the repository's own rule | The read-only guarantee moved from a grep that could not match `insert_finding` to a behavioural test with a recording fake, plus three mirror tests binding Python constants to TypeScript. All proven able to fail | `259906b`, `0a1c8bc`, `ffdabfb` |

Four findings reached shipped code. Two produced a specification awaiting a ruling. One was rejected
on the merits. One is a live security gap.

## The security finding, stated plainly

`engineering/llm-engineering-practice.md` records that PageIndex defends untrusted document text in
three layers — an injection-pattern list, delimiter framing with the smuggling bypass closed, and
system-prompt hardening — because it feeds PDF text to a model.

Sync's patch agent reads **vendor changelog text and customer repository contents**, and then edits
code. That is third-party text nobody at Sync controls, reaching a model with write access to a
customer's repository, with a pull request at the end of the pipeline. Sync has no equivalent
defence.

The mitigations that already exist are real but partial: every patch passes `tsc` and then the
customer's own CI, and `sync.index.shipped_tree` holds untracked and ignored paths out of the
compiled tree. Those constrain what a compromised patch can *ship*; they do not constrain what a
poisoned changelog can persuade the agent to *attempt*, and they do not cover an instruction that
produces code which compiles and passes tests.

This is the one finding that would justify the programme on its own, and it was found by an audit
dimension that existed only because the sweep was exhaustive.

## Learned and deliberately not acted on

**Rejected on the merits**, with the argument recorded:

- *A numeric confidence score.* The provenance rung already carries the evidence-class claim and is
  enforced by a column; a second axis would be false precision. Recorded in `b4b488d`.
- *Pentagon's spatial agent canvas.* Nothing in Sync's domain is spatial. Recorded in
  `notes/competitor-interfaces.md`.
- *Adopting a competitor's abandonment values wholesale.* The shape transfers; the values describe
  somebody else's product. Recorded in the specification and in `.claude/rules/interface-originality.md`.
- *A code generator or shared config file for the port.* Larger than the defect justifies. The house
  convention is that a constraint is enforced by something that fails, not by something that
  generates. Recorded in `ffdabfb`.

**Not done yet** — these are undone work, not decisions, and the distinction matters because undone
work masquerading as a decision is how a backlog rots:

| Item | Owner | Cost |
|---|---|---|
| Prompt-injection defence for the patch agent | the `src/sync/remediate/` session | Days. Needs a threat model first — which inputs, which boundary, what a refusal looks like |
| The abandonment vocabulary and `Disposition` move | Owner's ruling, then either session | A day, plus a migration decision for existing free-text rows |
| The two contradictions the specification found in `src/sync/remediate/` — `state.py` versus `tiered.py` on `NoPatchWarranted`, and `sync.mcp.propose` writing five values outside the `Outcome` literal | the `src/sync/remediate/` session | Hours each; the second now reads as a permanently in-flight run |
| Process-as-CI-benchmark, goal (2) above | Unassigned | The audit measured other people's processes but did not turn Sync's own into anything CI asserts |

## How the platform is different

**The honesty argument is now enforced rather than asserted.** Sync's position is that competitors
present a black box and ask for trust. Before this work the console *displayed* provenance; it now
*cannot omit it* — `bindingNullLabel` is a required prop, so rendering a null rung honestly is a type
error to forget rather than a convention to remember, and three call sites give three different
correct sentences. That is the product position expressed as a compile-time constraint.

**A live run can no longer lie about itself.** The Critical was not a rendering bug. Three modules
held three partial opinions about what states a run could be in, and the console read any non-null
outcome as terminal — so every live remediation displayed as a finished run that had decided to do
nothing. Sync was doing precisely what it accuses competitors of: a confident wrong verdict with the
reasoning hidden. Four task-level reviews missed it because each compared the client against the same
prose the client was written from.

**The interface is defensibly ours.** Twenty-two competitor screenshots sit in this repository, and
`.claude/rules/interface-originality.md` states why they are research and not a target — including
the argument that matters commercially: a console assembled from screenshots of black-box tools
inherits the assumptions that produced the problem and arrives looking like the thing it replaces.

### Where the position is not yet earned

- **The patch agent's untrusted-input surface.** Showing your reasoning is worth less if the
  reasoning can be steered by a hostile changelog.
- **Goal (2), process as a CI benchmark.** Sync asserts test discipline in prose and enforces it by
  review. The audit found no reference doing better, which is a comfort rather than an answer.
- **The console renders a run, not a fleet — this has since shipped.** `sync.dashboard.fleet`
  (`7f8661d`) added three read-only view models — runs, corpus summary, repositories — and
  `f6fbc93` put routes over them. `12cbaf0` built the fleet screen and made it the console's index
  route, moving the earlier overview to `/codebase`; `7535fbf` fixed it to render `abandon_reason`
  where it had claimed to but did not. The gap this bullet named is closed.

## What it cost, and what it should have cost

Approximately **1.5 million subagent tokens** across the programme.

The avoidable waste:

- **The audit was structured one agent per dimension**, so each of eleven agents read all nine
  repositories — roughly ninety-nine repository reads where nine would have done. Splitting by
  repository, then asking dimension questions of a shared reading, would have cost a fraction. This
  was an orchestration design error, not an inherent cost of the research.
- **A fourteen-agent fan-out relaunched into an exhausted account limit** burned 618,000 tokens in
  seventy seconds; twelve agents failed on the same error and one note survived. Re-dispatching into
  a limit re-runs failed agents rather than skipping them.
- **The closing report agent burned 383,000 tokens** re-reading nineteen notes before dying on a
  limit. This report was then written directly from the commit history at a fraction of the cost,
  which is itself the lesson.
- **Five session restarts** killed background agents mid-flight. The eventual fix — dispatching
  synchronously so work completes inside a turn — should have been the first response rather than the
  fourth.

Honest comparison. The same spend aimed directly at implementation would have produced perhaps two to
three more console features. Against that, the research produced one unlooked-for security finding, a
defect class closed structurally, a CI gate on a language that had none, and four process rules that
change how every future round is run. **Features would have been more visible. This was worth more —
but it would have been worth the same at roughly half the price.**

## What to do differently

Already written down in `docs/superpowers/ORCHESTRATION.md`:

- Width is the most expensive choice an orchestrator makes, and it costs the same whether or not it
  works.
- Model tier by role; the top tier is for whole-branch review and architecture, not for mechanical
  diffs.
- Never re-dispatch into a limit.
- A scheduled tick is capped and may not launch a workflow.

New, from this programme, and not yet written down:

- **Shard a survey by the thing being read, not by the question being asked.** Nine repositories read
  once beats eleven questions each re-reading nine repositories.
- **Dispatch synchronously when the session is unstable.** Background agents do not survive a restart;
  five were lost before this was learned.
- **Write the closing report from the commit history, not from the source material.** The evidence for
  "what changed" is the diff. Re-reading every note to write a summary costs more than the summary is
  worth.
- **A negative finding is a deliverable.** "None of the nine references solves this, and one carries
  the identical defect" was what justified building the port guard instead of hunting for a library.

## Decisions for the owner

| Decision | Recommendation |
|---|---|
| Fix the patch agent's prompt-injection exposure | **Yes, and first.** Write a threat model before code — which inputs are untrusted, where the boundary sits, what a refusal looks like |
| Accept, amend or reject the run-state and abandonment specification | Accept the `Disposition` move and the sixteen codes; leave existing free-text rows NULL rather than backfilling |
| Merge `m4-dashboard` to `main` | Yes. Merge gate is green, twenty-two commits, tree clean. Not done here because pushing is the human's |
| Fund another research round | Not now. The next round should be one repository per agent and aimed at one question — the fleet-level view is the strongest candidate |
| Turn process into a CI benchmark, goal (2) | Worth a small slice. Start with one measurable claim, such as every new test being shown to fail before it is trusted |
