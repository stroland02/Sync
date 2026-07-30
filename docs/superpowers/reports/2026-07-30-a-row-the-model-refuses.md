# A row the model refuses, and why a CHECK is not what closes it

M3-W112. `docs/superpowers/reports/2026-07-30-mcp-tool-surface-declines.md` found the gap while
examining the MCP tool surface: `vendor_change.severity` is `TEXT NOT NULL` with no CHECK against
a five-member `Literal`, so **a row Postgres stores is one the model refuses.** Both halves
confirmed. `src/sync/core/models.py:23` declares
`Severity = Literal["breaking", "warning", "deprecation", "addition", "info"]`, and `schema.sql`
declares `severity TEXT NOT NULL` at two places plus `change_severity` at a third, none with a
constraint. After this task it still does, and now says why.

The answer taken is the third of the three the brief named: **neither a CHECK nor a change to the
read.** The gap is a documented property of the schema, and the repair that would cost something
belongs at the tool boundary, which this task does not own. What ships is the vocabulary named
where `schema.sql` already names four others, the argument beside it, a grain declaration
`vendor_change` never had, and eleven tests pinning the property against a real server.

That is a decline, so the evidence for it is the whole of this report.

## Every route by which an invalid row can be written, and which are real

| # | Route | Real? | What it costs |
|---|---|---|---|
| 1 | `GraphStore.upsert_vendor_change`, `insert_finding`, `record_migration_outcome` | **No.** Each takes a Pydantic model whose field is typed `Severity`, and pydantic validates on construction. Measured, not inferred: constructing each of the three with `catastrophic` and every other field valid raises. | — |
| 2 | A vendor adapter building a `VendorChange` | **No.** Six construction sites in `src/` (`oasdiff`, `deprecations/catalogue`, `deprecations/parameters`, `mcp_server/adapter`, `feed/consumer`, `cli`). All go through the model. `mcp_server/adapter._change` types its parameter `severity: str`, which looks like a hole and is not — the value lands in `VendorChange(...)` on the next statement. | — |
| 3 | The signed feed | **No.** `feed/consumer.py:79` is `VendorChange(**entry)`. This is `CLAUDE.md`'s rule holding: a validly signed feed carrying a malformed change fails at parse, before a row is built. | — |
| 4 | `model_construct`, or `model_validate` with validation off | **No.** `model_construct` appears nowhere in `src/` or `tests/`. The one `model_validate` is `snapshot.py:56` against an MCP `ListToolsResult`, unrelated. | — |
| 5 | Raw SQL through `GraphStore._connect()` | **Yes, and it runs in this repository every suite.** `tests/test_schema_convergence.py::_insert_a_row` fills every text column with `'x'` to give `truncate_all` something to empty, which writes `severity = 'x'` into `vendor_change` and `finding` and `change_severity = 'x'` into `migration_outcome`. It writes to a database the fixture creates and drops, so nothing survives — but it is a real write of a real invalid value, and it is *inside* the application rather than a bypass of it. | Nothing today. It would be the first thing a CHECK broke. |
| 6 | A restore from a dump, a hand-applied SQL repair, `psql` | **Yes, and it requires bypassing the application.** Not observable from here. | Unbounded, and undetectable until a read. |
| 7 | **Drift: `Severity` loses a member.** A build that retires `warning` reads rows an earlier build wrote legitimately. | **Yes, and this one bypasses nothing.** The row was written correctly by the code that wrote it. | Every stored `warning` row becomes unreadable. **A CHECK does not help**: the constraint on an existing database enumerates whatever the DDL said when that database was created, so it permits exactly the value the new model refuses. |
| 8 | **Drift: `Severity` gains a member.** | Yes, and it has already happened once — `warning` was added when `oasdiff breaking`'s three grades stopped being collapsed into one. | Nothing today. **With a CHECK it becomes a cost**: an existing database refuses a value the deployed model considers valid. |
| 9 | A second `GraphReader`/writer implementation | **Not for writes.** One module in `src/` issues SQL against these three tables. Measured by regex over every `src/**/*.py`: `sync/graph/store.py`, and nothing else. `tests/test_severity_vocabulary.py::test_the_store_is_the_only_module_that_writes_a_severity_column` holds it. | — |

