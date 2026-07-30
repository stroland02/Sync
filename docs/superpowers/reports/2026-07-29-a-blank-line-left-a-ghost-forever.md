# One blank line left a call site in the graph forever, and deleting it deleted the finding

**Date:** 2026-07-29, finished 2026-07-30
**Scope:** B62 — a re-index of a changed repository accumulated rows instead of converging; the
truncate that hid it was load-bearing for a reason nobody had written down; and the obvious fix
destroyed what the previous scan had concluded.
**Outcome:** `call_site` rows are retracted rather than deleted. A moved call is no longer asserted
at the position it left, the findings raised against that position survive, and nothing acts on
them. Fourteen tests in `tests/test_reindex_convergence.py`, eighteen with the parametrised guard,
four gates green, corpus unmoved.

This is the second attempt. The first is preserved at `8a62f1d` on
`unreviewed/b62-ghost-call-sites` and is the base of this work rather than a discarded draft: its
measurements, its per-repository convergence and its grain comment are all still here. What it got
wrong is in its own section below, because the gate that caught it is the reason this document can
claim anything.

## Three facts the first attempt measured, before anything was written

```
--- 1. the same call site, one blank line added above it
   rows now: [('repo-a', 'src/billing.ts', 12), ('repo-a', 'src/billing.ts', 13)]
   findings: 1 -- the ghost keeps its own

--- 2. a second repository, then a scan of the first
   rows before: [('repo-a', 12), ('repo-a', 13), ('repo-b', 40)]
   rows after truncate_all(): []                       -- repo-b is gone too

--- 3. two repositories, one operation, one detector
   findings: 2 across repositories: ['repo-a', 'repo-b']
```

Each one makes the next one worse.

**The ghost.** `upsert_call_site` keys identity on `(repo_id, path, symbol, line, col)`, and its own
comment has said what that costs since `efcc19d`: "a call site that merely shifts down the file (no
other content change) becomes a new row rather than an update to the old one." A blank line is
enough. The stale row keeps the finding raised against it, so the graph holds a breaking finding at
a position the code no longer has, and `make_locate` would send an agent to it.

**The cure was a database wipe.** The same comment finishes: "That is safe at M0 only because cli.py
truncates the whole graph at the start of every run." `truncate_all` is per *database*, so a scan of
one repository erased every other repository's rows. `cli.run` already said that out loud — "a
hosted control plane must never do this, since it would erase other customers' state rather than
just this one's" — which left the graph with no usable convergence at all: the mechanism that worked
could not be shipped, and the alternative left ghosts.

**And the wipe was load-bearing, not merely convenient.** `call_sites_for_operation(vendor_id,
operation_id)` had no repository filter, so with two repositories in one graph
`VendorChangeDetector` emitted a finding for each. A finding is what a pull request is opened from,
so that is a patch proposed to one customer for a line in somebody else's codebase. Two of the four
detectors — `efficiency` and `status_rate` — already held the `repo_id` they needed for their
telemetry queries and did not pass it here. Per-repository convergence could not be adopted until
that clause existed, which is why this change is three things and not one.

## The first attempt solved that and broke something quieter

It converged the table with `DELETE FROM call_site WHERE repo_id = %s AND id <> ALL(...)`. Gated
against a real database by the coordinator before it could land:

```
initial index          -> 1 row
finding recorded       -> 1
after the line shift   -> call_site rows at lines [6]
GHOST GONE?            -> YES
FINDING SURVIVED?      -> NO -- the cascade destroyed it (count=0)
```

`finding.call_site_id REFERENCES call_site (id) ON DELETE CASCADE`. Deleting the stale row deletes
what the previous scan concluded about it, with no error and nothing left to notice. The original
brief had named that hazard in advance and called it worse than the defect being fixed, and it was
right: a ghost row is something a reader can notice, and a finding that is simply not there is not.
`CLAUDE.md` puts what a run concluded — including what it abandoned — among the data this system
learns routing from.

The first attempt's own test asserted the destruction as correct: `open_findings() == []` after the
move, with a docstring arguing the cascade "is what makes this safe to do at all". That test is now
`test_a_finding_outlives_the_call_site_it_names_moving`, asserting both halves instead.

