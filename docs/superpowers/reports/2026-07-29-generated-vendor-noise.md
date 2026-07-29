# Is the enum kind noise for the generated vendors, or is that a fact about Stripe?

**Date:** 2026-07-29
**Answers:** `2026-07-29-oasdiff-determinism.md` §4, which observed that
`src/sync/signals/generated/adapter.py` applies no noise filter and reported the four generated
vendors' exposure as "the full 46× swing".

**It is a fact about Stripe, and both halves of §4's sentence about these vendors are wrong.** The
exposure is not a 46× swing — over 72 oasdiff runs their pairs were bit-for-bit reproducible. And
the kind Stripe drops is not noise here: it is the sole route to 28 of 31 affected operations in
one OpenAI window and to all three in another. **No filter is justified for any of the four
vendors, and none was added.**

## 1. What was measured, over what

Every configured vendor's own specification pairs, resolved the way a run resolves them: read the
generator manifest at two commits of the SDK repository, take the specification each names, diff
them with the pinned differ.

| vendor | generator | how the pair was obtained |
|---|---|---|
| `anthropic` | Stainless | `.stats.yml` at two commits of `anthropics/anthropic-sdk-python`, each naming an `openapi_spec_url` |
| `openai` | Stainless | `.stats.yml` at two commits of `openai/openai-python`, likewise |
| `vercel` | Speakeasy | `vercel-spec.json` at two commits of `vercel/sdk` — see §5, this is not what the adapter fetches |
| `cloudflare` | Stainless | none. `.stats.yml` publishes `configured_endpoints: 2521` and no URL |

Two windows per fetchable vendor: one about six weeks wide, to sit alongside Stripe's
`v2320 → v2330`, and one adjacent-release window, so the answer is not a fact about a single hop.
Every specification is pinned by the sha256 of its bytes and verified before the differ sees it.
**The stainless URL is not a pin** — it embeds a hash that is not the content hash, and two
differently-named Anthropic URLs serve byte-identical documents (`a97790bd…`). The manifest's own
`openapi_spec_hash` is not a pin either, and agreed across that same pair.

Reproduce with `uv run python scripts/measure_generated_vendor_noise.py --runs 12`. It fetches from
GitHub and from the generators' spec hosts, which is why it is a script and not a test.

**12 runs per pair, 72 runs total, oasdiff 1.26.0.**

## 2. How 12 was arrived at, and why it turned out not to matter

`2026-07-29-oasdiff-convergence.md` measured the shape of oasdiff's instability on Stripe: the
operation-level union converged on run 1 and did not move across 23 further runs, while the
natural-key union never converged. A rule id is a component of the operation-level key, so the union
of rule ids converges no later than the union of operation-level rows. That is the argument for
reading N off a curve rather than choosing it, and the script prints the curve for exactly that.

**The curve is flat from run 1 on every pair.** Identical record count, identical rule-id
distribution, zero new kinds and zero new operation-level keys across all 12 runs of all six pairs.
The per-run share of every rule id has a min equal to its max, to one decimal place, everywhere.

| pair | records per run | operations per run | new kinds after run 1 | new op keys after run 1 |
|---|---:|---:|---:|---:|
| anthropic 06-30 → 07-28 | 42 (12/12 runs) | 18 | 0 | 0 |
| anthropic 07-23 → 07-24 | 22 (12/12) | 10 | 0 | 0 |
| openai 06-17 → 07-28 | 295 (12/12) | 31 | 0 | 0 |
| openai 07-23 → 07-28 | 8 (12/12) | 3 | 0 | 0 |
| vercel 06-18 → 07-28 | 424 (12/12) | 51 | 0 | 0 |
| vercel 07-27 → 07-28 | 40 (12/12) | 7 | 0 | 0 |

So the determinism report's "their exposure is the full 46× swing" does not hold. That sentence was
an inference from Stripe's corpus to a set of vendors nobody had run the differ against. Stripe's
instability comes from oasdiff truncating a deep recursive walk — the report's own §2 quotes the
path `error/payment_intent/customer/anyOf[…]/subscriptions/data/items/…` — and none of these four
specifications provokes it.

**One caveat, and it is the same one the convergence report carries.** This is oasdiff 1.26.0;
CI pins 1.26.1. Stability measured on one version is not stability on the other, and 72 runs on
1.26.1 is a measurement nobody has taken.

## 3. The distribution, per vendor

Per run, since every run agreed. `level` is oasdiff's own grading, which `to_vendor_changes` now
reads rather than constants — M3-W79.