**The measured state of the world.** A snapshot, and it has to be described as one: the count moves
while you look at it, because every suite run creates a database per xdist worker and `conftest`'s
sweep drops the ones killed runs left behind. Twenty minutes apart the same query returned 216
non-template databases and then 195.

At the survey: 214 scanned, 182 reachable — the rest are `pg_database` rows that refuse a connect,
all but one of them `sync_<task>_gw<n>` names left by killed xdist runs. `vendor_change` present in 145 of
them, `finding` in 145, `migration_outcome` in 129. Severity-bearing rows found: 130 `breaking` in
`vendor_change`, 2 `info` and 1 `breaking` in `finding`, 3 `breaking` in `migration_outcome` — 136
in total. **Rows holding a value outside the vocabulary: zero.** Three of the five members —
`warning`, `deprecation`, `addition` — appear in no persisted row anywhere, which is why route 7
would go unnoticed.

So: **no production route can write the row.** One in-repo route does, deliberately, into a
throwaway database. Two out-of-application routes can. And one route — the narrowing drift —
requires no bypass at all and is the one route a CHECK is useless against.

## Whether the three columns share one vocabulary, and how that was established

They do, and by identity rather than by reading five strings off three declarations:

    VendorChange.model_fields["severity"].annotation        is sync.core.models.Severity  -> True
    Finding.model_fields["severity"].annotation             is sync.core.models.Severity  -> True
    MigrationOutcome.model_fields["change_severity"].annotation is ...Severity            -> True

All three are the same alias object, all with `('breaking', 'warning', 'deprecation', 'addition',
'info')`. **None is wider by design**, and the two candidates for being wider are not:

- `finding.severity` is chosen by a detector rather than copied. Four of the five detectors write
  a constant (`info`, `addition`, `deprecation`, `breaking`); `vendor_change` passes the vendor's
  own grading through, which is how `warning` can reach the column. Still exactly `Severity`.
- `migration_outcome.change_severity` is copied from the change an attempt was made against
  (`MigrationOutcome.from_attempt`). The corpus does not grade differently, and it should not:
  an attempt against a change whose severity the model cannot name is not a wider grading, it is
  an unreadable row, in the one table that cannot be backfilled.

`tests/test_severity_vocabulary.py::test_the_three_columns_are_typed_by_one_alias` asserts the
identity, so retyping one of them fails there rather than being discovered by a rejected row.

**The wider count that decided the shape of the answer.** Ten columns in this schema have a closed
vocabulary behind them: `severity` twice, `change_severity`, `vendor_change.source`,
`finding.status`, `migration_outcome.strategy`, `observed_shape.json_type`,
`observed_shape.source`, and `binding_rung` on both `finding` and `observed_call`. **Not one is
constrained in DDL.** Four already name their vocabulary in a comment — `json_type` and
`observed_shape.source` as `-- 'a'|'b'|'c'`, both `binding_rung`s in prose. The schema's
convention is therefore established and consistent: name the vocabulary, do not constrain it.
`severity` was the odd one out for not even having the comment.

## What a CHECK does to a database that already holds a violating row

Three measurements, all against Postgres 16.14 on 5433, none reasoned about.

**1. A CHECK in a column definition never reaches a database that already has the column.** This
is the decisive one. Measured directly on `vendor_change`: an aged database given today's schema,
then `schema.sql` edited to add `CHECK (severity IN (...))` inline, then `apply_schema` run against
both a database created after the edit and the aged one.

    fresh, after the edit:   CHECK ((severity = ANY (ARRAY['breaking'::text, ...])))
    aged,  after the edit:   []
    aged accepts 'catastrophic' with the CHECK in the file:  catastrophic
    fresh refuses it:  23514