## The shape chosen, and the two rejected

**Retract by absence.** `call_site` gains `retracted_at TIMESTAMPTZ`. `replace_call_sites` upserts
what the pass found and stamps the repository's other current rows instead of deleting them. Every
query that speaks for the revision last indexed filters `retracted_at IS NULL`; `get_call_site`
does not, so a finding's call site stays readable by the id the finding already holds. The record
survives and nothing acts on it.

The cost is real and is declared in `schema.sql`: the table only grows, one row per position a call
has ever occupied, and nothing prunes it. That is deliberate — a retention rule is a decision about
how long a conclusion stays explainable, and the brief was explicit that inventing one here was not
wanted.

**Keep what is referenced** — delete only rows no finding points at — was rejected. It makes the
contents of a table describing source code depend on whether a detector happened to fire, and it
leaves in place exactly the ghosts a reader is most likely to be looking at: the ones with findings
attached.

**Follow the call site** — recognise that the call moved and repoint the finding — was rejected as
unsound rather than merely hard. Position is deliberately part of identity, so a call at line 13
where there used to be one at line 12 may be the same call shifted or a different call written where
the old one was deleted, and nothing at this layer distinguishes them. A wrong guess reattributes a
conclusion to a call nobody drew it about, which is quieter than either defect it would be fixing.

## What changed

**`call_site.retracted_at`**, nullable with no default, which is the only shape `apply_schema` can
add to a table that already has rows — and every row it would be added to is one the last pass did
find, so NULL is the correct value for all of them. The grain comment is extended rather than
replaced: one row per position a call site has ever been indexed at, and the `retracted_at IS NULL`
subset is what a detector, a count or a rank is about.

**`GraphStore.replace_call_sites`** stamps instead of deleting, in one transaction with the upserts,
and only over rows that are still current. That last clause is why `retracted_at` means *when the
graph stopped seeing this call* rather than *the most recent pass that did not see it* — the second
is a fact about the scan schedule, not about the code.

**`upsert_call_site` clears `retracted_at` on conflict.** A call that comes back to a position it
once occupied — the comment above it deleted again — is current, and identity is positional, so this
is the same row rather than a resurrected ghost.

**Three read queries now say "current".** `call_sites_for_operation` and `call_site_counts` filter,
with no opt-in flag to include history: handing a detector the retracted set is the defect. On
`call_site_counts` it matters more than it looks — a count over the whole table grows every time a
line is added above a call, so ranking would promote whichever repository was edited most.

**`open_findings` joins `call_site`** and requires `retracted_at IS NULL`. This is the half that
makes retention safe: the hazard that made deleting tempting was a finding naming a line the code no
longer has, and filtering here answers it without destroying the row. `status` is untouched on
purpose — it records what remediation did, and writing 'abandoned' there would claim a run reached a
conclusion it never reached.

**Test doubles.** Five stub stores gained `truncate_all(keep=())` and `replace_call_sites`, and two
stub detectors gained `repo_id`. All of them were failing against the preserved commit, which is how
this branch can say the first attempt's suite was never run: sixteen tests, in four files it did not
touch.

`tests/test_cli.py::test_the_graph_is_truncated_after_apply_schema_and_before_the_scan` now also
asserts `store.kept == ("call_site",)`. Without it the ordering assertions pass just as well against
a scan that truncates `call_site` too, which is what they used to be asserting.

## Verification

**The regression was reproduced before it was fixed.** Against `8a62f1d`'s delete, with the new test
in place:

```
>       assert _findings_in_table(store) == [finding_id]
E       AssertionError: assert [] == ['88b37608b89...501abf30c060']
E         Right contains one more item: '88b37608b89bf00a876d501abf30c060'
```

**Every new clause was then broken deliberately, one at a time, and the test that claims it went
red.** A predicate nothing tests is a predicate the next person deletes:

