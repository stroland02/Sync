# Six declines on the surface a customer's agent talks to, and what it can tell apart

M3-W107. `src/sync/mcp/` is the product surface: four frozen tools and one resource, and
everything else in this repository is reached through them. M3-W83 hardened the transport
underneath it. Six statements in the two modules above the transport had never executed, and
five of them were a decline — a tool answering "nothing" to an agent that cannot distinguish
that from "nothing is wrong". The sixth refuses out loud, which is what made the comparison
worth making.

This follows the shape of `docs/superpowers/reports/2026-07-29-mcp-signal-refusals.md`, which
examined the signal source that watches a *vendor's* MCP server. That is a different thing from
this product surface, and using the same shape is what makes the two comparable.

## Coverage, before and after

Both figures come from the same command, run over the whole suite:

    uv run pytest -q -p no:randomly --color=no --cov=sync.mcp --cov-report=term-missing

Before, at `8187a9b`, the commit this branch left `main` from — 2545 passed, 4 skipped:

    src\sync\mcp\resources.py      39    2    95%   123, 143
    src\sync\mcp\tools.py          84    4    95%   291, 294-295, 344
    TOTAL                         297    6    98%

After, on the tree with `origin/main` merged in — 2576 passed, 4 skipped:

    src\sync\mcp\__init__.py        5    0   100%
    src\sync\mcp\propose.py        41    0   100%
    src\sync\mcp\registry.py       22    0   100%
    src\sync\mcp\resources.py      39    0   100%
    src\sync\mcp\server.py        106    0   100%
    src\sync\mcp\tools.py          84    1    99%   344
    TOTAL                         297    1    99%

Five of the six are covered. **No production file changed** — the diff is tests, one fixture and
this report. `tools.py:344` is not covered and is not coverable; the argument is below, with the
whole-suite probe that shows the condition never holds.

## The six

`tools.py:294-295` is two statements and appears as two rows, split by the two ways the block is
entered. They are not the same event and only one of them is a decline that is right.

| # | Statement | Input that reaches it | Is declining right? | What the agent observes |
|---|---|---|---|---|
| 1 | `tools.py:291` `return None` | a `Finding` whose `vendor_change_id` is null — two of the five detectors read telemetry and raise findings with no vendor change, which `Finding`'s own docstring records | Yes. The finding is a real answer and lacks a field it never had. | **A row**, carrying `change_kind: null`. |
| 2 | `tools.py:294` `except (KeyError, LookupError, ValueError)`, entered by `KeyError` | the reader answers "no such change" at its boundary — `GraphStore.get_vendor_change` raises when `fetchone()` returns nothing | Yes. `_site_for` makes the argument for the same catch: one dangling reference must not deny an agent every other answer. | **A row**, `change_kind: null`. Identical to 1. |
| 3 | `tools.py:295` `return None`, reached by `ValueError` | a row that **exists and does not validate**. `GraphStore.get_vendor_change` ends in `VendorChange(**row)`, and `pydantic.ValidationError` is a subclass of `ValueError`. | **No.** A graph holding a change it cannot parse is not a graph holding no change, and this is the one place on the surface where those two become one answer. | **A row**, `change_kind: null`. Identical to 1 and 2, and the frame is a success frame with `isError` false. |
| 4 | `tools.py:344` `return current` | a null `indexed_at` on a call site | Unreachable — see below. | **Nothing.** |
| 5 | `resources.py:123` `return []` | `resources/list` against a server built with no `FeedCache`, which `serve`'s signature makes a configuration rather than a fault | Yes. Advertising the six registered vendors would offer six URIs whose reads all fail, and a client that trusts a listing has no reason to handle a listed resource being absent. | **An empty listing.** The same answer a configured-but-empty cache gives, deliberately: `read`'s own comment settles that both are "no verified snapshot is available" and both are repaired by a fetch. |
| 6 | `resources.py:143` `raise ResourceError(...)` | a `resources/read` whose uri is outside `sync://feed/` | Yes, and out loud. | **A JSON-RPC error**, `-32002`, with `data.reason == "unknown_resource"` and the uri echoed back. |

Every one of these is reached through `serve` with scripted frames rather than by calling a
function, because what an agent acts on is the frame.

## `tools.py:294`: what can raise those three types *inside* the block

M3-W83 left a closely related narrowness in `server.py` and recorded why: `dispatch` raises
`KeyError` for an unknown tool and `TypeError` for an unknown argument, so a tool raising either
of those *internally* would be reported as "unknown tool" — and the reachability, not the shape,
is what made it safe. The same question, asked of this handler:

```python
def _change_for(self, finding: Finding) -> VendorChange | None:
    if finding.vendor_change_id is None:
        return None
    try:
        return self._graph.get_vendor_change(finding.vendor_change_id)
    except (KeyError, LookupError, ValueError):
        return None
```

**At the boundary.** `GraphStore.get_vendor_change` raises `KeyError` when the row is absent.
That is the decline the catch was written for, and it is the only one the code's own comment —
in `_site_for`, which carries the identical tuple — argues for.

**Inside.** The store's second statement is `VendorChange(**row)`. `pydantic_core.ValidationError`
inherits from `ValueError` (`ValidationError → ValueError → Exception`, verified against pydantic
2.13.4), so a row the model refuses is caught by the same clause and becomes an absent change.
Four shapes reach it: a `severity` outside the five-member `Severity` literal, a `source` outside
`ChangeSource`, a `raw` that is not a JSON object, and any field the deployed model requires that
the row does not carry. `vendor_change.severity` is `TEXT NOT NULL` in `schema.sql` with no CHECK
constraint, so the database is not the thing stopping it.

**Whether it is reachable today, through `GraphStore`.** No, on all three types, and each for a
different reason:

- `KeyError` is **not** reachable. `finding.vendor_change_id` is
  `TEXT REFERENCES vendor_change (id) ON DELETE SET NULL`, so a non-null value names a row that
  exists and deleting the change nulls the pointer rather than dangling it. That routes to line
  291, not to the catch. The clause's *intended* case is the one the schema already prevents.
- `LookupError` other than `KeyError` — nothing on the path raises `IndexError`.
- `ValueError` needs a `vendor_change` row written outside the model. Every write today goes
  through `insert_vendor_change(VendorChange)`, so the row was validated on the way in.

**What would make it reachable.** Two things, and neither is exotic. A row written by anything
other than `insert_vendor_change` — a restore, a hand-applied SQL repair, a backfill. Or model
and schema drifting: retire a `Severity` member, or add a required field, in a build that reads
rows an earlier build wrote. The column is untyped text and the model is a closed literal, so the
drift is one edit away and the database will not report it.

It is also reachable through any `GraphReader` that is not `GraphStore` — the Protocol is
structural precisely so one can exist — which is what `RowBackedGraph` in
`tests/test_mcp_tool_declines.py` is. That fake builds its models the way the store does rather
than looking up prebuilt ones, because a dict of models cannot reach the statement in question.

**Does a genuine internal fault reach an agent as an absent answer? Yes,** and it now has two
tests saying so. `sync_whats_at_risk` returns the row with `change_kind: null`, byte-identical to
a telemetry finding that never had a change. And `_evidence_for` — the other caller — puts `{}`
in `spec_diff`, which is the raw vendor record a human reviewer judges a patch by. "The spec diff
was empty" and "the spec diff could not be read" are one string there.

**One smaller thing.** `KeyError` is a subclass of `LookupError`, so the three-member tuple is a
two-member tuple written out. It has no behavioural effect and the same tuple appears in
`_site_for`.

## Can an agent tell a declining tool from a tool that found nothing?

**No, anywhere on the graph surface.** All four tools decline in a shape the agent already uses
for a successful empty answer:

- `sync_whats_at_risk` drops a finding whose call site cannot be read — `_site_for` returns
  `None` and the loop `continue`s — and `total` counts only the survivors. A page built from five
  findings of which one was unreadable is byte-identical to a page built from four.
- `sync_explain_call_site` returns `None` both for a line that was never indexed and for a line
  that was indexed and whose site will not read.
- `sync_whats_changed` returns an empty page both for a vendor nothing recorded and for a vendor
  recorded as having changed nothing. This one is documented and argued for, and the argument
  holds: raising would make an agent treat a knowledge gap as a failure.
- `sync_propose_patch` returns `None` for a finding the graph does not hold.

The envelope adds no channel. `binding_source` says how a binding was *established* — `static`,
`resolved`, `observed` — not whether reading it succeeded, and `indexed_at` is a freshness claim
rather than a completeness one.

`resources.read` is the counter-example on the same server: three outcomes, told apart by
`error.data.reason` rather than by prose, with a fourth (`unknown_resource`) for a uri this
server does not serve at all. The difference is not that resources are easier. It is that the
resource path was designed by writing the three outcomes down first, and the graph tools were
not.