`apply_schema` converges an existing database by re-issuing every column definition as
`ADD COLUMN IF NOT EXISTS`, and Postgres skips the whole item — constraint included — when the
column is already there. Its own docstring already said it "cannot rename a column, change a type,
add or drop a constraint"; this is what that costs a CHECK specifically. The constraint would be
present on every database created after the edit, where every write already goes through a
validated model, and absent from every database that predates it, which is the only place a
hand-written row can be. **Absent and believed present is worse than absent.**

**2. A table-level `ADD CONSTRAINT` is refused outright by a table holding a violating row.**
SQLSTATE 23514, `check constraint "vc_sev" of relation "vendor_change" is violated by some row`.
Across two hundred-odd databases, that is an apply-time failure in whichever one somebody happens to
hold a bad row in, at startup, for a run that has nothing to do with severity.

**3. A bare `ADD CONSTRAINT` is not idempotent.** 42710 on the second apply, which breaks the rule
`CLAUDE.md` binds every stage to. `DROP CONSTRAINT IF EXISTS` followed by
`ADD CONSTRAINT ... NOT VALID` is idempotent — measured over two consecutive applies — and
`NOT VALID` leaves pre-existing rows readable while refusing new ones. That is the shape the
migration would have to take, and it is the same shape as `binding_rung`'s `unattributed`
default: *tolerate history, constrain the future.* A DROP-then-re-ADD does not re-validate, so
the tolerance survives re-application.

So a CHECK *is* buildable, in exactly one form. What it does not survive is the argument for why.

## Which of the three answers was taken, and the case against the other two

### Rejected: option 1, a CHECK constraint

Four reasons, in the order of how much weight they carry.

**It would make `schema.sql` a second declaration of a vocabulary `sync.core` owns, and the
comment on `Severity` records that this coupling is the thing that does not exist.** Verbatim:
*"Nothing enumerates this type on a frozen surface: the MCP tool schemas type `severity` as a bare
string and `schema.sql` stores it as TEXT, so widening it moves no contract."* That is not an
accident anybody left behind — it is why widening the vocabulary cost one line when oasdiff's three
grades stopped collapsing into one. And a hand-maintained copy of the members in DDL is precisely
the mechanism `_add_missing_columns` refuses on its own docstring: *"the alternative is a parallel
list of ALTERs that somebody has to remember to extend, and forgetting is the entire defect being
fixed here — a mechanism that needs the same discipline the bug needed is not a fix."*

**It does not address the route that requires no bypass.** Route 7 — a member retired — leaves an
existing database's constraint permitting exactly the value the new model refuses. The constraint
is not merely unhelpful there; it is stale by construction.

**It closes one of four shapes that reach the same silence.** W107 enumerated them: a `severity`
outside `Severity`, a `source` outside `ChangeSource`, a `raw` that is not an object, and any field
a later model requires that the row does not carry. `vendor_change.source` is `TEXT NOT NULL` with
no CHECK either. Constraining `severity` alone buys a quarter of one read's failure modes;
constraining all ten closed-vocabulary columns is a different and much larger decision about
coupling, and it is not this task.

**And it has a measured cost inside the suite.** `test_schema_convergence.py::_insert_a_row` fills
every text column with `'x'` from a type-keyed `_FILLER` map, which is what lets it stay generic
over a schema that gains tables. A CHECK makes that map domain-aware per column — the same parallel
list, one file over.

### Rejected here, and reported as the next task: option 2, making the read loud

**The half inside `src/sync/graph/` is already correct, and that is the finding.** W107's sentence
*"the write is guarded by the model; the read is not"* is true of the tool and not of the store.
`get_vendor_change` raises two disjoint types:

| Input | Raises | `LookupError`? | `ValueError`? |
|---|---|---|---|
| an id no row has | `KeyError` | yes | no |
| a row that exists and does not validate | `pydantic_core.ValidationError` | no | yes |

