# Twenty-one unexecuted statements in the mutation engine, and what each one costs the label

M3-W99. `sync.benchmark.mutate` synthesises the labelled pairs binding precision and recall are
scored against. Twenty-one of its statements had never run — nineteen are places the engine
declines to mutate a site, one raises, and two produce a mutated source. Thirteen are reachable
through its two public functions and are now covered; eight are unreachable, and this says why
rather than reaching them by calling internals.

This is the fifth module examined this way and the first that is part of the **instrument** rather
than the product. That changes what a defect costs. A wrong answer in a detector loses a finding
and the number falls. A wrong answer here moves the *label*, and
`2026-07-29-sync-verification-regime.md` records that failure having already happened once — recall
read 1.0000 against a corpus that shared the binder's blind spot, and fell to 0.8000 the moment the
corpus was fixed. The corpus is frozen now and its precision is a CI gate, so a bad label is gated
*on* rather than merely reported.

**No production code changed.** Two of the twenty-one statements are redundant in the forward
direction and both were deliberately left; the argument is in "Redundant, unreachable, and the
difference" below.

## Coverage, before and after

Both figures come from the same command, run over the whole suite:

    uv run pytest -q -p no:randomly --color=no --cov=sync.benchmark.mutate --cov-report=term-missing

Before, at `88e0620`, which was `origin/main` when this branch was cut and with no edit in the tree:

    src\sync\benchmark\mutate.py     213     21    90%   164, 210, 226, 239-240, 281, 291, 321,
                                                        346, 370, 374, 440, 456, 468, 528, 531,
                                                        539, 561, 564, 572, 587
    1 failed, 2367 passed, 2 skipped in 314.59s

After:

    src\sync\benchmark\mutate.py     213      8    96%   164, 370, 456, 468, 539, 561, 572, 587
    1 failed, 2388 passed, 2 skipped in 120.82s

No statement was added or removed, so the line numbers are the same in both columns. Twenty-one
tests were added, all in `tests/test_mutation_declines.py`, and `git diff --stat` against the base
is that one file and nothing else. `src/sync/benchmark/` is byte-identical between this branch and
`origin/main` as it now stands, eleven commits later, so these figures still describe the module a
merge would land against.

**The one failure is in both columns, it is the same test, and chasing it found a real defect in
`tests/conftest.py` — see "The `--cov` failure is a defect, and it is bigger than one red test"
below.** `uv run pytest -q`, which is the gate as the brief specifies it and the form CI runs, is
**2389 passed, 2 skipped, exit 0**. The failure appears only when `--cov` is on: two of two
coverage runs failed and two of two plain runs passed. It also failed in the "before" run with
nothing of this task's in the tree, which settles attribution.

### The `--cov` failure is a defect, and it is bigger than one red test

This started as "measure the coverage before you start" and ended somewhere else, so it is recorded
here rather than dropped. `tests/conftest.py` is forbidden to this task and nothing below was
changed.

`sweep_leaked_databases` wraps its connection in `try: ... except psycopg.Error: return []`, and its
docstring is explicit about why: *"**Nothing here may fail the run.** Cleanup that breaks a suite is
worse than the leak it fixes."* Under `pytest-cov` that handler does not catch, and the reason is
not the exception's type but its **identity**. Measured from inside a scratch test under
`-n0 --cov`, on `psycopg.connect("postgresql://…@localhost:1/postgres", connect_timeout=10)`:

    raised   psycopg.errors.ConnectionTimeout @ 1404256365968
    attribute psycopg.errors.ConnectionTimeout @ 1404278453376     same_class = False
    the raised class's MRO `Error` @ 1404256347120  is not  psycopg.Error @ 1404278455360
    isinstance(exc, psycopg.Error) = False
    sys.modules holds exactly one 'psycopg.errors'

