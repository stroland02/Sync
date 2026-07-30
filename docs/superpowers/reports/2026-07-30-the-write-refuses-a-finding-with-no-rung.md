# The write refuses a finding that names no rung

**Date:** 2026-07-30
**Scope:** B66 — B65 landed `finding.binding_rung` and five attributing detectors, and nothing
enforced that a finding names a rung. The column's `NOT NULL DEFAULT 'unattributed'` meant a
forgetful detector's row landed looking exactly like one written before the column existed.
**Outcome:** `GraphStore.insert_finding` raises `ValueError` naming the detector when the rung is
`unattributed`. Fourteen existing tests now state the rung their detector actually attributes, the
corpus is unmoved, four gates green.

## Where the check went, and why not the other place

`Finding` is exported from `sync.core`, which `CLAUDE.md` calls the published plugin SDK: a third
party writing an adapter depends on that module alone, so a required field breaks every detector
anyone else has written. That position was tried and reversed on the contract, and this task did not
re-open it — the measured churn inside this repository (153 failures, 120 errors, 32 files) is the
smaller half of the argument.

`sync.graph` is internal, so nothing published is at stake, and `CLAUDE.md` puts validation at
boundaries — user input, vendor responses, subprocess output. A write to Postgres is one of those; a
Pydantic constructor inside our own detector is not. So `insert_finding` refuses, and constructing an
unattributed `Finding` stays legal and keeps meaning what it says: no binder claimed this.

**Refused, not warned, and not corrected.** A warning would leave the row, and the row is the
problem: `unattributed` is what the column defaults to, so a finding written without a rung is
indistinguishable from every row that predates the column, and no later query can separate a
detector that forgot from history that could not know. Substituting a rung would be worse — there is
no value to choose that is not a binding claim nobody made, and `sync.benchmark.binding` scores
precision per rung off this column, so a guessed value there is a measurement about a binder that
never ran. There is no bypass parameter for the same reason the brief gave: it would be used.

## Other write paths — the answer

**`insert_finding` is the only route into `finding` that can set a rung, and the only INSERT in
`src/`.** Checked four ways:

- `INSERT INTO finding` appears exactly twice in the repository: `store.py:348`, and
  `tests/test_finding_rung.py:194`, which writes a row *without* the column on purpose to prove the
  default still answers for history.
- `set_finding_status` is the only other write, and its statement sets `status` alone — it cannot
  introduce a row and cannot change a rung.
- No `COPY`, no `copy_from`, no `executemany` anywhere in `src/`, `scripts/`, `benchmark/` or
  `tests/`.
- `psycopg.connect` appears in `src/` only in `graph/store.py`, so no module holds a second
  connection it could write through. Tests and `conftest.py` open their own, which is how the
  legacy-row test above works.

`sync.benchmark` deserves its own sentence because the brief asked: it never persists a finding at
all. `score.py` runs detectors and reads their output in memory, which is also why the corpus figures
below cannot move.

## The fourteen, and how each rung was decided

No blanket edit, and no generic constant was needed — **every failing fixture names a detector, and
the rule B65 landed fixes the rung from the detector**, so each value states something true rather
than something convenient:

| test file | fixtures | detector | rung | why |
|---|---|---|---|---|
| `test_graph_store.py` | 1 | `vendor_change` | `static` | what `VendorChangeDetector` attributes |
| `test_graph_store.py` | 3 | `efficiency` | `observed` | the correlator's rung, correlated case |
| `test_pipeline_composes.py` | 1 (9 tests) | `parameter-deprecation` | `static` | what the detector attributes |
| `test_reindex_convergence.py` | 1 | `vendor_change` | `static` | as above |
| `test_schema_convergence.py` | 1 | `efficiency` | `observed` | as above |

Seven `Finding` constructions, fourteen failing tests, because `test_pipeline_composes.py` builds its
finding in one shared helper.