Neither is a subclass of the other. All four reads were measured against a real row: none of
`get_vendor_change`, `all_vendor_changes`, `open_findings` or `migration_outcomes` returns a
partial or null-filled answer — every one raises. **Nothing in `sync.graph` has to move.**

The two cases become one answer in `src/sync/mcp/tools.py`, whose `_change_for` catches
`(KeyError, LookupError, ValueError)`. So the repair is a one-token narrowing in a file this task
is forbidden to touch:

```python
    def _change_for(self, finding: Finding) -> VendorChange | None:
        if finding.vendor_change_id is None:
            return None
        try:
            return self._graph.get_vendor_change(finding.vendor_change_id)
        except LookupError:            # was (KeyError, LookupError, ValueError)
            return None
```

`LookupError` still absorbs the dangling-reference decline that `_site_for`'s docstring argues
for — one bad reference must not deny an agent every other answer — while a `ValidationError`
escapes to `_call`, which already returns `isError: true` naming the exception type. No new
response field, and `tests/golden/tool_schemas.json` does not move, because the published freeze
covers the request half of the contract and there is no `outputSchema`.

**What that next task needs from this one: nothing.** No store change, no schema change, no new
exception type. Two things it will have to do inside `src/sync/mcp/`:

1. `test_the_three_silences_are_one_answer_to_an_agent` in `tests/test_mcp_tool_declines.py` pins
   the current flattening by comparing three payloads for equality. W107 wrote it so that a repair
   turns it red on purpose. It has to be replaced, not deleted — the two silences that remain
   correct (a null `vendor_change_id`, and a dangling reference) must still be one answer.
2. `_site_for` carries the identical tuple, and the same argument applies to it: a `CallSite` row
   that will not parse is currently dropped from a page and counted out of `total`. Narrowing one
   and not the other leaves half the flattening in place.

A store-level wrapper — a named `ValueError` subclass naming the row — was considered and
rejected. It buys nothing: `ValidationError` is already a type the tool can separate, and a
subclass of `ValueError` would still be absorbed by the catch that is the actual defect. Adding it
would be error handling for a condition the store already reports correctly.

### Taken: option 3, neither — with one qualification the brief asked for

The brief's precondition was *"defensible if every write route requires bypassing the
application"*, and strictly that is not met: route 7 bypasses nothing. But the qualification points
the same way. The only answer that helps route 7 is the read, and the useful half of the read is
out of scope. So what ships is what is inside these files:

- **`vendor_change` gets the grain declaration it never had.** It was the only table in
  `schema.sql` without one, and `.claude/rules/graph-grain.md` requires one per table. Identity is
  the tuple `upsert_vendor_change` hashes, and the oasdiff at-least-once exemption belongs in it.
- **The vocabulary is named on all three columns**, in the convention four other columns already
  use, with the argument above written where a future reader will look for it.
- **Eleven tests, fifteen cases**, against a real server, pinning: that Postgres accepts the value in all three
  columns; that the model refuses it, asserted beside a valid construction so the refusal cannot
  come from a missing field; that every member round-trips through all three columns; that the
  vocabulary is exactly five members; that no read answers for an unparseable row; that the two
  cases raise disjoint types; that no CHECK stands over a severity column; that a CHECK in a
  column definition does not reach a database that has the column; that `apply_schema` converges
  twice over a violating row; and that one module writes these tables.

The fixture is not new. `tests/fixtures/graph/vendor_change_rows.json` is W107's, and its
`off-literal-severity` row already carries `catastrophic`. Both files read the one fixture, so if
`Severity` ever gains that member both stop testing what they claim on the same commit rather than
one of them quietly retiring its coverage.

## Mutation table