### The same flattening reaches the rung, and that changed under this task

`finding.binding_rung` became an enforced column while this task was in flight:
`GraphStore.insert_finding` now refuses a finding whose rung is `unattributed` and names the
detector that raised it. So every finding the graph holds names a real rung — `static`,
`resolved`, `observed` or `unresolved` — and the surface answers `binding_source: "static"` for
all four of them. No row carries a rung at all.

`_envelope`'s docstring argues the constant is honest, and on its own terms it was: neither a
compiler pass nor telemetry runs in this server, so claiming `resolved` would assert something
nothing here established. What the enforcement changes is that the *finding* now carries a rung
established elsewhere, and `CLAUDE.md` is explicit that every artifact derived from a binding
carries the rung it came from, "and so does every artifact derived from it". A tool response is
one. An agent handed a claim resting on a span-to-operation correlation is told it rests on a
static binding.

Reported rather than repaired, for the same reason as the rest of this section: the rung is per
finding and `binding_source` is per response, so carrying it honestly means a field on the row.
`test_every_answer_reports_binding_source_static_whatever_rung_the_finding_names` pins the loss
across all four rungs, so the repair turns a test red on purpose instead of passing silently.

The new refusal changes nothing else about what an agent can receive. It is a write-side check;
`Finding` still defaults `binding_rung` to `unattributed` and constructing one is still legal, so
no read path and no tool signature moved.

### Whether the frozen schemas make this a finding rather than a fix

**The golden file does not forbid the fix, and that is itself worth recording.**
`tests/golden/tool_schemas.json` stores `name`, `description` and `inputSchema` for each of the
four tools, and nothing else — `schemas_as_data()` emits exactly those three keys and there is no
`outputSchema`. So the published freeze covers the **request** half of the contract and not the
response half. A response field added to `_envelope` would leave the golden file byte-identical,
and `test_every_response_carries_the_provenance_fields` asserts a subset (`<=`), so it would pass
too. The one artifact that exists to make a contract change deliberate would not see this one.

That leaves two candidate repairs, and the reason neither is applied here is not the freeze:

1. **Narrow the catch.** `except LookupError` in place of the three-member tuple lets a
   `ValidationError` escape, and `_call` already has the channel: it returns a result with
   `isError: true` naming the exception type. No new field, no schema movement. The cost is that
   it aborts the whole page for one bad row, which is exactly what `_site_for`'s docstring argues
   against — though `LookupError` still absorbs the dangling-reference case that argument is
   about, so the loss is confined to genuine faults. The mutation table below measures the blast
   radius: narrowing to `KeyError` is killed by four tests and nothing else in the MCP suite.
2. **Report per row.** Keep the row, and carry a count of rows whose change could not be read.
   Proportionate, and possible without moving the golden file — but it adds a response field to a
   published surface on the strength of a fault that is not reachable through `GraphStore` today.

Choosing between them is a design decision with a specification above it, the fault is not
reachable through today's write paths, and this task's brief scopes the work to testing. So it is
reported. What has changed is that the behaviour is now pinned: `test_the_three_silences_are_one_answer_to_an_agent`
compares the three payloads for equality, so a repair that distinguishes them turns it red on
purpose.

## Two statements that are redundant, and they are redundant differently

### `tools.py:343-344` is unreachable in the forward direction

```python
def _later(current: datetime | None, candidate: datetime | None) -> datetime | None:
    if candidate is None:
        return current
```

`_later` has one caller: `newest_index = _later(newest_index, site.indexed_at)`. `site` comes
from `_site_for`, which returns a `CallSite`, and `CallSite.indexed_at` is a non-optional
`datetime` with a default factory — pydantic refuses `None` for it. Nothing in `src/` or `tests/`
uses `model_construct`, so there is no validation-bypassing path that could produce one.

**The probe, rather than the reasoning.** `return current` was replaced by
`raise AssertionError("PROBE tools.py:344 taken")` and the **whole suite** was run: green, at the
same pass count as the baseline before and after. The condition never held, which is a stronger
statement than "no assertion changed".

Both of the categories earlier tasks distinguished apply. It is **deletable with the suite still
green** — which the probe already settles, since a statement that never executes cannot be
distinguished from any replacement of it, including its absence — and it is
**unfalsifiable by any conforming fixture**, because reaching it needs a `GraphReader` that
returns something other than a `CallSite`, which is a non-conforming implementation and not an
input. It is left in place: removing it means narrowing `candidate: datetime | None` with it, and
that is a refactor with no proved defect behind it.

