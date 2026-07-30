# `stroland02/m1-forge` is superseded, not merely conflicting

**Date:** 2026-07-29
**Verdict:** Do not merge. Every change it carries has landed on `main` by another route, and the
two halves it is the only source of are the older of two independent implementations.
**Why this exists:** the branch has been reported as "unmerged, 7 commits" on every coordinator
tick for most of a day. That is a standing item nobody can act on, and the reason it cannot be
merged has never been written down where the next reader finds it. This settles it with
measurement so it is not re-litigated.

## What the branch holds

```
b5f24e0 docs: re-measure coverage 105 commits on, and harden the module it names
474c299 fix: say why the mutation generator is reached from nothing
5c546fa docs: re-audit the spec corpus 105 commits after the last sweep
0613da2 feat: generate labelled pairs by mutating a real repository
9d46454 test: state what a labelled mutation pair has to be, before building one
d7e98cf docs: record the B17 collision, and what each side of it has
c7f3cf2 feat: let the indexer find call sites for a vendor that is not Stripe
```

## The measurement

`git merge-tree --write-tree main stroland02/m1-forge` reports **nine conflicts**, and two of them
are `add/add`:

```
CONFLICT (content): docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md
CONFLICT (content): docs/superpowers/specs/2026-07-28-sync-deprecation-signal.md
CONFLICT (content): docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md
CONFLICT (content): src/sync/benchmark/__init__.py
CONFLICT (add/add): src/sync/benchmark/mutate.py
CONFLICT (content): src/sync/index/python_lang.py
CONFLICT (content): src/sync/index/typescript.py
CONFLICT (add/add): tests/fixtures/ts/twilio/package.json
CONFLICT (add/add): tests/fixtures/ts/twilio/src/insights.ts
```

An `add/add` conflict is the load-bearing detail. It means both sides created the file
independently, which is what distinguishes a branch that is *behind* from one that is *superseded*.

## Each half, and where it landed instead

**The mutation generator (`0613da2`, `9d46454`, `474c299`).** `main` carries its own
`src/sync/benchmark/mutate.py` at 590 lines against this branch's 379. `main`'s version is the one
M3-W99 examined statement by statement — 213 statements, 21 declines tabled, and the finding that
`mutate.py` is an unpinned input to a frozen corpus. Merging the 379-line version would replace an
audited module with an unaudited one.

`474c299`'s subject — *"say why the mutation generator is reached from nothing"* — is the tell. On
this branch the generator had no caller. On `main` it is wired: `sync benchmark --score-pair`
reaches it, twelve corpus specifications score through it, and `gate_corpus.py` gates on the result.

**Multi-vendor indexing (`c7f3cf2`).** Landed by another route and measurably so. The
`_SDK_PACKAGE = "stripe"` constant this commit existed to remove is **gone from
`src/sync/index/typescript.py`** — zero occurrences — and the mechanism that replaced it is more
general than the one here: `sdk_bindings` per language with a `symbol_root` that defaults to the
package (`typescript.py:170`, `:185`). Twilio fixtures exist on `main` under
`tests/fixtures/twilio/` at two vendor versions plus a shape-only reduction, which is why the
`tests/fixtures/ts/twilio/` files conflict `add/add` rather than applying.

**The two docs commits (`5c546fa`, `b5f24e0`).** Both are dated audits — *"105 commits on"* — and
`main` is now several hundred commits past the tree they describe. The spec corpus has been
re-audited twice since by `2026-07-29-sync-spec-audit-log-2.md`, and coverage has been re-measured
repeatedly, most recently to the point where no module in the tree sits below 90%. A dated report
is a record of what was true that day; merging one written against a superseded tree adds a
contradiction, not a measurement.

**The collision record (`d7e98cf`).** This is the one commit whose content is still worth having,
and it is why the branch is kept rather than deleted: it records the B17 collision from the side
that lost it. `docs/superpowers/reports/b17-multi-vendor-index.md` is readable at
`git show stroland02/m1-forge:docs/superpowers/reports/b17-multi-vendor-index.md`.

## What was decided earlier, and why it still holds

An earlier tick ran a trial merge, found four conflicts, and refused on the grounds that
`c7f3cf2` predates the work that superseded it, so merging would revert landed code. That
reasoning was right and the situation has only hardened: the conflict count has grown from four to
nine as `main` moved, and two conflicts are now `add/add` where they were once content.

## What to do

**Nothing, and stop carrying it as an open item.** The branch stays as a record. It is not merged,
not deleted, and not a decision waiting on anybody.

If a future task wants the one thing this branch is still the only source of — the losing side's
account of the B17 collision — read it out of the ref rather than merging it.