The three `efficiency` fixtures are the only ones where a choice existed: that detector carries
`observed_call.binding_rung`, which is `observed` when the spans correlated and `unresolved` when they
did not. Those tests are about row identity and column convergence rather than attribution, so they
take the correlated case — the rung a loop finding with a real call count behind it actually holds —
with a comment at the site saying that is why. Writing `unresolved` there would have been equally
green and would have implied a correlation failure the fixtures say nothing about.

Two docstrings were corrected rather than left to drift. `FindingRung` said *"`unattributed` on a row
written after this shipped is still a bug -- it is just one the type no longer catches"*, and the
field's own docstring described the sixth-detector gap as open. Both now name where the check is.

## Verification

**Watched red first**, both new tests, for the reason expected:

```
FAILED test_persisting_a_finding_that_names_no_rung_is_refused    DID NOT RAISE ValueError
FAILED test_the_refused_finding_leaves_no_row_behind              DID NOT RAISE ValueError
```

**Then the guard was mutated to check which test notices**, because the second one is only worth
having if it catches something the first does not:

```
== the guard never fires
   RED: test_persisting_a_finding_that_names_no_rung_is_refused
   RED: test_the_refused_finding_leaves_no_row_behind

== the guard fires after the row is written
   GREEN: test_persisting_a_finding_that_names_no_rung_is_refused
   RED: test_the_refused_finding_leaves_no_row_behind
```

A write-then-check implementation raises the same exception and leaves an `unattributed` row behind,
which is the worse of the two failures because the exception suggests nothing was written. Only the
second test sees it.

**The controls both hold, and neither is new.** A finding that names a rung still writes and reads
back through the model — `test_a_persisted_finding_can_be_attributed_to_a_rung_by_one_column`,
`test_the_rung_survives_a_read_back_through_the_model`, and the fourteen repaired tests are all
evidence of it. Rows already in a database still read as `unattributed`:
`test_a_row_written_before_the_column_existed_reads_as_unattributed` inserts one the way a deployed
database holds it — without the column — and asserts both the row and `open_findings()` answer
`unattributed`. The guard is on the write, so it does not reach that row, which is the point: the
default exists for history and history is still readable.

The corpus, scored from two clean databases in this worktree — `main` at `fa013a0` with `src` and
`tests` stashed, then the same tree with the change restored:

```
                        before          after
  binding precision     1.0000 n=26     1.0000 n=26
  binding recall        1.0000 n=26     1.0000 n=26
  falsifiable negatives      7               7
  pairs scored              17 of 17        17 of 17
  symbol map            5f71dcd3bec1    5f71dcd3bec1
```

`gate_corpus.py` printed "Every floor cleared" on both, exit 0 on both. Identical is the expected
result rather than a lucky one: the scorer never persists a finding, so the guard is not on its path.

The four gates:

```
uv run pytest                                             2549 passed, 2 skipped in 102.89s
uv run lint-imports                                       Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests  exit 0
uv run python scripts/lint_dead_links.py src --baseline …  exit 0
```

Two tests added, so the collected total moves from the brief's 2549 to 2551. The second skip is this
worktree rather than this change, and it is the same pair B64 reported:
`test_oasdiff_determinism.py:159` wants `tools/oasdiff` and `test_parameter_reduction.py:166` wants
`.cache/specs/v2320.json`. Both skip by design when their inputs are absent and both would run after
`scripts/fetch_measurement_inputs.py`.

## What is left

**A detector can still emit an unattributed finding; it just cannot persist one.** The failure moved
from silent to loud, not from possible to impossible, and the loud version arrives at the write
rather than at the detector that caused it. A conformance test over `sync.detect` — parse each module
and require every `Finding(...)` to name `binding_rung`, the way
`test_reindex_convergence.py` guards `call_sites_for_operation` — would catch it one step earlier and
is the natural follow-up.

**`CLAUDE.md`'s rung bullet does not mention the refusal.** It says every artifact derived from a
binding carries its rung; it could now say that the write enforces it. Left to the coordinator, since
that file is the shared context every agent reads and editing it from a worker is how two versions of
a rule appear.