`test_a_call_site_always_carries_an_index_time` pins the premise where the consequence lives, so
making `indexed_at` optional fails beside the code that would then need the branch rather than
silently bringing a dead branch to life.

### `tools.py:290-291` is executed, and its deletion is invisible

The opposite case, and the pair is why both are recorded. The `raise AssertionError` probe at
line 291 is **killed** — the guard is genuinely taken. But deleting the guard outright survives
the whole suite at the same pass count, because `get_vendor_change(None)` produces a `KeyError`
from every reader that answers an absent id that way, and line 294 catches it. Against
`GraphStore` specifically: `WHERE id = %s` with a Python `None` parameter compares against SQL
NULL and returns no rows, measured against the container on 5433 rather than assumed.

So the guard is **redundant in the forward direction, and it is 294-295 that masks it.** That the
masking is the cause rather than a blind test is shown by the compound mutation: delete the guard
*and* the catch together, and the run is killed — by `test_a_finding_that_names_no_vendor_change_is_still_a_row`
among others, the very test that covers line 291.

It stays, and not only out of caution. `GraphReader.get_vendor_change` declares
`change_id: str`; passing `None` violates the Protocol's own type, and the guard is what keeps
the surface inside its declared contract. Redundant against today's single implementation is not
redundant against the interface.

## The golden file did not move

`tests/golden/tool_schemas.json`, sha256 of the raw bytes, unchanged throughout:

    7070b152ee3ddd24e23144022704495b05451865568505c1a71ff253e23997fe

The mutation harness takes that digest before its first run and after its last, and stops if they
differ. Nothing in this task would have changed a schema; the four tools' names, descriptions and
input schemas are untouched, and no production file changed at all.

A digest is also now pinned by test. `test_the_published_tool_contract_is_byte_stable` hashes the
golden file's *canonicalised* JSON — `json.dumps(..., sort_keys=True)`, so a checkout's line
endings are not what is being pinned — and asserts
`b69c020883a894c2e4174b5a2c6a7bc68a93eb3fdfb3175950631acf26b36352`. The existing equality test
catches a schema that moved; this catches the expectation itself being regenerated, which is the
one edit that makes the equality test pass while the published contract has in fact changed.

## Mutation table

Every test here pins existing behaviour, so "fails first" was established by breaking the
statement each covers. Harness at `%TEMP%\w107_mutate.py`, not committed. It runs
`uv run pytest -q --color=no -p no:randomly -n0` over the MCP test files, or the whole suite
under the repository's own `-n auto` where the claim is a whole-suite one. It compiles each
mutated file before pytest sees it, reads pytest's summary *counts* rather than line prefixes,
classifies any exit code other than 0 or 1 as UNREADABLE, and re-establishes the baseline at the
same pass count after every run.

Every row below was re-measured on the tree with `origin/main` merged in, after `-n0` was fixed —
an earlier run of the same specs produced the identical verdicts at the pre-merge pass counts.
Baselines: 135 passed for the `resources.py` spec, 147 for the `tools.py` spec (the difference is
the twelve tests added in between), and 2580 over the whole suite.

