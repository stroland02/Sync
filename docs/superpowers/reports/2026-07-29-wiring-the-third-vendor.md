# Wiring the third vendor, and the tuple that meant three things

M3-W88 built Cloudflare as a third deprecation source, proved the parser reads its page, and
reported that nothing ran it: `DEPRECATION_SOURCES` was a tuple in `src/sync/cli.py`, so a source
added to the adapter module was importable, tested and unreachable. That is the same defect
`sync.signals.registry` was written to fix for vendor adapters, where `cli.py` named
`StripeAdapter` by hand and no run could reach the second one.

The tuple had a second problem. Four call sites read it, doing three different jobs, and its
comment asserted a property of the pages that was false. This task splits the question the four
sites ask and moves the registry out of the entry point.

## What `parse_parameter_deprecations` does with a page carrying no parameter table

**It returns the empty list. No raise, no partial row, nothing written.**

Established by running it over all three committed captures before anything was designed:

```
anthropic.md:               3 parameter rows
openai.md:                  0 parameter rows
cloudflare-workers-ai.md:   0 parameter rows
```

Then by asking *why*, because "returns nothing" and "cannot read this page" are the distinction
the whole signal is built on:

- **Cloudflare** has no pipe table anywhere on the page, so `_cells` rejects every line.
- **OpenAI** has pipe tables, and eight of them carry a `Deprecated model` header cell that
  `_STATUS` does match on. What stops them is the next filter: `_parameters_in` requires
  `^[A-Za-z_][A-Za-z0-9_]*$`, and `Shutdown date` has a space. So the rows are dropped one step
  later than expected rather than not matching at all.

The stronger finding is that this is a fact about what the vendors publish, not about the parser:
**the word "parameter" does not occur anywhere on the OpenAI page**, and does not occur anywhere on
Cloudflare's. Anthropic's page carries an `## API parameter deprecations` section with a real
table. Only one of the three publishes parameter deprecations at all.

That measurement contradicts the comment this task replaced, which claimed *both* existing vendors
publish a parameter table. It was false for OpenAI before Cloudflare existed, and nobody had
checked.

### So the two failure modes are not symmetric, and the design follows that

The brief posed them as opposites. They are not equally bad, because the two parsers fail
differently:

| Wrong wiring | What happens | Severity |
|---|---|---|
| A model-publishing source left out of the model scan | Its retirements are never seen. The vendor looks healthy. Eighteen Workers AI models, silently. | **Severe, and silent** |
| A source with no parameter table included in the parameter scan | `parse_parameter_deprecations` returns `[]`. Nothing incorrect is produced and no extra page is downloaded, because both halves share one cache file. | **Benign** |
| A source with no model table included in the model scan | `DeprecationAdapter.fetch_changes` raises on zero rows, and the scan prints `model-deprecation: <vendor> unavailable` on every run. | **Loud, and self-reporting** |

The residual cost on the parameter side is not a bad row. It is the failure path: a fetch error
prints `parameter-deprecation: <vendor> page unavailable`, which claims a detector lost findings
for a vendor that publishes none. `_scan` prints a per-detector count including zero precisely so
that a zero means something, and a zero taken across three vendors of which two cannot contribute
means less, not more.

So the declaration earns its keep mainly on the model side and on not misreporting the parameter
side. It is not preventing corrupt data, and this report says so rather than overstating it.

## The design, and the two that were rejected

**Chosen: two required fields on `DeprecationSource`, and the registry moved beside the constants
it names.**

```python
publishes_model_deprecations: bool
publishes_parameter_deprecations: bool
```

`DEPRECATION_SOURCES` now lives in `sync/signals/deprecations/adapter.py` with the three source
constants, exported through the package, and is read by `cli.py` rather than defined there. Two
accessors derive the subsets:

```python
def model_deprecation_sources() -> tuple[DeprecationSource, ...]
def parameter_deprecation_sources() -> tuple[DeprecationSource, ...]
```

Three properties decided it.

**One list, so the classic drift cannot happen.** A vendor is registered in exactly one place. The
failure the brief warned about — added to one list, forgotten in the other — has no site to occur
at.

**Both fields are required, with no default.** A default is how a fourth source silently inherits
whichever answer was right for the vendor that happened to be added first, which is this defect
with a new coat.

**Booleans rather than a set of signal names.** `CLAUDE.md` says not to add validation for
conditions that cannot occur; the better move is to make the condition unable to occur.
`signals=frozenset({"parameters"})` — plural typo — would silently drop a source out of the
parameter scan and need a validator to catch. A misspelled dataclass keyword is a `TypeError` at
import, with no validation code written.

**Rejected: two lists.** It duplicates every vendor that carries both signals, so a fourth vendor
gets added to one and forgotten in the other. That is the failure this task exists to fix, moved
rather than removed. It is also worse than the brief suggests: the literal indexer needs the
*union*, so two lists means a third expression at the third call site, and nothing keeps that one
in step either.