Every test here pins behaviour that is already correct, so "fails first" was established by
breaking what each one covers. Harness at `%TEMP%\w112_mutate.py`, not committed. It runs
`uv run pytest tests/test_severity_vocabulary.py -p no:randomly -n0 --color=no -q --tb=no -rf`
against a database it drops and creates for each run, so a mutation to `schema.sql` is measured on
a database built from the mutated file — the configuration in which an inline CHECK is present at
all. Baseline: **15 passed**, re-established at 15 after the last mutation.

| # | File | Mutation | Verdict | Killed by |
|---|---|---|---|---|
| 1 | `store.py` | a word added to the module docstring | **SURVIVED**, 15 passed | — the harness is not blind |
| 2 | `store.py` | unbalanced paren in `_stable_id` | **DID-NOT-COMPILE** | `compile()`, before pytest ran |
| 3 | `schema.sql` | an anchor that is not in the file | **NOT-APPLIED** | the harness, before any run |
| 4 | `schema.sql` | a two-line anchor spelled with `\n` against a CRLF file | **ANCHOR-MISSED** | the harness — matches only after translating to `\r\n` |
| 5 | `schema.sql` | inline `CHECK (severity IN (<the five>))` on `vendor_change.severity` | **KILLED**, 5 failed | `…no_check_constraint_stands_over_a_severity_column`, `…postgres_stores_a_severity_the_model_refuses…`, `…no_read_answers_for_a_row_it_cannot_parse`, `…already_tells_an_absent_row_from_one_it_cannot_read`, `…apply_schema_converges_over_a_database_holding_a_row…` |
| 6 | `schema.sql` | inline `CHECK (severity IN ('breaking'))` — a guessed domain | **KILLED**, 9 failed | the five above plus four of the five `…every_member_of_the_vocabulary_survives_a_round_trip…` cases. **This is the row that shows the round-trip test earns its place**: without it a CHECK that rejects four fifths of the vocabulary passes everything else in the file. |
| 7 | `schema.sql` | table-level `DROP CONSTRAINT IF EXISTS` + `ADD CONSTRAINT … CHECK`, validated | **KILLED**, 5 failed | the same five. The idempotence test is the one that matters here: the constraint applies cleanly until a violating row exists, then 23514. |
| 8 | `models.py` | `Severity` narrowed — `warning` retired | **KILLED**, 1 failed | `…the_vocabulary_is_exactly_these_five_members`. The only thing in the repository that notices: no persisted row anywhere holds `warning`. |
| 9 | `models.py` | `Severity` widened — `catastrophic` added | **KILLED**, 5 failed | `…the_vocabulary_is_exactly_these_five_members`, `…postgres_stores_a_severity_the_model_refuses…`, `…the_model_refuses_the_value_the_database_accepted`, `…no_read_answers…`, `…already_tells_an_absent_row…`. Widening the vocabulary to include the fixture's value fails loudly instead of retiring the coverage. |
| 10 | `store.py` | `get_vendor_change`'s absent case raises `ValueError` instead of `KeyError` | **KILLED**, 1 failed | `…already_tells_an_absent_row_from_one_it_cannot_read` — which is the test the next task's argument rests on |
| 11 | `graph/__init__.py` | a second module carrying `INSERT INTO finding (` | **KILLED**, 1 failed | `…the_store_is_the_only_module_that_writes_a_severity_column` |

**No survivals** other than the control, and no verdict differed from what was expected of it.
`models.py` is a file this task is forbidden to modify; mutations 8 and 9 were applied for
measurement and restored from the original bytes in a `finally`, and `git status` was clean
afterwards.

### False-verdict modes, and which were reproduced

All six the brief names are answered, and four were reproduced on purpose as controls:

- **Killed vs survived read from colourised prose.** `--color=no`, and the verdict comes from
  pytest's summary *counts* (`N passed`, `N failed`, `N error`), never from `FAILED ` line
  prefixes. Those lines are parsed only to attribute a kill.
- **Did-not-compile arriving as a kill.** `compile()` runs on the mutated Python before pytest is
  invoked. **Reproduced** — row 2.