| Statement | Mutation | Outcome | Killed by |
|---|---|---|---|
| — (control) | a word changed in a docstring | **SURVIVED** at exactly the baseline count, both specs | — the harness is not blind |
| — (control) | `FEED_MIME_TYPE` → `"text/plain"` | **KILLED**, 1 failed | `…resource_template_is_published_exactly_as_declared` |
| — (control) | unbalanced paren in `FEED_URI_PREFIX` | **DID-NOT-COMPILE** | caught by `compile()` before pytest ran |
| `resources.py:123` | `return []` → advertise every registered vendor | **KILLED**, 3 failed | `…no_feed_cache_advertises_nothing`, `…advertises_nothing_and_serves_nothing`, `…same_nothing` |
| `resources.py:123` | probe: `raise AssertionError` | **KILLED**, 3 failed | the branch is taken |
| `resources.py:143` | `raise ResourceError(...)` → `pass` | **KILLED**, 9 failed | `…outside_the_feed_scheme…`, `…no_uri_is_refused…`, `…only_resembles_the_feed_prefix` (×5), `…not_an_unknown_vendor`, `…prefix_boundary_is_exact…` |
| `resources.py:143` | probe: `raise AssertionError` | **KILLED**, 9 failed | the branch is taken |
| `tools.py:294-295` | the whole `except` deleted, fault escapes | **KILLED**, 5 failed | `…row_that_does_not_validate…`, `…graph_cannot_find…`, `…not_reported_as_a_tool_error`, `…empty_spec_diff…`, `…three_silences_are_one_answer…` |
| `tools.py:294` | catch narrowed to `except KeyError` | **KILLED**, 4 failed | the four above that involve the unparseable row — the `KeyError` test is untouched, which is what isolates the two entry paths |
| `tools.py:294-295` | probe: `raise AssertionError` in the handler | **KILLED**, 5 failed | the block is entered |
| `tools.py:291` | probe: `raise AssertionError` in the guard | **KILLED**, 3 failed | `…names_no_vendor_change_is_still_a_row`, `…not_reported_as_a_tool_error`, `…three_silences…` |
| `tools.py:290-291` | guard deleted (ask the graph for a null id) | **SURVIVED**, 147 passed — and **SURVIVED** the whole suite at 2580 | masked by 294-295; see the compound below |
| `tools.py:290-295` | guard **and** catch both deleted | **KILLED**, 5 failed | including `…names_no_vendor_change_is_still_a_row`, which is what proves the survival above is masking rather than a blind test |
| `tools.py:344` | probe: `raise AssertionError`, **whole suite** | **SURVIVED**, 2580 passed | nothing — the condition never holds |

One survival, and it is the reported redundancy rather than a gap. The brief's order was followed
on it — suspect the mutation, then the test, then the code — and it came out at the code: the
compound mutation shows the deletion is observable once the clause that absorbs it is also gone.

### False-verdict modes, and which the harness reproduced

All five the brief names are answered, and one was reproduced on purpose:

- **Colourised summaries.** `--color=no`, and the verdict is read from pytest's summary *counts*
  (`N failed`, `N passed`) rather than from `FAILED ` line prefixes.
- **A flag collision reading as a clean run.** Any exit code other than 0 or 1 is UNREADABLE, not
  a survival. `-n0` is used for focused runs, which `pyproject.toml` itself names as the form that
  does not collide with the repository's `-n auto`.
- **A `SyntaxError` mutation arriving as `ERROR`.** `compile()` runs on the mutated source before
  pytest is invoked. **Reproduced deliberately** by the third control above, which reported
  DID-NOT-COMPILE and never reached pytest.
- **Decoding versus arriving bytes.** `PYTHONIOENCODING=utf-8` is set in the child environment,
  and `errors="replace"` is used only for the harness's own reading of that output.
- **`pytest -q; echo $?` reporting `echo`'s status.** The harness reads
  `subprocess.CompletedProcess.returncode` directly; no shell reports on pytest's behalf.

The blind-harness check is the first control row: a docstring word changed must survive at
exactly the baseline pass count, and a survival at any other count is reported as
BASELINE-DRIFTED rather than as a survival.

**One thing this harness got away with, worth recording.** Its focused runs used `-n0` while `-n0`
was broken repository-wide: the leaked-database sweep reported every pid equal to the current
process as dead, which under a serial run included the run's own database. That produced 186
errors for anyone running the whole suite with `-n0`, and it never touched these runs, because the
focused path names nine MCP test files and `tests/test_leaked_database_sweep.py` is not among them.
So the baselines were green for a reason that had nothing to do with the harness being right. The
table above was re-measured after the fix landed and the verdicts are unchanged, which is what
turns that from luck into a result.

## Nothing else was judged unreachable

The other five were reached with committed fixtures through `serve`, without calling a private
function to get at a branch. `_change_for` is private and both of its statements were reached
through `tools/call`, asserting on the JSON-RPC frame.

One fixture correction is worth recording, because it is where this task could have written down
a false result. The obvious way to reach `tools.py:295` is a fake whose `get_vendor_change`
raises — and any fake that stores prebuilt `VendorChange` objects can only ever raise `KeyError`,
which is the boundary case and not the one in question. Such a fixture would have covered the
statement and shown nothing: the `except KeyError` mutation would have survived, and the report
would have concluded the catch was correctly scoped. `RowBackedGraph` reads rows and calls
`VendorChange(**row)` because that is the only shape in which the `ValueError` path exists, and
`test_the_off_literal_row_is_one_the_model_refuses_and_the_schema_accepts` asserts the row is
still one the model rejects — so widening `Severity` fails loudly rather than quietly retiring
the coverage.
