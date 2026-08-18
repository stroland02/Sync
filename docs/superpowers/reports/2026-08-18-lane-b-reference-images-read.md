# What the reference images actually say, for the Solution Workflow and the chrome

**Lane B, 2026-08-18.** The owner's verdict on the last pass was that the console *"doesn't look much
different from what was originally developed"*, and the diagnosis in the verbatim brief is that the
lane worked from prose about screenshots rather than from screenshots. This is what I found on
opening them, scoped to the surfaces Lane B owns: `features/workflows/**`, `layouts/**` and the app
chrome.

Images read so far: `supabase-02`, `-03`, `-05`, `-14`, `-17`, `superlog-02`,
`superlog-deep-01`, `coderabbit-04`, `greptile-03`.

## The single most useful thing in the reference set, and it arms our own refusal

`superlog-02` documents the confidence scalar we refuse — and documents what it *means*:

> *"The numeric `confidence` field uses a 0–10 scale where **10 means the agent found direct,
> verbatim evidence (a line of code, a matching stacktrace, a clear log message)**, and 0 means the
> finding is largely speculative. Treat scores below 4 as hypotheses to verify, not conclusions."*

**Their number is our provenance rung with the information thrown away.** A line of code is `static`.
A matching log or trace is `observed`. Speculative is `unresolved`. They compress a class of evidence
into a scalar and then have to write a paragraph telling you how to decompress it — including a
threshold ("below 4") that is itself an invented cut point.

This changes how the refusal should read on our screen. We are not declining to say how confident we
are and offering nothing in its place; **we render the fact their scalar is a lossy encoding of.** The
workflow screen should say so in one sentence rather than merely omitting a number, because the
omission is invisible and the argument is not.

Also refused there, and now with names: `rootCauseConfidence: high | medium | low` — the bucketed
form, which is the same claim with fewer digits — and `severity: SEV-1 | SEV-2 | SEV-3`, which is the
invented severity `CLAUDE.md` already refuses. We render the change kind the detector emitted.

## The state machine our reply box needs, and we do not have

`superlog-02` names five run states: `queued`, `running`, **`awaiting_human`**, `complete`, `failed`.
And:

> *"When the agent is in the `awaiting_human` state, your reply … will **resume the investigation in
> place — no new run is created**."*

That is exactly the interface `M10`'s resume-on-review-comment needs, and it names the missing piece:
**a reply box is only meaningful against a state that says the run is waiting for you.** Ours renders
a disabled box because no write route exists — correct — but it should also say *whether the run is
in a state where a reply would do anything*. A reply box on a `complete` run is a different refusal
from a reply box on a run that is waiting.

Two further fields worth having, both derivable in principle and neither invented:
`resumeCount` (how many times a human turn re-entered this run) and `cumulativeRuntimeMinutes`
(compute time summed across segments). Note the second is **not** wall-clock elapsed — which is why
our rail was right to refuse a duration: a run parked on a customer's CI accrues wall-clock and no
compute. Their field is the honest version of the number we declined to invent.

## Structures to take for the workflow screen

**From `coderabbit-04`, the finding view:**

- A file header carrying the path, with a collapse chevron, above **`Comment on lines +1930 to +1933`**
  — the anchor stated in words, not only implied by a gutter.
- The change rendered as a real diff: line numbers, `+`/`-` gutter, red and green grounds.
- Two disclosure sections below the prose, each with its own copy control: **"Committable suggestion"**
  and **"Prompt for AI Agents"**. The second is precisely the *copy the agent prompt* action our rail
  renders disabled.
- An **IMPORTANT** callout inside the suggestion, telling the reader to review before committing.
  That is our *nothing reaches a pull request unverified* position, rendered.

**From `greptile-03`:** an *Important Files Changed* table — filename against what changed in it, one
row per file, prose in the second column. Directly usable for a patch review, and it is the part of
that screen worth taking; the `Confidence Score: 1/5` above it is the part that is not. Worth noting
the bullets *underneath* their score are the real content — the reasons. Keep reasons, drop scalar.

## Chrome, which is the other half of Lane B

**The rail is icons only.** `supabase-02` and `-03` show a ~42px icon rail with no labels and **no
section headings whatsoever**. Ours carried thirteen headings for eleven rows before tonight. That is
the largest single reason the console read as unchanged.

**But headings are not banned — they live in the second tier.** `supabase-05` shows the expanded
panel carrying four quiet section labels (`DATABASE MANAGEMENT`, `ACCESS CONTROL`, `CONFIGURATION`,
`PLATFORM`) over roughly fifteen rows. So the correct ratio is about four sections to fifteen rows,
not thirteen to eleven. `M14-W380` cut ours to two over eleven, which is inside that band. **Zero
would have been wrong**, and I would have got there from the prose alone.

**One unresolved conflict, and I will not resolve it silently.** In every Supabase shot the top bar
spans the **full width above** the sidebar. The owner's earlier instruction was the opposite — sidebar
full height, top bar not in front of it — and that is what `M14-W366` built. The reference and the
ruling disagree. The ruling stands until the owner says otherwise; this is recorded so nobody
"fixes" it toward the screenshot without noticing it reverses an instruction.

## One image is unreadable

`superlog-deep-03-documented-five-run-states.png` renders as a solid dark frame with no content. The
five states it was captured for are legible in `superlog-02` instead, so nothing is lost — but the
file should be re-captured or deleted rather than left as a reference nobody can read.

## What this changes in Lane B's queue

1. **Say the refusal, do not merely perform it.** The workflow screen renders the rung; it should also
   carry one sentence saying that the rung is what a confidence score compresses, because the
   omission is invisible to a reader who has seen the competitor.
2. **The reply box should name the run's state**, not only the missing route. Waiting-for-you and
   finished are different refusals.
3. **The node cards should carry a real diff and a file anchor in words**, with copy controls on the
   agent prompt and the suggested change.