Two sets of psycopg's exception classes coexist in the process. `psycopg_binary._psycopg` — the C
extension that raises this one, from `generators.pyx:67` — holds one set, and
`sys.modules["psycopg.errors"]` exposes another, so `except psycopg.Error` names a class that is not
in the raised exception's MRO. `isinstance` says False and the MRO prints `['ConnectionTimeout',
'OperationalError', 'DatabaseError', 'Error', 'Exception']`, which is why reading the traceback
alone makes the handler look correct. Why enabling coverage produces the duplication is not
established here; the timeout itself elapses with or without it, so the timing is not the variable.

> **Correction, 2026-07-30, by the coordinator. Everything from "Under `pytest-cov` that handler
> does not catch" to the end of the paragraph above is wrong.** The class-identity mechanism does not
> exist. This report's own scratch probe, re-run under the configuration it names, reports the
> opposite of what it recorded:
>
>     same_class = True    is_same_Error = True    isinstance = True
>
> `psycopg_binary._psycopg` is in `sys.modules`, but it does not hold a second set of the classes
> that matters, and `psycopg.Error` is in the raised exception's MRO by identity. Three independent
> checks agree: this probe under `-n0 --cov`; a full `-n0 --cov` suite run at 2441 passed, exit 0,
> 741 s, with zero occurrences of `psycopg.Error` or `ConnectionTimeout` in its output; and the
> parallel coordinator's own MRO check, which returned `True` for both `OperationalError` and
> `psycopg.Error`.
>
> **The failure this paragraph was chasing is real, and the cause is elsewhere.** The parallel
> coordinator found it, and it is one gap between two guarded regions rather than a broken handler.
> `conftest.py`'s admin connect catches `psycopg.OperationalError`; `sweep_leaked_databases` catches
> `psycopg.Error` twice, at the inner DROP and around the whole body. Between them sits the block
> where the run creates its own database — the `with conn:` that issues `DROP DATABASE … WITH
> (FORCE)` and then `CREATE DATABASE` — and that block has **no `try` and no `except` at all**.
> Anything psycopg raises there escapes `pytest_configure` and takes the session before collection,
> which is the observed shape. A `ConnectionTimeout` is one way in; likelier on a busy container is
> a transient failure dropping a database another run still holds, since `WITH (FORCE)` still needs
> the lock.
>
> So the consequence stated below stands and the mechanism above does not. What was wrong was not
> the observation but the explanation, and a wrong explanation stated as measured fact is worse than
> none — it sent two readers to `psycopg_binary._psycopg` before anyone read the twelve lines
> between the two handlers.
>
> A fix is still not this report's to choose, and the open question is what it should do rather than
> where it goes. The parallel coordinator argues for failing loudly rather than warning and
> continuing, and the argument is worth carrying: the connect case can honestly say "no server, the
> tests needing one were going to fail anyway", while this case cannot — the server is there, the
> run could not make its own database, and continuing unisolated would put a run's writes into
> whatever `SYNC_DSN` already pointed at.

**Two consequences, and the second is the one that matters.** The red test is cosmetic — it asserts
exactly this contract, so it is doing its job. But `sweep_leaked_databases` is also called from
`pytest_configure` (`conftest.py:311`), where an escaping exception takes the **whole session**
before collection, not one test. So a coverage run against a Postgres that times out rather than
refusing — a container starting, a busy server, a wrong port — dies at configure time with a
`ConnectionTimeout` and no tests at all, and the file's stated invariant is void in exactly the
situation it was written for.

The fix is not obvious and is not this task's to choose. `except Exception` would restore the
invariant and lose the type discipline; catching `psycopg.Error` *and* re-checking by name is
worse. Reporting it is the right move.

## The twenty-one

| # | Statement | Input that reaches it | Is declining right? | What the caller observes |
|---|---|---|---|---|
| 1 | `164` — `_same` returns False for a None handle | **Nothing.** `_same`'s two callers pass `parent.field(value_field)` and a node; a binder node whose value field is None never has a call-or-wrapper child. See below. | Unanswerable — the condition cannot occur | — |
| 2 | `210` — **raises** on a supported kind naming no field | a `request-property-removed` whose oasdiff `text` carries no backticked token, so `changed_field` answers None | Yes, and raising rather than declining is the right contract. See "Why 210 raises". | **`ValueError` naming the change id.** The scored run stops. |
| 3 | `226` — `continue`, pre-scan | any site in the tree, targeted or not, whose suffix `_MUTABLE_LANGUAGES` does not name | Yes. The alternative is refusing the pair, so one Ruby file anywhere in a real checkout would cost the whole specification. | **Nothing.** The pair is produced; that site is labelled unaffected. |
| 4 | `239-240` — appends to `unreachable` | a **target** whose suffix is not mutable | Yes. Nothing broke it, so unaffected is the honest label — and naming it is what stops the honesty from being invisible. | **`MutationPair.unreachable`**, which reaches an artifact. The only decline in this module that does. |
| 5 | `281` — `depends_on_change` returns False | a fieldless change, or a path with no grammar | Yes, and note it is the *same input* as row 2 answered differently: this function produces no label, so it has none to protect. | **`False`.** `score_pair` reads it as "the tree does not carry the change here". |
| 6 | `291` — `_already_depends` returns False | a recorded line/col naming no call | Yes. An unparseable position cannot be shown to already carry the field. | **`False`**, and the pre-scan does not refuse the tree. |
| 7 | `321` — `_mutate` returns None | the same input as row 6, in the edit half | Yes, and None rather than an exception is deliberate: a call the mutation cannot attach to is ordinary in a real repository. | **`unreachable`**, via row 4's append at 244. |
| 8 | `346` — **inserts** into an empty mapping literal | a call passing `{}` — TypeScript `object` or Python `dictionary` | Not a decline. `{}` needs no separator and `{ limit: 3 }` does. | **A mutated source**, and a label that says affected. |
| 9 | `370` — `_insert_keyword_argument` returns None | **Nothing.** A `call` node always carries an `arguments` field. See below. | Unanswerable | — |
| 10 | `374` — **inserts** into an empty argument list | a Python call written `list()` | Not a decline. `list()` needs no separator and `list(other)` does. | **A mutated source**, and a label that says affected. |
| 11 | `440` — `_call_at` returns None | a recorded line/col that is not the exact start of a call | Yes, and the exactness is the point: a merely-containing call would put the label on a site nobody chose. | **`unreachable`**, through rows 6 and 7. |
| 12 | `456` — `_object_argument` returns None | **Nothing.** Same as row 9. | Unanswerable | — |
| 13 | `468` — `_keyword_names` returns `set()` | **Nothing.** Same as row 9. | Unanswerable | — |
| 14 | `528` — TypeScript identity check | assigning to a call's result: `list() = 1`, `(list()) = 1`, `list()! = 1`, `list() as any = 1` — all four are trees `tsc` rejects and tree-sitter parses | Yes, and **the statement is redundant** — 531 refuses every input that reaches it, one line later. See below. | **`unreachable`**, and the source byte-identical. |
| 15 | `531` — TypeScript target is not a plain identifier | `const { data } = list()`, `const [first] = list()`, `order.page = list()` | Yes. A destructuring pattern binds the *fields* and a property target binds something whose lifetime is the object's; writing `data.has_more` off either manufactures a labelled positive no correct binder can find. | **`unreachable`**, and the source byte-identical. |
| 16 | `539` — `_result_binding` falls out of its loop | **Nothing.** Reaching it requires climbing to the root through wrapper kinds only, and the root node is `program`, which is not a wrapper. | Unanswerable | — |
| 17 | `561` — Python identity check | **Nothing.** Python's grammar never parents a call-or-wrapper off `assignment`/`named_expression` in a non-value slot; the error recovery reparents to `ERROR`. | Unanswerable, and redundant if it were reachable — 564 subsumes it exactly as 531 subsumes 528 | — |
| 18 | `564` — Python target is not a plain identifier | `a, b = list()`, `order.page = list()`, `cache['k'] = list()` | Yes, same argument as row 15. | **`unreachable`**, and the source byte-identical. |
| 19 | `572` — `_python_result_binding` falls out of its loop | **Nothing.** Same as row 16; the Python root is `module`. | Unanswerable | — |
| 20 | `587` — `_reads_field` skips a member with a missing side | **Nothing.** `attribute` and `member_expression` require both sides in both grammars; a partial read parses to `ERROR`, not to a half-built node. | Unanswerable | — |

Thirteen declines observed. **Twelve of the thirteen are invisible to everything except
`unreachable`, and one raises.** That is a better ratio than the four modules examined before this
one, where every decline reached nobody.

## Why lines 346 and 374 were uncovered, and what it means for the corpus

The brief put this as the sharpest question: they are the branches that *produce* a mutated
source, so if neither had run, either the corpus never takes those paths or something else
produces the pairs and these are dead alternatives.

**Neither. They are the empty-container halves of the two rewrites, and their non-empty siblings
are covered.** `_insert_property` ends in two returns one line apart — 345 for a literal that
already holds an entry and therefore needs a trailing comma, 346 for one that does not.
`_insert_keyword_argument` ends the same way: 376 for an argument list with something in it, 374
for one without. 345 and 376 have always been covered.

So nothing else produces the pairs, nothing is a dead alternative, and **all twelve proposed
specifications are scored through the covered halves.** Every site the frozen corpus mutates
already passes at least one entry or one argument, which is what real Stripe call sites look like:
nobody writes `stripe.paymentIntents.create({})`.

The two are covered anyway, and the reason is not completeness for its own sake. The separator is
the whole difference between the pair of returns, and it is the kind of difference that is wrong in
exactly one direction and silently: a comma too many produces `{ limit: 'sync-benchmark', }`,
which TypeScript accepts and Python's `ast` accepts, so a mutation with the branches swapped would
produce a *valid* tree carrying a *correct* label and nothing would notice. Both mutations of 346
and both of 374 are killed by the new tests, so the separator is now pinned in both directions.

One qualification on 374 that is not a defect but is worth knowing: the insertion is trailing, and
for an empty argument list the leading and trailing forms coincide, so this is the one branch where
the comma reasoning `_insert_keyword_argument`'s docstring argues for is paid for nothing. The
docstring is still right for every other input.

## Who reads `unreachable`, and whether a scored run would notice it growing

**This module is the counterexample the brief was looking for.** Four tasks in a row found declines
that reach nobody; `unreachable` reaches an artifact:

- `MutationPair.unreachable` → `score.py:324` → `ScoredPair.unreachable_targets`
- → `scripts/score_corpus.py:181`, qualified by pair name because a call site id is only unique
  within a repository → `CorpusScore.unreachable_targets`
- → rendered twice: a per-pair `unreachable` column, and then every target named under *"Targets
  the mutation could not attach to, labelled unaffected"*
- → and into the score JSON, which is what CI hands to `gate_corpus.py`.

The recorded score carries **7**, all response-side:

    fireship-server-GetPaymentMethods-response-property-removed::1292e9cc…
    furever-PostPaymentIntents-response-property-removed::885d560f…, 8f9aa532…, df2e6332…, f82eeb47…
    remix-PostPaymentIntents-response-property-removed::833ff938…
    turbo-PostRefunds-response-property-removed::029f6fe8…

`mutate.py:511` says *"Five of the corpus's eleven unreachable targets are the first, two are the
second"*. Its breakdown sums to seven and matches the recording exactly — all seven are
response-side, which is the only side `_result_binding` declines on — so the total is the part that
looks stale, from before B34 widened the binding forms. It is a comment on a covered line and not
this task's to edit, but a reader comparing the two numbers will be confused by it.

**Would a scored run notice the count growing? A human reading the output, yes. CI, no.** The
figure is printed and recorded, and nothing compares it against anything.

## Whether a decline can silently shrink the corpus

**Yes, and none of the four floors would fire.** This is the most consequential thing in the
report.

A target that stops being mutable stops being broken, so `generate_pair` labels it unaffected —
correctly. Follow that through `gate_corpus.py`'s four floors:

| floor | recorded | after one target goes unreachable |
|---|---|---|
| `PRECISION_FLOOR` 1.0000 | n=26 | **1.0000**, n=25 — by `falsifiable_negatives`' own reasoning rather than by measurement: the newly-negative site has no field read, and `_deepest_match` over an empty list returns None whatever the change, so the detector emits no finding for it and there is no false positive. |
| `RECALL_FLOOR` 1.0000 | n=26 | **1.0000**, n=25. Recall's n is the count of labelled positives; it falls, the rate does not. `check()` reads `samples` only to word a message. |
| `FALSIFIABLE_NEGATIVES_FLOOR` 7 | 7 | **7 or 8.** It is a floor, so an increase passes; and the newly-negative site is not a candidate anyway, by the same filter as the precision row. |
| `PAIRS_SCORED_FLOOR` 17 | 17 | **17.** `aggregate` scores a pair whose every target went unreachable — deliberately, and `CorpusScore.pairs`' docstring says so. |

So the gate stays green over a corpus that quietly stopped covering part of itself, which is the
exact failure `PAIRS_SCORED_FLOOR` was added to catch one level up. The verification-regime spec's
argument for freezing — *"a pair regenerated each run scores a different input set each run, so a
movement in the number means nothing"* — is what this defeats, and the reason it can be defeated
is worth stating plainly:

**`mutate.py` is an unpinned input to the frozen corpus.** The corpus pins its checkouts three
ways (`repositories.yaml`: commit, subpath, `tree_digest`) and its symbol map by digest
(`scripts/symbol_map_pin.py`, which `gate_corpus.py` refuses a score without). The generator that
turns those pinned inputs into labels is pinned by nothing. Edit a decline in this file and the
labelled input set changes without a single pinned digest moving.

**What would catch it, priced rather than built.** A fifth floor in the shape the file already
uses: `AFFECTED_SITES_FLOOR = 26`, or equivalently a floor on recall's `n`, declared beside the
four with the recorded figure and the argument. It is three lines and one assertion in
`test_every_floor_is_the_figure_the_corpus_recorded`, which already pins the other four against the
recording. `scripts/gate_corpus.py` is forbidden to this task, so it is reported.

Two notes for whoever adds it. The figure to floor is `affected_sites`, not `len(unreachable_targets)`
— a ceiling on the declines would fire on an honest corpus edit that adds a pair with an unreachable
target, and the thing actually worth protecting is the number of positives the score is computed
over. And it wants the same `_rate`-style derivation the other two use, over the per-rung integers
rather than over `affected_sites`, so a floor and a rate can never disagree about the same corpus.

## Why 210 raises, and whether raising is right

`generate_pair` raises `ValueError` when `changed_field` answers None for a kind
`SUPPORTED_KINDS` admits — an oasdiff record whose `text` carries no backticked token, since
`changed_path` deliberately has no fallback to the URL path.

**Raising is right, and it is a different contract from declining on purpose.** Declining would
produce a tree nothing was written into. Every label on it would say unaffected, the detector would
still fire on whatever it found, and the pair would score as a run of pure false positives. Read
off the corpus output that is a pipeline hallucinating, not a generator that had nothing to write —
and it is the same argument `UnsupportedChangeKind`'s docstring makes for the refusal three lines
above it, which is why the two belong together rather than one raising and one declining.

The contract is *not* interchangeable with `depends_on_change`'s, and the two are one function
apart. Row 5 of the table is the same fieldless change reaching the audit half, which returns
`False`. That is also right: it produces no label, so it has no label to protect, and "nothing
depends on a change that names no field" is a true answer to the question it was asked. Both are
now pinned, in the same file, adjacent, so the asymmetry is visible in the suite rather than only
here.

Where a raise would be wrong is the case this module already gets right: `_mutate` answering None.
A call the mutation cannot attach to is ordinary in a real repository, and abandoning a whole
checkout over one of them would be a generator refusing the corpus rather than describing it.

## Whether a mutation is always detectable as a mutation

`MUTATION_LITERAL` is `'sync-benchmark'` and appears in both rewrite branches. The brief's worry:
if a real repository already contains that literal, the label and the source agree by coincidence.

**The literal is not what would go wrong, because nothing matches on it.** The label claims a
dependency on a *field*, and every reader of that claim reads the field name:
`depends_on_change` → `_declared_keys` / `_keyword_names` / `_reads_field`, all of which compare
key and property *names*. `grep` over `src/` and `scripts/` finds `MUTATION_LITERAL` in
`mutate.py`'s four rewrite returns and in the `sync.benchmark` re-export, and nowhere else — no
detector, no scorer and no gate consults it. A repository that happened to pass
`'sync-benchmark'` as some other field's value changes no label at all — pinned in
`test_a_site_already_naming_the_field_refuses_the_tree_rather_than_relabelling_it`, deliberately in
the same test as the case that does matter, so the two cannot be confused.

**The collision that could move a label is a call site already declaring the field, and it is
guarded — by a raise over the whole tree, before any pair exists.** The pre-scan at 223–231 walks
*every* site, not only the targets, and `_already_depends` refuses by name. That is the guard, it is
loud, and `mutate.py`'s "Guarding the exactness" section is the argument for it.

Two honest limits on that guard, neither a live defect:

- **A computed key is not seen.** `_declared_keys` counts literal keys only, and says why: a
  computed key names no field anyone can compare against. So `{ [k]: v }` where `k` evaluates to
  the field escapes the pre-scan. The mutation then writes the field in as well, and the label
  still says affected, which is still true of the source — so this is a duplicate entry rather
  than a mislabel.
- **`**kwargs` is not seen either**, for the same reason: `_keyword_names` reads `keyword_argument`
  children and a splat is `dictionary_splat`. `list(**params, limit='sync-benchmark')` is legal
  Python that raises `TypeError` if `params` carries `limit` — but nothing executes a corpus
  checkout, and the label describes what the source names, which it does.

Neither is worth a guard. Both are worth knowing before someone reads the pre-scan as exhaustive.

## Redundant, unreachable, and the difference

**Eight statements are unreachable.** The evidence is three independent kinds, and the third is
decisive:

1. **Structural.** For 539 and 572 the loop can only fall through if the walk climbs to the root
   through wrapper kinds only, and the root node is `program`/`module`, which no `_RESULT_WRAPPERS`
   set contains. For 370, 456 and 468 a `call`/`call_expression` node only exists if there is an
   opening paren, and then the `arguments` field exists too — possibly with a MISSING close paren,
   never absent. For 587 both grammars require both sides of an `attribute`/`member_expression`. For
   164 the None handle can only arrive from a binder node whose value field is None, and such a node
   never has a call-or-wrapper child. For 561, Python's `assignment` takes a *pattern* on the left,
   never a call or a wrapper, and `f() = 1` and `(f()) = 1` both reparent into `ERROR` — measured.
2. **Empirical, over real bytes.** A sweep over 306 committed Python files and 66 committed
   TypeScript files found **zero** instances of any of: a call node without `arguments`, a read node
   missing a side, or a binder node with a non-value call-or-wrapper child.
3. **The whole suite, with all eight replaced by `raise AssertionError` at once**: 2389 passed, 2
   skipped, exit 0. Nothing anywhere in the suite arrives at any of them.

**Two statements are redundant in the forward direction, and they are a different thing from
unreachable.** 528 *executes* — the four TypeScript assignment-to-a-call-result shapes reach it —
and deleting it changes no answer, because for every input that reaches it, 531 refuses one line
later. That is provable rather than measured: `assignment_expression` has exactly `left` and
`right`, so a child that is not the value *is* `left`, and the child's kind is by construction a
call or a wrapper and therefore never `identifier`. `variable_declarator`'s `name` slot gives the
same argument, and its `type` slot never holds a bare call or wrapper — probed across eight
spellings including `let x: f() = 1` and `let x: typeof f() = 1`.

Measured, not merely argued: with 528 deleted the suite is green; with 528 deleted **and** 531
relaxed to `if target is None`, seven tests fail.

561 is the same clause on the Python side, and it is both — unreachable outright, and subsumed by
564 by the identical argument if it were ever reached.

**Neither was removed.** `2026-07-29-hand-written-symbol-maps.md` and
`2026-07-29-typescript-symbol-reader.md` reached this verdict on five clauses across three modules
and left all five, and the reason transfers exactly: it is a production change no test proves
necessary, and here the clause makes the function's central claim — *the call must be the value the
name receives* — true by construction rather than by an accident of which grammar node comes first.
`_result_binding`'s own docstring at 524–526 argues for it against a defect that reached the corpus,
and deleting the statement that argument is attached to would leave the argument pointing at
nothing.

**Which kind each of the eight is.** 164, 370, 456, 468, 587 are *unfalsifiable by any fixture* —
the condition cannot occur, so no input makes them observable, and nobody should go looking for the
fixture. 539 and 572 are unfalsifiable *and* redundant: Python returns None off the end of a
function, so the explicit `return None` is explicitness rather than logic. 561 is unfalsifiable and
subsumed. 528 is the only one that is reachable and redundant.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the statement
each covers. Harness at `%TEMP%\w99\mutate_harness.py`, not committed. It runs
`pytest -q --color=no -n0 -p no:randomly` over the six files that exercise this module, asserts each
mutation string matches exactly once, `compile()`s the mutated source before pytest sees it, and
classifies from the summary *counts* rather than from line prefixes. Baseline asserted green at 73
passed before the run and 73 passed after every run, so a survival is distinguishable from a blind
harness.

| # | Statement | Mutation | Outcome | Detail |
|---|---|---|---|---|
| M-210 | 210 | raise replaced by a substituted field | KILLED | 1 failed |
| M-210' | 210 | raise replaced by an early empty pair | KILLED | 1 failed |
| M-226 | 226 | pre-scan skip deleted | KILLED | 2 failed |
| M-226' | 226 | pre-scan skip coerced to `typescript` | KILLED | 1 failed (after the fixture was fixed; **SURVIVED** before) |
| M-239 | 239-240 | an unparseable target labelled affected | KILLED | 1 failed |
| M-239' | 239 | records nothing, only skips | KILLED | 1 failed |
| M-281 | 281 | the audit half answers True | KILLED | 2 failed |
| M-291 | 291 | no call at the position answers True | KILLED | 2 failed |
| M-321 | 321 | no call at the position returns the source unedited | KILLED | 2 failed |
| M-346 | 346 | the empty literal takes a trailing comma | KILLED | 2 failed |
| M-346' | 346 | the empty literal is declined | KILLED | 2 failed |
| M-374 | 374 | the empty argument list takes a leading comma | KILLED | 1 failed |
| M-374' | 374 | the empty argument list is declined | KILLED | 1 failed |
| M-440 | 440 | falls back to a containing call | KILLED | 2 failed (after the fixture was fixed; **SURVIVED** before) |
| M-528 | 528 | the TypeScript identity check dropped | **SURVIVED** | redundant; 531 subsumes it |
| M-528+531 | 528 | identity check dropped *and* 531 relaxed | KILLED | 7 failed — names the subsuming clause |
| M-531 | 531 | a non-identifier TypeScript target accepted | KILLED | 3 failed |
| M-564 | 564 | a non-identifier Python target accepted | KILLED | 3 failed |
| M-164 | 164 | the None guard in `_same` deleted | **SURVIVED** | unreachable |
| M-370 | 370 | the missing-arguments guard deleted | **SURVIVED** | unreachable |
| M-456 | 456 | the missing-arguments guard deleted | **SURVIVED** | unreachable |
| M-468 | 468 | the missing-arguments guard deleted | **SURVIVED** | unreachable |
| M-539 | 539 | the loop-exhausted return deleted | **SURVIVED** | unreachable and redundant |
| M-561 | 561 | the Python identity check dropped | **SURVIVED** | unreachable and subsumed |
| M-572 | 572 | the loop-exhausted return deleted | **SURVIVED** | unreachable and redundant |
| M-587 | 587 | the missing-side guard deleted | **SURVIVED** | unreachable |

Seventeen of eighteen mutations over the thirteen reachable statements killed, and the one survival
is named by the mutation directly below it. Nothing failed to compile and nothing came back
UNREADABLE.

**The two false verdicts the harness produced, and both were the mutation rather than the code.**
The brief's rule — suspect the mutation, then the test, then the code — held for the eighth time on
this project:

- **M-226'** replaced `_language_for(...) or "typescript"` and passed. The Ruby fixture was
  `c = client.customers.list()`, which every grammar answers the same way about, so substituting a
  language changed no outcome. The fixture now passes a hash: `{ limit: 3 }` is byte-identical in
  Ruby and TypeScript, so reading the file under *any* grammar finds `limit` declared and refuses
  the tree. Both the deletion and the coercion now kill.
- **M-440** added a fallback to a containing call and passed. The fixture held no call at all, so
  the fallback had nothing to find. The position is now one byte inside a real call nested inside
  another, which gives a fallback two candidates and makes both wrong.

Both were test weaknesses that a two-outcome harness would have reported as "the statement is
redundant", which is the wrong conclusion about a load-bearing guard. That is the value of running
the mutation rather than reasoning about it.

### The four false-verdict modes, and which one bit

The brief named four and the harness answered all four by construction. Only one had to be
answered *before* the first useful run, and it is the encoding one — the run against the eight
unreachable statements is 25 pytest invocations, and `mutate.py`'s prose carries em dashes on
lines pytest renders when a test fails. Every child gets `PYTHONIOENCODING=utf-8` in its
environment and every read is `errors="replace"`; `encoding="utf-8"` on the call chooses how to
decode arriving bytes, not which bytes arrive. `-n0` rather than `-p no:xdist`, `--color=no`, and
`compile()` first cover the other three. None of the four produced a verdict in this run, which is
what "answered by construction" is supposed to look like.

## Fixtures and provenance

**No fixture file was created.** Every input is an inline source string at the assertion, which is
how `test_result_binding_identity.py` and `test_python_response_binding.py` already state a
constructed shape — and for the inputs here that are deliberately *malformed* (a position one byte
off a call, four TypeScript trees `tsc` rejects, an oasdiff record naming no field), the fixture
*is* the claim being made. Putting it in a file one directory away would separate the claim from
the assertion resting on it.

`benchmark/corpus/` was not touched and nothing here reads it. No test calls a vendor API or a
model API.

## No defect was found in the production code

Twenty-one statements accounted for, thirteen covered, eight unreachable with three independent
kinds of evidence, and no production change. Two defects were found and fixed **in the tests
written by this task**, both before commit.

Three things are reported rather than repaired, each outside this task's files:

- **No floor protects the corpus's positive count** (`scripts/gate_corpus.py`), which is what lets
  a decline in this module shrink the scored input set with every gate green. Priced above.
- **`mutate.py:511` says "eleven unreachable targets" and the recorded score says seven.** Its own
  breakdown sums to seven, so the total predates B34 widening the binding forms. It is on a covered
  line.
- **`tests/conftest.py`'s `except psycopg.Error` does not catch under `pytest-cov`**, because two
  copies of psycopg's exception classes coexist and the extension raises the one the handler does
  not name. Reproduced deterministically in 10.21s with `-n0 --cov` on one test. It voids
  `sweep_leaked_databases`' stated "nothing here may fail the run" invariant, and the same function
  runs in `pytest_configure`, where an escape takes the whole session before collection.
