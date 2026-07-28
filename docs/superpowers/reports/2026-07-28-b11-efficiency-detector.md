# B11 — the efficiency detector

Built three of the four findings the design document names, refused the fourth, and emit no
dollar figure. What follows is the reasoning for each, and one correction to a report the
coordinator relayed about the salt.

## What was built and what was refused

**Vendor calls inside a loop — built.** `call_count >= 10` within one trace. The strongest
signal the table supports, and the one its grain exists for.

**Repeated identical calls with no caching — built, with a correction.** Equal `target`
digests within one trace mean the same URL was requested more than once.

The correction is that repeats are counted over *successful* spans only, which is where this
parts company with `ObservedCall.repeated_calls`. That property counts every duplicate digest,
including a request the caller re-issued after a 500. That is correct for the property and
wrong for this finding: proposing a cache for a call that failed is advice to cache an error.
The property is not changed — `sync.core` is shared — the detector computes its own.

**Retry storms — built.** `max_resend_count >= 3`. The maximum rather than the sum, because
each span already counts its own resends and adding them across spans answers no question.

**Default page sizes against large result sets — refused.** The table cannot see it.

A default page size is visible only in a request's query string. The only column that ever held
one is the salted `target` digest, which is one-way by construction, and `url_template` carries
the vendor's published path template with no query string at all. The information was destroyed
at the observation boundary, deliberately, by the privacy rule in `.claude/rules/graph-grain.md`.

The available proxy is many distinct targets in one trace looking like a pagination walk. It is
refused because it is indistinguishable from a loop over a list of ids — which is the first
finding, and has a different fix. A detector firing on that would be guessing while sounding
certain. Making it real needs a stored page-size *parameter value*, which is a schema change
and a privacy argument, not a detector change. `test_no_page_size_finding_is_emitted_from_anything`
pins the refusal so a proxy cannot be introduced quietly later.

## Thresholds

| Threshold | Default | Basis |
|---|---|---|
| loop | 10 calls to one operation in one trace | Clear of any written-out sequence |
| repeat | 2 repeats of one target in one trace | 1 is explained by read-after-write |
| resend | 3 on a single call | `resend_count` is 0 on a first attempt |

All three are constructor arguments. All three are **policy floors, not calibrations**, and
nothing in this repository can currently make them anything better.

`vendor_change` refuses to pick a depth cut-off because there is no labelled data to calibrate
one against, and that objection applies here in full. `observed_drift` could answer it with a
distribution-free argument — the rule of three over sample size — because its question is about
whether a sample is large enough to speak. "Is this a loop" is not that kind of question, so
that escape is not available.

What is done instead: every rationale quotes the observed count, so a finding can be judged
without trusting the threshold that surfaced it. What would replace the defaults is a corpus of
real traces with labelled outcomes — which findings a customer actually acted on — and that does
not exist. The committed OTLP fixture is 9 spans, which cannot calibrate anything; the tests
therefore construct `observed_call` rows directly rather than pretending the fixture justifies
a number.

The loop default of 10 is the one most open to challenge. It is chosen so the first findings
shipped are ones nobody argues with, and the cost is real: a loop of five is invisible.
Precision over recall is this repository's committed direction, so that is the intended trade
rather than an oversight.

## The dollar figure: there is not one

A saving is a call count multiplied by a price per call. **No table in this repository holds a
price.** Not `observed_call`, not `call_site`, not `vendor_change` — confirmed by grep across
`src/` for price, pricing, cost_per, usd, cents_per and per_call. Vendor pricing varies by plan
and by negotiated contract and none of it is stored.

So the rationale states the **call volume**, which the table can source, and states no money.
`test_the_rationale_states_the_call_volume_and_never_a_dollar_figure` asserts no `$` and no
`usd` appears in any rationale, and that the observed count does.

Two in-repo precedents for the same discipline, and they are not equally on point:

- `sync.benchmark.axes` excludes `cache_read_input_tokens` from a cost total rather than
  "inventing a price ratio this module has no business asserting". This is the same refusal
  about the same kind of number.