### anthropic, 2026-06-30 → 2026-07-28 — 42 records, 18 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `request-property-any-of-removed` | 20 | 47.6% | 3 | 7 ops |
| `response-property-enum-value-added` | 9 | **21.4%** | 2 | 2 ops |
| `response-body-one-of-added` | 2 | 4.8% | 3 | 2 ops |
| `request-body-became-required` | 2 | 4.8% | 3 | — |
| `request-property-became-required` | 2 | 4.8% | 3 | — |
| `request-property-list-of-types-narrowed` | 2 | 4.8% | 3 | — |
| `request-parameter-removed` | 2 | 4.8% | 2 | 1 op |
| `response-property-const-removed` | 1 | 2.4% | 3 | — |
| `request-property-all-of-added` | 1 | 2.4% | 3 | — |
| `request-property-all-of-removed` | 1 | 2.4% | 2 | — |

### anthropic, 2026-07-23 → 2026-07-24 — 22 records, 10 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `request-property-any-of-removed` | 22 | **100%** | 3 | 10 ops |

`response-property-enum-value-added` does not appear at all.

### openai, 2026-06-17 → 2026-07-28 — 295 records, 31 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `response-property-enum-value-added` | 268 | **90.8%** | 2 | **28 ops** |
| `response-property-list-of-types-widened` | 18 | 6.1% | 3 | — |
| `response-property-max-length-unset` | 9 | 3.1% | 3 | — |

### openai, 2026-07-23 → 2026-07-28 — 8 records, 3 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `response-property-enum-value-added` | 8 | **100%** | 2 | **3 ops — all of them** |

### vercel, 2026-06-18 → 2026-07-28 — 424 records, 51 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `response-property-enum-value-added` | 368 | **86.8%** | 2 | 11 ops |
| `response-property-one-of-added` | 21 | 5.0% | 3 | 3 ops |
| `response-body-one-of-added` | 12 | 2.8% | 3 | 11 ops |
| `response-property-became-optional` | 10 | 2.4% | 3 | 5 ops |
| `response-optional-property-removed` | 7 | 1.7% | 2 | 4 ops |
| `response-property-type-changed` | 3 | 0.7% | 3 | — |
| `request-body-one-of-removed` | 1 | 0.2% | 3 | 1 op |
| `response-body-wrapped-in-one-of` | 1 | 0.2% | 3 | 1 op |
| `request-parameter-list-of-types-narrowed` | 1 | 0.2% | 3 | — |

### vercel, 2026-07-27 → 2026-07-28 — 40 records, 7 operations

| rule id | records | share | level | sole route to |
|---|---:|---:|---:|---:|
| `response-optional-property-removed` | 20 | 50.0% | 2 | 3 ops |
| `response-required-property-removed` | 10 | 25.0% | 3 | — |
| `response-property-enum-value-added` | 9 | **22.5%** | 2 | 1 op |
| `response-property-one-of-added` | 1 | 2.5% | 3 | — |

### cloudflare — nothing to measure

`cloudflare/cloudflare-python`'s `.stats.yml` publishes an endpoint count and no URL, confirmed
against the live file on 2026-07-29. `SpecSource.is_fetchable` is False, `fetch_changes` returns
before the differ is invoked, and its record count is structurally zero rather than measured as
zero. A filter here would be a no-op on a vendor that produces nothing. The script re-checks this
each run and says so loudly if the vendor starts publishing a URL, because that is the day
cloudflare acquires an exposure nobody has measured.

## 4. The decision, and the argument from the numbers

**No filter, for any of the four.** Three things have to hold for a noise filter to earn its place,
and for these vendors none of them does.

**The share is not a property of the corpus.** It is 93% for Stripe and 92% for Twilio, and here it
ranges from 0% to 100% across six windows of three vendors — 21.4% and 0% for Anthropic, 90.8% and
100% for OpenAI, 86.8% and 22.5% for Vercel. Anthropic's dominant kind is
`request-property-any-of-removed`, a level-3 request-side change no filter proposed for Stripe would
have touched. A constant drawn from one vendor and applied to a code path serving four is a
measurement from a different corpus wearing the costume of a rule, which is what
`CLAUDE.md` means by keeping vendor-specific knowledge in the vendor's adapter.

**Dropping it costs coverage here, where for Stripe it cost none.** This is the decisive number and
it is an exact inversion of §4 of the determinism report. There, the volume and the coverage sat in
different kinds: dropping `response-property-enum-value-added` removed 93% of records and **0%** of
the varying operation-level rows — all 467 of those were `response-optional-property-removed`, the
kind the filter keeps. Here the same kind is the *sole route* to the operations:

| pair | operations | lost if the kind were dropped |
|---|---:|---:|
| anthropic 06-30 → 07-28 | 18 | 2 |
| anthropic 07-23 → 07-24 | 10 | 0 |
| openai 06-17 → 07-28 | 31 | **28** |
| openai 07-23 → 07-28 | 3 | **3 — the entire release** |
| vercel 06-18 → 07-28 | 51 | 11 |
| vercel 07-27 → 07-28 | 7 | 1 |