**Rejected: ask the parser.** Derive it — a page carries parameter deprecations if parsing finds
some. It needs no configuration and cannot go stale, and it is wrong for the reason the rest of
this system keeps insisting on: it cannot distinguish "this vendor publishes none" from "the parser
could not read this page". `DeprecationAdapter` already refuses to make exactly that inference,
raising on a page that parses to zero rows rather than reporting an empty change list. Deriving the
declaration would also invert the order of operations — the page has to be fetched to decide
whether to fetch it.

The declared answer is held to the evidence instead, which is the pattern `prefixes` already
uses in this package: authored beside the URL, and checked by a test against the committed capture.
`test_only_the_anthropic_page_publishes_a_parameter_table` is that check.

### The declaration for OpenAI is a behaviour change, and it is worth naming

`OPENAI.publishes_parameter_deprecations` is `False`, so its page is no longer read for
parameters. Today that changes no output — the parse returned `[]` — and it costs no extra
download, because the model half fetches the page either way.

The risk is honest and stated: if OpenAI adds a parameter table, the declaration is stale and the
signal is missed. That is the same staleness `prefixes` already carries — a new model family with a
new prefix goes unindexed — with the same mitigation, a committed capture and a test over it. What
tipped the decision is that a declaration meaning "may one day carry" is uncheckable, and one
meaning "does carry, as measured" is.

## What each of the four call sites now asks for

| Line | Site | Reads | Today |
|---|---|---|---|
| 525 | `_parameter_deprecations` | `parameter_deprecation_sources()` — which pages carry a request-parameter table | Anthropic |
| 627 | `_model_deprecations` | `model_deprecation_sources()` — which pages carry model retirements | all three |
| 674 | `_literal_call_sites` | `DEPRECATION_SOURCES` — **every** source, unfiltered | all three |
| 870 | the run report | `model_deprecation_sources()` — the same set line 627 read | all three |

Line 674 is the one the brief flagged as easily overlooked, and it is the one that changed least.
It supplies `prefixes` to the literal indexer, which indexes model ids in the *customer's* code and
has nothing to do with which table a vendor publishes. A finding of either kind needs a call site
to attach to, so narrowing it to one signal's sources would leave the other signal's findings
pointing at nothing. It stays unfiltered, and the docstring now says that is deliberate.

Lines 627 and 867 must name the same set — `VendorChangeDetector` is scoped to one vendor, so a
retirement upserted for a vendor with no detector is a row nothing will ever read. They read one
shared accessor rather than two comprehensions, so they cannot drift.

## Is a fourth vendor added to one place and missed in another detectable?

**The two-list drift cannot occur**: there is one list, and one field per signal on each entry.

**The residual gap is real and is caught.** A `DeprecationSource` can still be defined in
`adapter.py` and never added to `DEPRECATION_SOURCES` — which is exactly what happened to
`CLOUDFLARE`. `test_every_source_the_deprecations_package_defines_is_registered_for_a_scan` walks
the adapter module's namespace for `DeprecationSource` instances and asserts the set matches the
registry, and asserts the set is non-empty first so it cannot pass over nothing.

Two further couplings are asserted rather than conventional:

- `test_the_run_builds_a_detector_for_every_vendor_it_fetched_retirements_for` compares the run
  report's vendor list against the vendors `_model_deprecations` actually produced changes for,
  rather than against a literal list. A fourth source needs no edit to this test.
- `test_no_source_is_registered_twice` — every row is keyed by vendor id, so a repeated source
  would parse one page twice and upsert under one key.

The one gap left: a source defined in some *other* module would not be seen by the namespace walk.
The three constants live in `adapter.py` by convention and the test asserts against that module.

## The exact wording replaced at `cli.py:93`

Removed, in full:

```python
# Vendors whose parameter deprecations a scan reads. Both publish one page carrying both a model
# lifecycle table and a parameter table; `parse_parameter_deprecations` tells them apart.
DEPRECATION_SOURCES: tuple[DeprecationSource, ...] = (ANTHROPIC, OPENAI)
```

Three claims in two lines, and two of them were false. "Both publish one page carrying both a
model lifecycle table and a parameter table" is false for OpenAI, whose page never mentions
parameters. "`parse_parameter_deprecations` tells them apart" credits the wrong rule: what keeps
Anthropic's lifecycle rows out of the parameter results is not the status cell — `_STATUS` matches
a bare `Deprecated` — but `_IDENTIFIER` rejecting a hyphenated model id one filter later.

Nothing replaced it in `cli.py`. The definition moved to `adapter.py`, and `cli.py` imports it.

## Mutation results