- **Unreadable.** Any exit code outside `{0, 1}` is UNREADABLE, not a survival. `-n0` on focused
  runs, which `pyproject.toml`'s own `-n auto` would otherwise collide with.
- **Baseline-drifted.** Zero failures at a pass count that is not the baseline is BASELINE-DRIFTED,
  not SURVIVED. This is also what catches a skipped test, which exits 0 from the child. Row 1 is
  the blind-harness check: a docstring word must survive at *exactly* 15.
- **Not-applied.** The anchor must occur exactly once; absent or ambiguous is NOT-APPLIED before
  any run. **Reproduced** — row 3 (M3-W109's mode).
- **Anchor-missed.** An anchor containing `\n` that matches only after translation to `\r\n` is
  ANCHOR-MISSED rather than NOT-APPLIED, because the two have different repairs. **Reproduced** —
  row 4 (M3-W108's mode). Every file in this tree is CRLF: `schema.sql` 297 CRLF and 0 bare LF,
  `store.py` 695 and 0.
- **`pytest -q; echo $?`.** The harness reads `CompletedProcess.returncode`; no shell reports on
  pytest's behalf. The child gets `PYTHONIOENCODING=utf-8` and the harness decodes with
  `errors="replace"`.

A seventh mode this harness had to handle that the brief did not name: **DID-NOT-APPLY.** A
mutation to `schema.sql` can leave DDL that Postgres refuses, which errors every test at fixture
setup and produces exit 1 with zero `failed`. Classified separately from KILLED, since a schema
that does not apply has measured nothing. No row reached it.

## Which scheduler each measurement used

- Focused runs while iterating, and **every row of the mutation table**: `-n0`, serial, explicitly
  passed to override `pyproject.toml`'s `-n auto`.
- The four gates below and the full-suite count: the repository's own `-n auto` (xdist).
- The database survey and the DDL probes: no pytest — direct `psycopg` against 5433.

`SYNC_DSN` was pinned to `sync_w112` for iteration and `sync_w112_mut` for the harness, both
created by this task and both dropped by it. The probe databases `sync_w112_probe`,
`sync_w112_fresh` and `sync_w112_aged` were created and dropped by their probes. No database this
task did not create was written to, and the survey of the other 214 was read-only.

## Gates

| Gate | Exit | Result |
|---|---|---|
| `uv run pytest -q` | 0 | 2656 passed, 2 skipped, 141s, under `-n auto` |
| `uv run python scripts/lint_encoding.py src scripts tests` | 0 | clean |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 0 | 95 files, 201 dependencies, `sync.core depends on nothing` KEPT |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | 0 | clean, including the reference from `schema.sql` to this file |

The suite grew by exactly the fifteen cases added here, and that is measured rather than inferred
from the pass count: `--collect-only` reports 2658 selected on this branch against 2643 at the
commit it branched from, which with two skips is 2641 passing there. The brief's figure of 2639 was
two behind whatever landed before this task started.

## What is left, in priority order

1. **Narrow `_change_for` and `_site_for` in `src/sync/mcp/tools.py`** to `except LookupError`,
   and replace `test_the_three_silences_are_one_answer_to_an_agent` with one that keeps the two
   correct silences together and separates the third. The argument and the diff are above. This is
   the repair that addresses every write route including the narrowing drift.
2. **`vendor_change.source` has no vocabulary comment**, and it is the second of the four shapes
   that reach the same silence. One line, the same convention.
3. **`finding.status` and `migration_outcome.strategy`** are the remaining closed-vocabulary
   columns with neither comment nor constraint.
4. **When a real migration mechanism arrives** — `apply_schema`'s docstring names the conditions —
   the CHECK becomes cheap, because `DROP CONSTRAINT IF EXISTS` + `ADD … NOT VALID` can then be
   generated from `sync.core` rather than copied into `schema.sql` by hand. The reason to decline
   it today is the copy, not the constraint.