A filter that makes OpenAI report a real release as no change at all is not noise reduction. It is
the silent-vendor failure this adapter's own `_spec` docstring refuses to accept from a fetch
outage — *"an outage that reads as 'this vendor changed nothing' is the exact failure this adapter
exists to catch, arriving from our own side"* — arriving instead from our own filter, where nothing
downstream can tell it from a vendor that genuinely shipped nothing.

**There is no volume problem to solve.** The widest window measured produced 424 records. Stripe's
runs produced 33,914 to 737,850. Stripe's `NOISE_KINDS` comment argues that "carrying that volume
through the graph to produce findings nobody asked for is the wrong default", and at three orders of
magnitude less volume that argument does not reach. It is also weaker than it was for a second
reason: M3-W79 made `to_vendor_changes` read oasdiff's own level, so these records now arrive
stamped `warning` rather than the constant `breaking` §5 of the determinism report measured. The
weak-finding concern the filter existed to express is now expressed in the data, where triage can
act on it, instead of being enforced by deletion.

**Is there a differently-shaped filter?** No kind in any pair is both high-volume and sole route to
nothing, which is the only shape that would cost nothing. The closest candidates —
`response-property-list-of-types-widened` and `response-property-max-length-unset` for OpenAI — are
6.1% and 3.1% of one window and would remove 0 operations and 0 findings anyone would notice. A
filter that saves 27 records out of 295 is not worth the vendor-knowledge it puts in shared code.

## 5. Two defects found on the way, neither fixed here

**Vercel diffs the live specification against itself, so it can never report a change.**
`.speakeasy/workflow.yaml` names `https://openapi.vercel.sh/` — a live URL, identical in every
commit of the manifest — so `_spec_url` returns the same URL for both versions and the adapter
fetches the current document twice, moments apart, into two cache files. The Speakeasy parser sets
no `spec_hash`, so `changed_from` always answers "changed" and the vendor pays for both fetches on
every scan. Measured: two fetches of that URL three seconds apart were byte-identical
(`7223643e…`, 9,757,380 bytes) and the diff between them was **0 records**. The 424 records in §3
come from `vercel-spec.json` committed at two commits of `vercel/sdk`, which is the pair the
specification actually moved through and an upper bound on what the adapter finds today rather than
what it finds. **This is the next task**, and it is a coverage bug rather than a noise one: a vendor
that reports nothing looks exactly like a vendor that changed nothing.

**`2026-07-29-oasdiff-determinism.md` §4 needs a correction.** Its last paragraph says the four
generated vendors' "exposure is the full 46× swing". The observation that no filter is applied is
correct; the exposure claim is an inference from Stripe's records and §2 of this report measures it
as false. That report is not this task's to edit.

## 6. What is pinned in tests

`tests/test_generated_adapter_noise.py`. Nothing there asserts that a filter is absent by reading
the module — every case asserts on rows that came out of `fetch_changes`, so a filter added anywhere
between the differ and the rows fails regardless of how it is spelled.

| test | claim | mutation that killed it |
|---|---|---|
| `..._the_kind_stripe_drops_survives_this_path_end_to_end` | the pin, through the real differ | Stripe's `NOISE_KINDS` copied in; widened to drop everything |
| `..._no_record_the_differ_reported_is_missing_from_the_rows` | shape-independent — counts and kinds in equal counts and kinds out | all four filter mutations, including one keyed on `level` rather than rule id |
| `..._every_kind_the_fetchable_vendors_produce_reaches_a_row` | 20 cases, one per rule id observed | all four, naming the kinds each drops |
| `..._the_enum_kind_is_the_only_route_to_every_operation_openai_changed` | §4's decisive number, on committed records | one record's `id` changed in the fixture |
| `..._the_enum_kind_is_a_minority_of_what_anthropic_produces` | the share is not a corpus property | the dominant kind relabelled to the enum kind in the fixture |

Six mutations, six killed by the intended tests. The two evidence tests read
`tests/fixtures/generated_noise/`, which holds the real oasdiff output for the OpenAI adjacent
window (8 records) and the Anthropic six-week window (42 records) — small enough to commit, and
what makes the decision checkable without the network.

`test_no_record_the_differ_reported_is_missing_from_the_rows` is the one worth keeping if the
others were ever trimmed: the level-keyed mutation left every kind-by-kind case green and was caught
only there.

## 7. Commands, so a reader can re-run this

```bash
uv run python scripts/measure_generated_vendor_noise.py --runs 12 --out noise.json
uv run python scripts/measure_generated_vendor_noise.py --runs 12 --vendor openai

uv run pytest tests/test_generated_adapter_noise.py -q
```

The script verifies every specification's sha256 before the differ sees it and refuses rather than
warning, for the reason `scripts/fetch_measurement_inputs.py` gives: a substituted input parses,
measures, and produces a number that differs from the documented one by an amount nobody can see.
