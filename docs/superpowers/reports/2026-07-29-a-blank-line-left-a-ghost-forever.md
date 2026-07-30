# One blank line left a call site in the graph forever, and the only cure was wiping the database

**Date:** 2026-07-29
**Scope:** B62 — a re-index of a changed repository accumulated rows instead of converging, and the
truncate that hid it was load-bearing for a reason nobody had written down.
**Outcome:** `replace_call_sites` converges one repository; `call_sites_for_operation` can be scoped
to one; a scan keeps `call_site` instead of emptying the database; thirteen tests, all watched red
first.

## Three facts, measured against Postgres before anything was written

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
enough. The stale row keeps the finding raised against it, because `finding.call_site_id` cascades
on delete and nothing was deleting — so the graph holds a breaking finding at a position the code no
longer has, and `make_locate` would send an agent to it.

**The cure was a database wipe.** The same comment finishes: "That is safe at M0 only because cli.py
truncates the whole graph at the start of every run." `truncate_all` is per *database*, so a scan of
one repository erased every other repository's rows. `cli.run` already said that out loud — "a
hosted control plane must never do this, since it would erase other customers' state rather than
just this one's" — which leaves the graph with no usable convergence at all: the mechanism that
worked could not be shipped, and the alternative left ghosts.

**And the wipe was load-bearing, not merely convenient.** This is the part that was not written down
anywhere. `call_sites_for_operation(vendor_id, operation_id)` had no repository filter, so with two
repositories in one graph `VendorChangeDetector` emitted a finding for each. A finding is what a pull
request is opened from, so that is a patch proposed to one customer for a line in somebody else's
codebase. Two of the four detectors — `efficiency` and `status_rate` — already held the `repo_id`
they needed for their telemetry queries and did not pass it here, which crossed one repository's
spans against another's code. Per-repository convergence could not be adopted until that clause
existed, which is why this change is three things and not one.

## What changed

**`GraphStore.replace_call_sites(repo_id, sites) -> list[str]`.** Upsert the revision just indexed,
then `DELETE FROM call_site WHERE repo_id = %s AND id <> ALL(...)`, both inside one transaction so no
reader sees a window where a live call site is absent. The empty sequence is a real answer rather
than a guard: a customer who removed their last call to a vendor has zero call sites, and declining
to write that would leave the graph claiming an integration that is gone.

**`call_sites_for_operation(..., repo_id=None)`.** Optional, and its absence means every repository —
which is a genuine query for an aggregate across customers, and the reason it is not simply required.
All four detectors now pass it.

**`truncate_all(keep=())`.** `cli.run` passes `keep=("call_site",)`. Keeping a parent while
truncating its children is what the foreign keys already allow: `finding` references `call_site`, and
truncating the referencing table needs nothing from the referenced one.

**`call_site` finally has a grain comment.** `.claude/rules/graph-grain.md` requires one on every
table and its own worked example is this table — `-- Grain: one row per call site, per indexed
revision.` The table never had it. What it says now is *not* per revision, because this table carries
no history: one row per call site per repository, at the revision last indexed.

The same three probes, re-run through the new API:

```
--- 1. rows now: [('repo-a', 'src/billing.ts', 13)]        findings: 0 -- the ghost took it
--- 2. rows after truncate_all(keep=('call_site',)): [('repo-a', 13), ('repo-b', 40)]
--- 3. findings: 1 across repositories: ['repo-a']
```

## Why the AST guard, rather than a required parameter

`repo_id` staying optional means a fifth detector can reacquire the defect silently, and a wrong
finding here is a pull request against the wrong repository. Making the parameter required would have
caught that at the call site — and would also have broken the legitimate cross-repository query and
about ten existing store tests that have no repository to name.

So the guard is a test that parses each module under `src/sync/detect/` and fails on a call to
`call_sites_for_operation` with no `repo_id` keyword, naming the file and line. Read from the source
rather than from behaviour on purpose: two of the four detectors need observed shapes or spans before
they emit anything, so checking all four by behaviour costs four fixtures and checks the same one
thing.

## What is still cross-repository, and why it was left

`run()` still truncates `finding`, `vendor_change`, `migration_outcome` and both observed tables
wholesale, so a scan of one repository still clears every repository's rows in those five. That is
unchanged rather than fixed, and each one is a separate decision with its own grain argument:

- `finding` and `vendor_change` are re-derived by every scan, so clearing them is closer to correct
  than not — but they are not scoped either, and a per-repository `finding` sweep is the natural
  follow-up now that call sites converge.
- `vendor_change` additionally carries the named exemption in `CLAUDE.md`: oasdiff-derived rows do not
  converge over identical bytes, so that table is at-least-once by declaration and stopping the
  truncate would let it accumulate.
- `observed_shape` and `observed_call` are written by `sync ingest` and cleared by the next
  `sync run`, which is a defect of its own shape — a scan discarding telemetry it did not produce —
  and is not an accumulation bug, so it is not this one.

Also unchanged: `sync.benchmark.score` still calls `truncate_all()` with no `keep`, correctly. A
corpus pair is scored against a database that should hold nothing else, and per-repository
convergence would be a weaker guarantee there rather than a stronger one.

## Verification

Thirteen tests in `tests/test_reindex_convergence.py`, each watched red before the implementation
existed — nine failed on `AttributeError: 'GraphStore' object has no attribute
'replace_call_sites'`, and four on the AST guard naming `vendor_change.py:112`,
`observed_drift.py:117`, `efficiency.py:179` and `status_rate.py:217`.

Among them the assertion `graph-grain.md` asks for by name — "run the stage twice against one fixture,
assert row count and every row identity are unchanged" — which the delete had to be shown not to
break.

The four gates:

```
uv run pytest                                                      TOTALS
uv run lint-imports                                                Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src tests                    exit 0
uv run python scripts/lint_dead_links.py src --baseline ...         exit 0
```

`lint_dead_links` passing matters more than usual here: it is what says `replace_call_sites` is
actually reached from `cli.run` rather than being a correct method nothing calls.