- `2026-07-25-sync-positioning-and-open-core.md` says **"Ship the efficiency claim after the
  corpus can source it, not before."** Cited as precedent for the discipline rather than as the
  same claim — that passage is about *Sync's own* cost to operate, sourced from the migration
  corpus, which is a different number from the customer's vendor bill. The reasoning transfers;
  the number does not.

## Is the salt stable enough to rely on?

The relayed report that "the salt has no provenance" is **not accurate**, and the precise
version matters because it changes the fix.

A stable salt implementation exists: `sync.remediate.corpus.corpus_salt()`. `SYNC_CORPUS_SALT`
wins if set; otherwise a value is generated once with `secrets` and persisted to a gitignored
`.sync-corpus-salt` at the repository root, with a process-lifetime fallback if that file cannot
be written. It is stable across runs and unique per deployment, by design and with the reasoning
written down.

**It is not wired to the telemetry path.** `ingest_payload(..., salt=...)` takes `salt` as a
plain argument, and its only callers are tests, which pass a literal. `corpus_salt()`'s only
caller is `sync/remediate/corpus.py:235`, the `migration_outcome` path. So the digest in
`observed_call.spans[].target` is produced from whatever a caller happens to hand in, and no
production caller exists yet to hand in anything.

`ingest.py`'s own module docstring already states the consequence: a rotated salt "makes repeat
calls look distinct and silently deletes the cache finding. Nothing in the schema can detect that
having happened."

The precise exposure for this detector, which is narrower than "the cache finding is unreliable":

- `record_observed_call` merges span maps across batches — `spans = observed_call.spans || EXCLUDED.spans`.
  One row therefore accumulates spans ingested at different times, possibly in different processes.
- Whenever one salt covered every batch that fed a row — the normal case, and every case today —
  the digests in that row are mutually comparable and repeats are counted correctly.
- If the salt differs *between* two batches landing in one row, one URL yields two digests inside
  one span map. `distinct_targets` over-counts and the cache finding **silently under-fires**. It
  fails safe rather than raising a false finding, which is the right direction, but it fails
  invisibly.
- The loop and retry-storm findings do not read the digest at all and are unaffected.

It is worth being exact about why that middle case is reachable, because the intuitive argument
against it — one trace is one batch, so one salt — is not what this repository does. Two
committed tests demonstrate a single trace's spans arriving across separate ingest calls and
merging into one row: `test_a_partial_redelivery_of_overlapping_spans_converges`, whose docstring
describes a collector re-sending a buffered subset repacked with newer spans, and
`test_the_first_sighting_is_held_and_the_last_advances`, which feeds one trace two batches in
order. `record_observed_call`'s own docstring names the same behaviour — backlog flushed after
the live stream resumes, so batches do not arrive in order. Each of those calls takes its own
`salt` argument. Same process means same salt and no exposure; a process boundary between two
batches feeding one row is where a divergence could enter, and the per-process fallback below is
the way it plausibly would.

So the cache finding was built, with the dependency stated rather than worked around. The fix is
to have whatever eventually calls `ingest_payload` source its salt from `corpus_salt()`. That is
one line and it is not made here: telemetry belongs to another worker, and the change belongs
with the endpoint work that will introduce the first real caller.

Two further properties of the salt, recorded because they are real and are deliberately not
defended against in code:

- **A rotated salt silently changes every stored digest, and no column records which salt
  produced a row.** That is a real gap for any future analysis comparing digests across time —
  a corpus join, a longitudinal cache-hit measurement. It is not this finding's gap, which
  compares digests inside one row, and it is not fixed here.
- **`SALT_FILE` resolves to the repository root, so every worktree has its own.** Digests are
  therefore not reproducible across checkouts. This detector's tests are unaffected because they
  never touch the ambient salt: `_spans()` writes literal strings such as `"same"` and
  `"charge0"` directly into the `target` field, so equality is asserted over values the test
  controls and `hash_request_target` is never called. Anyone later writing a test that wants a
  reproducible digest must pass an explicit salt rather than rely on the ambient one.

## Mutations

Nine, each applied to a clean tree and restored, against a baseline asserted to be green with
the identical command first.

