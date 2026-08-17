# Gate 3 against an empty graph — the state a design partner sees first

Signed: 2026-08-17T13:14:37-04:00

**Re-signed at 13:14:37 to cover `M14-W349`** (the retry affordance, committed 13:13:59), which
touched `web/src/components` and twenty feature files and so moved the console after the previous
signature at 12:54:34. It is signed rather than re-walked, and the reason is checkable rather than
asserted: the diff over `web/src/features` contains **only** the `ErrorState` invocation gaining an
`onRetry` prop — verified by filtering the commit's feature-file diff for lines not containing
`onRetry` and getting nothing back. The change adds a control and asserts no figure, so no claim
this gate measures could have moved. The rendered result was observed on the built console during
the same session: with the API killed the failure showed "Try again" beside its explanation, and
with the API restored a click recovered the panel without a page reload.

The original signature for this walk follows.

Signed-original: 2026-08-17T12:54:34-04:00

That is a real clock reading taken after `M14-W346` landed at 12:54:13, not a round number chosen
to look tidy. It has to fall after the fix commit: the fix changes `web/src/features`, so a
signature dated before it would describe a console one commit older than the one it claims to
cover — the same staleness this gate catches, self-inflicted.

Every previous Gate 3 walk ran against `scripts/seed_console.py`'s fixture; the first pass names
`seed-console` twenty-eight times. **A design partner's first five minutes are the opposite state**
— configured, nothing indexed, every table empty — and until now nobody had looked at it. This
walk is that state, and it extends the Gate 3 signature to cover it.

**Result: one real defect, found and fixed. Two screens were already right, and one behaviour the
stock-take suspected turned out to be already correct.**

## How the state was stood up

A **separate database**, `sync_empty_walk`, created and schema-applied through `GraphStore.apply_schema`,
rather than truncating the shared graph — Postgres on 5433 is shared with five other lanes, and
emptying their data to look at a screen would be the most expensive possible way to answer this.
Verified before walking: **9 tables, 0 rows across all of them.** The API ran against that DSN and
the console was served from the production static server behind the credential gate, so this walk
covers the empty state *and* the runtime a partner is served, at once. The database was dropped
afterwards.

## The defect: Fleet's open-findings tile read as a clean bill of health

Measured on the empty graph, before the fix:

| Tile | Value | Note |
|---|---|---|
| **Open findings** | **0** | **"Across every vendor, every repository."** |
| Runs | 0 | "One per checkpoint thread, not one per finding." |
| Repositories indexed | 0 | "Holding at least one call site. Never indexed has no row." |
| Repair attempts | 0 | "One row per attempt. 0 detectors have open findings." |

**Three of those four zeros are honest and one is not.** Runs and repair attempts count events, and
zero events genuinely occurred. Repositories-indexed already carries the distinction in its own
note, and carries it well.

Open findings is the defect. `0 across every vendor, every repository` describes a search that
covered everything and found nothing. On an unindexed graph no call site has been read, so nothing
*could* have been found — the number is arithmetically true and the sentence beside it asserts a
measurement that never happened. **That is absence rendered as zero, on the exact axis this console
exists to argue about, on the first screen of a partner's first session.**

A reader could in principle infer the truth from the sibling tile two positions away. That is
precisely the inference this console refuses to make readers perform: every figure names its own
scope, which is why the flaw is in this tile rather than in the rail.

**Fixed** in `web/src/features/fleet/fleet-facts.tsx` (`openFindingsNote`), test-first. With nothing
indexed the note now reads:

> No repository has been indexed, so nothing has been searched — this is not a measurement that
> found nothing.

The ordinary scope note returns as soon as one repository is indexed, and the bounded-scan
qualification still wins where it applies, because a count that stopped early is a floor whatever
the index holds. Both branches are covered by tests, and the fix was confirmed on the running empty
console rather than only in the suite.

## What was already right, stated with the evidence

These are worth showing a partner rather than merely not complaining about.

**Detector attribution (`/detectors`) — zero bare zeros.** It renders, verbatim:

> No open finding is attributed to any detector. The API answered, and the graph holds no open
> findings in this scope right now. That is an answer, not a failure — nothing indexed here is
> currently flagged by any detector.

It distinguishes an empty answer from a failed one *in the sentence itself*, which is the whole
question this walk was sent to ask.

**Settings — zero bare zeros.** The adapter table renders `Nothing received` rather than `0`, over
a heading that states the rule: *"An adapter with nothing received has never delivered, which is
not the same as having delivered nothing — a vendor Sync watched and found unchanged reports a
count."*

## The failed-fetch question, answered — and the hypothesis disproved

The dispatch asked whether "a failed panel offers no way to re-ask" and "a reader cannot tell a
failed fetch from an empty graph" might be the same defect wearing two hats. **They are not, and
the evidence is direct.** With the API killed and the console left running, Fleet renders:

| State | What the figure shows |
|---|---|
| Empty graph, API healthy | `0`, with "No repository has been indexed…" |
| API unreachable | `— the API did not answer` |

**Zero bare zeros in the failure case.** The console already distinguishes the two states, and it
distinguishes them where it matters — in the figure slot, not in a banner a reader might miss.

So the stock-take's item stands but shrinks: the console **says** which state it is in, it simply
does not offer recovery from the failed one. That is a smaller, separate defect about affordance
rather than honesty, and it should not be conflated with this walk's finding.

## Verdict

**Gate 3 extends to the empty state.** After the one fix, no screen reachable on an empty graph
reads zero where it means never-measured, and the two screens that were already right say so in
their own words rather than by omission.

The signature above covers both the seeded database and the empty one. The seeded evidence is in
`2026-08-17-gate-3-screen-pass.md` and `2026-08-17-gate-3-resign.md`; this file is the third and
current signature, and the one the meter should read.

## Method note

Separate database created and dropped; the shared container was never restarted. API on 8801 and
consoles on 4201/4202, all stopped and **confirmed refusing connections by asking the socket** —
the first `pkill` left the API answering, and the live processes had to be found by command line
and stopped explicitly, which is the trap `.claude/rules/console-dev-loop.md` documents. Chrome's
viewport override was cleared.
