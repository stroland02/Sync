# Which quality axes are waiting on `B7`, and which one is not

**2026-08-17, Lane C.** Gate 2 reports `0 of 5 quality axes measured; every axis reports no
samples`, which is true and collapses two different facts. "No samples yet" and "structurally
unmeasurable until an attempt goes green" call for different work, and only one of them is anybody's
to act on today.

Written as a finding rather than a build: no code changed to produce it.

## The answer

**Four of the five are denominated on a merged pull request and cannot move before `B7`. The
fifth — routing accuracy — needs no pull request at all, and is the shortest path to moving a gate
on the board.**

| Axis | Denominator | Waiting on |
|---|---|---|
| `merge_rate_by_change_kind` | findings with `pr_number is not None and pr_merged is not None` | `B7`, then a merge outcome arriving |
| `merge_rate_by_tier` | the same | `B7`, then a merge outcome arriving |
| `tokens_per_merged_patch` | `merged_findings` | `B7`, then a *merged* pull request |
| `wall_ms_per_merged_patch` | `merged_findings` | `B7`, then a *merged* pull request |
| **`routing_accuracy`** | **findings with any attempt at tier 0** | **nothing outside the pipeline** |

Read off `src/sync/benchmark/axes.py:171-185`.

## Why the four are strictly blocked

`decided` is `pr_number is not None and pr_merged is not None` (`:171`), and both merge-rate axes
group it. `merged_findings` is the subset where `pr_merged` is true (`:173`), and both the token and
wall-clock axes divide by it (`:201-210`).

So they need three things in order: a run that opens a pull request, that pull request reaching a
decision, and the decision arriving in `migration_outcome`. The first is `B7`. Nothing before it
moves any of these four, and no amount of local running produces a sample.

**The corpus makes that concrete.** Four production attempts today, one with `pr_number = 101`, and
`pr_merged` null on all four. One pull request was opened and no outcome has ever come back, so
`decided` is empty and every one of the four axes divides by zero findings.

A null `pr_merged` is deliberately not counted as unmerged — `axes.py:168-170` says why, and it is
right: counting a webhook that has not arrived as a rejection would make every recent run look worse
than it was, and the number would improve on its own with no change to the pipeline.

## Why routing accuracy is different

`routed_to_tier_zero` is every finding with any attempt at tier 0 (`:176-179`). No pull request
appears in that predicate, and none appears in `held_at_tier_zero` either (`:180-184`), which asks
whether the finding stayed at tier 0 and whether a tier-0 attempt passed static verification.

**Both are facts a run produces before it ever reaches a forge.** The corpus already holds four
production attempts that opened no pull request, so rows of exactly this kind are being written
today.

It reads zero for a different reason from the other four: **nothing has been routed to tier 0 yet.**
The four attempts carry tiers 1, 2, 2 and −1. That is a fact about which findings have been
attempted, not about the forge, and it is fixable by a run rather than by a decision.

**What it would take:** one production `sync run` over a change the tier cascade routes to tier 0 —
a mechanical codemod — reaching static verification. No pull request, no merge, no `B7`.

## One shortcut that does not exist, checked rather than assumed

Rehearsal rows cannot supply it. `GraphStore.migration_outcomes` filters `WHERE NOT is_rehearsal`
in SQL (`store.py`), so a `sync rehearse` run — which needs no forge at all and would otherwise be
the obvious way to manufacture a tier-0 attempt — writes rows the axes never see.

That filter is correct and should stay: a rehearsal row is a fixture standing in for evidence, and
Gate 2 exists to refuse exactly that. It is recorded here because it is the first thing anybody
would try.

## What this changes about Gate 2's verdict

`CANNOT TELL` remains right, and for a sharper reason than "no samples". Four axes have no sample
obtainable by any action available today; one has no sample because of what has been attempted so
far.

The gate does not currently draw that line, and a reader who acts on `0 of 5` will reasonably go
looking for five problems. There is one, plus a decision that is the owner's.

**Deliberately not built here.** Teaching Gate 2 to say which axes are blocked means encoding each
axis's denominator a second time, in a second place, and `CLAUDE.md` calls a fact written twice the
most expensive debt in this repository because the disagreement is silent. If it is worth having,
the distinction belongs in `sync.dashboard.fleet.corpus_health` beside the axis definitions — one
field per axis saying what its denominator requires — and the gate should read it, exactly as it
reads everything else there.