| Mutation | Caught by |
|---|---|
| loop counts spans across traces instead of within one | `..._same_volume_spread_across_traces_is_not_a_loop` (+11 more) |
| loop fires only strictly above the threshold | `..._many_calls_to_one_operation_in_one_trace_is_a_loop` |
| repeats counted over every span including failures | `..._a_repeated_call_that_failed_is_not_reported_as_a_missing_cache` |
| repeat fires only strictly above the threshold | `..._identical_targets_within_one_trace_are_an_uncached_repeat` |
| resend read as the total rather than the worst single call | `..._resend_is_read_as_the_worst_single_call_not_the_total` |
| a dollar figure introduced into the rationale | `..._rationale_states_the_call_volume_and_never_a_dollar_figure` |
| findings raised as breaking rather than informational | `..._findings_are_informational_rather_than_breaking` |
| a page-size proxy fired from distinct targets | `..._no_page_size_finding_is_emitted_from_anything` |
| uncorrelated observations no longer skipped | **SURVIVED — see below** |

The survivor is a real result rather than a failure to write a test. `if not call.operation_id:
continue` is **not a correctness guard**: both indexers drop a call site whose symbol did not
resolve (`python_lang.py:402`, `typescript.py:328`), so no `call_site` row carries an empty
`operation_id`, so `call_sites_for_operation(vendor, "")` returns nothing and the no-call-site
rule already produces the same outcome.

Rather than contrive a test that cannot distinguish the two mechanisms, the line is documented
as what it is — an early-out avoiding a query per uncorrelated observation, and `IngestReport`
calls `uncorrelated` the count worth watching, so that query is not rare — and the test docstring
now says the no-call-site rule is what enforces the outcome. Keeping the assertion is still
right: it pins the behaviour callers depend on, against whichever mechanism delivers it.

## Things the brief did not mention

**An efficiency finding cannot be raised against uncorrelated traffic at all.**
`Finding.call_site_id` is a required `str`, so a finding must name a call site. An observed call
that correlated to no operation has none, and one whose operation no indexed code calls has none
either. Both are skipped, following `observed_drift`'s precedent. The consequence worth stating:
this detector can only see cost in code the indexer already resolved, so its coverage is bounded
by symbol-map coverage rather than by telemetry coverage.

**`Severity` has no cost axis.** The vocabulary is `breaking | deprecation | addition | info`.
`info` is the honest fit and is what is emitted; reporting a saving as `breaking` would let it
compete in triage with a call site that no longer compiles. This is a gap in a `sync.core` type
and was not changed.

**One finding is emitted per (observed call × call site), which may be wrong for this
detector.** If an operation has three call sites, one looping trace yields three findings. That
matches `vendor_change` and `observed_drift`, where each site is independently affected. For
efficiency it is arguably wrong: the cost is incurred once per trace, not once per site, so
three findings triple-count a single saving. Not resolved unilaterally — fixing it means either
picking one site arbitrarily or letting a finding address several, and the second is a change to
a shared type.

**The detector had to be wired into `cli.py`, and a lint is what caught that.** The first full
suite run failed on `test_lint_dead_links.py`: `EfficiencyDetector` was "reached from nowhere in
the scanned tree; a component only a test calls is not wired in". That is correct and it was my
omission — I had built a detector no scan could run, which `_detector_suite`'s own docstring
already names as the failure mode that made two earlier detectors worthless.

So `cli.py` now constructs it, last in the suite, because a scan's first output should be what
is about to break rather than what costs money. `_detector_suite` gained a `repo_id` argument,
since this is the only detector scoped to a repository rather than to a vendor, and the two CLI
tests that call it were updated.

Wiring it also **resolved a baselined dead link**: `GraphStore.observed_calls` was listed in
`scripts/dead_links_baseline.txt` under the comment "the efficiency detector's reader, ahead of
the detector that will consume it". That entry was written in anticipation of this task, and the
baseline's own rule is that whoever wires a symbol up deletes its entry in the same commit. Done.
The file shrinks by one.

**Scope.** Nothing was edited under `src/sync/index/`, and neither `schema.sql` nor
`protocols.py` was touched. No detection reads `call_site`'s loop column; the observed loop
signal and a static one are different evidence and joining them is a later task.