Ten mutations plus a sentinel, each applied to the shipped source and reverted. Every one kills at
least one test, and the restored baseline is re-asserted green afterwards so that "nothing failed"
is distinguishable from "cannot see failures".

| # | Mutation | Result |
|---|---|---|
| — | **Sentinel**: no source is registered at all | killed 20 — a kill is detectable |
| M1 | Drop the third vendor: restore the shipped defect | killed 5 |
| M2 | Parameter scan ignores the declaration and reads every source | killed 1 |
| M3 | Model scan ignores the declaration and reads every source | killed 2 |
| M4 | OpenAI declares a parameter table it does not publish | killed 1 |
| M5 | Cloudflare declares a parameter table it does not publish | killed 1 |
| M6 | Cloudflare declares no model retirements | killed 3 |
| M7 | Literal indexer narrowed to one signal's sources | killed 1 |
| M8 | Run report names the parameter sources instead of the model sources | killed 2 |
| M9 | Run report drops the filter entirely | killed 1 |

M1 is the shipped defect restored, and it kills five tests including the registration invariant and
the literal-prefix check — the two halves W88 could reach and could not.

### A third way to get a false survival

`CLAUDE.md` and W88 record two harness faults that both report *every mutation survives*: a plugin
flag colliding with `-n auto` so pytest exits 4 with no `FAILED` lines, and parsing
`startswith("FAILED ")` against colourised output. This run found a third.

**M4's first form did not compile.** Written as an insertion, it produced a duplicate
`publishes_parameter_deprecations` keyword — `SyntaxError: keyword argument repeated`. pytest
reports that as `ERROR tests/...` rather than `FAILED tests/...`, **and still exits 1**. So it
lands inside the accepted `{0, 1}` exit codes, matches no `FAILED ` prefix, and reads as a clean
survival. Verified by hand before it was believed.

The general rule worth keeping: a harness must separate **killed** from **did not compile** from
**cannot see the result**, because two of those three look like a survival and only one is. The
harness now counts `ERROR ` lines and reports them as its own fault, never as a survival.

### M9 survived first, and the test was at fault

M9 removes the filter from the run report. It survived the first run, and following
`CLAUDE.md`'s order — suspect the mutation, then the test, then the code — the mutation was
legitimate and the fault was in the test.

`cli.py` imports `DEPRECATION_SOURCES` by name, so it holds **its own binding**. The test
registered a synthetic parameters-only source by patching `adapter.DEPRECATION_SOURCES`, which the
accessors read at call time — but the mutated line 870 read `cli.DEPRECATION_SOURCES`, still
pointing at the shipped three. An unfiltered report over that stale binding returns exactly the
set the test asserted, so the mutation changed nothing the assertion could see. Patching both
bindings kills it.

For the record, the production code was never the suspect that paid out. It has now been outside
the fault on this project every time.

### What the shipped set cannot exercise

`publishes_model_deprecations` is `True` for all three vendors, so its `False` branch has no
shipped example — the same "all N pages agree" coincidence that made two of the parser's rules
facts about two pages rather than about deprecation pages.
`test_a_source_publishing_only_parameters_reaches_only_the_parameter_scan` registers a synthetic
source to exercise it, which is what M3 and M6 kill. Without it the field would be decoration.

## Gates

Run on the final tree, merged up to `origin/main`, unpiped, exit codes checked.

| Gate | Result | Exit |
|---|---|---|
| `uv run pytest -q` | 2237 passed, 2 skipped | 0 |
| `uv run python scripts/lint_encoding.py src scripts tests` | clean | 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 1 contract kept, 0 broken | 0 |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | clean | 0 |

## What the next task should take

1. **`sync.index` is not told which signal a prefix serves, and that is now a choice rather than
   an oversight.** `_literal_call_sites` hands every source's prefixes to the literal indexer
   because a finding of either kind needs a call site. If a future source publishes parameter
   deprecations for models it does not name — a vendor documenting `temperature` without a
   retirement list — its prefixes would be indexed for a signal that has no use for them. Harmless
   today, and `src/sync/index/` was outside this task's files, so it is reported rather than
   changed.
2. **A parameter table whose model ids are valid identifiers would be misread.** What keeps
   Anthropic's lifecycle rows out of the parameter parser is `_IDENTIFIER` rejecting a hyphen, not
   any rule about what a lifecycle row is. A vendor naming models `gpt5` or `opus` would emit one
   parameter deprecation per model. No committed page does this; the safety is incidental, exactly
   as W88 found for "Variants that remain active".
3. **`adapter.py`'s module docstring still says "Both vendors serve clean markdown when the
   documented `.md` suffix is appended"**. There are three sources, and Cloudflare needs the
   directory-plus-`index.md` form because the bare `.md` suffix 404s there. W88 recorded the fact
   and the docstring was not updated; it was left alone here rather than edited around the
   registry addition.