```
RED: call_sites_for_operation drops the current-revision predicate
     test_a_detector_raises_nothing_against_a_call_site_that_moved
RED: call_site_counts drops it
     test_ranking_counts_the_calls_the_code_has_and_not_the_ones_it_had
RED: replace_call_sites re-stamps rows already retracted
     test_retraction_records_the_pass_that_lost_the_call_not_the_latest_one
RED: upsert_call_site stops clearing retracted_at
     test_a_call_that_comes_back_to_its_old_position_is_current_again
RED: open_findings stops joining call_site
     test_a_finding_outlives_the_call_site_it_names_moving
```

The first run of that check reported the second line GREEN, which was the check being wrong rather
than the test: the needle `WHERE repo_id = %s AND retracted_at IS NULL` is a prefix of the clause in
`replace_call_sites`, so it patched that instead and the mutation never reached `call_site_counts`.
Recorded because a mutation harness that silently patches the wrong line reads exactly like a test
that cannot fail.

The four gates:

```
uv run pytest                                             2482 passed, 1 skipped in 151.77s
uv run lint-imports                                       Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests  exit 0
uv run python scripts/lint_dead_links.py src --baseline …  exit 0
```

Run after merging `main` at `1631514`, which is three tests further along than the 2479 this
change was gated at on its own. The merge is clean: main's four newer commits touch
`signals/reachability.py`, `tests/test_decode_handlers.py` and three documents, none of which this
change goes near.

`lint_encoding` is silent when it passes, so it was shown to fail first: pointed at a file holding
`Path("x").read_text()` it exits 1 and names the line.

The corpus, scored from two clean databases — `main` at `18ca661` with `src` and `tests` checked out
into this worktree, then the same worktree with this change restored:

```
                        before          after
  binding precision     1.0000 n=26     1.0000 n=26
  binding recall        1.0000 n=26     1.0000 n=26
  falsifiable negatives      7               7
  pairs scored              17 of 17        17 of 17
  symbol map            5f71dcd3bec1    5f71dcd3bec1
```

`gate_corpus.py` prints "Every floor cleared" on both, exit 0. Both were taken before the merge
described above, so the only difference between the two columns is this change. That the figures are
identical is the expected result rather than a lucky one: `sync.benchmark.score` truncates its own
database per pair, so no pair ever re-indexes a repository and no retraction happens during scoring.

**Two gates were red in this worktree before any of this work, for environmental reasons, and both
are worth recording because either could be mistaken for a regression.** `.cache/specs/symbols.json`
held the 179-symbol artifact that predates B39 while `benchmark/corpus/symbol_map.yaml` pins the
272-symbol one; rebuilding it from any specification on disk reproduces the pinned digest exactly,
which is the pin's own claim about itself being confirmed. And `.cache/corpus` was missing the
`virtual-lab` clone, which excluded two pairs as `no-call-site-on-the-changed-operation` and put the
corpus gate at 15 of 17 pairs and 6 negatives. Both are gitignored per-worktree artifacts, neither
is in this diff, and `scripts/fetch_corpus_repositories.py` restored the second at the pinned tree
digest.

## What is left, named rather than fixed

**A finding whose call site was retracted is invisible and nothing lists it.** It is out of
`open_findings` by design and no query returns it, so "what did we conclude about code that has since
moved" is answerable only in SQL. That is the right trade for now — the row is kept precisely so the
question stays answerable later — but the query does not exist.

**`sync run` still truncates `migration_outcome`.** `truncate_all(keep=("call_site",))` empties every
other table the schema declares, which includes the corpus of repair attempts. It is pre-existing and
it is not what B62 was about, but it is the same defect one table over: `CLAUDE.md` says abandoned
runs are data, and a scan currently deletes them. Whoever picks this up should read `keep` as the
mechanism that already exists to fix it.

**`finding` and `vendor_change` are still cleared wholesale and still cross-repository.** Both are
re-derived every scan, so clearing them is closer to correct than not, and `vendor_change` carries
the named oasdiff exemption in `CLAUDE.md` — it does not converge over identical bytes, so stopping
its truncate would let it accumulate. A per-repository `finding` sweep is the natural follow-up now
that call sites converge.

**`sync.benchmark.score` still calls `truncate_all()` with no `keep`, correctly.** A corpus pair is
scored against a database that should hold nothing else, and per-repository convergence would be a
weaker guarantee there rather than a stronger one.
