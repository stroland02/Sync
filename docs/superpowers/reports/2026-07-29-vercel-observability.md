# A vendor whose manifest names a live endpoint cannot be diffed, and must say so

**Date:** 2026-07-29
**Task:** M3-W85
**Answers:** `2026-07-29-generated-vendor-noise.md` §5, which found the defect while measuring
something else and named it the next task.

**The defect is a property of the manifest, not of the generator and not of the vendor.** One of
four configured vendors resolves to the same URL at both ends of every version pair, and the
condition that detects it names no vendor and no generator. A pair that cannot be compared is now
reported as unobservable and **downloads nothing**, where before it fetched a 9.7 MB document twice
per scan to diff it against itself and report zero records.

## 1. Which vendors resolve to the same URL at two commits

Established by fetching each configured vendor's manifest at two commits through the authenticated
`gh` CLI and running the repository's own `parse_manifest` over what came back. The commit pairs are
the ones `scripts/measure_generated_vendor_noise.py` pinned for M3-W81, so this lines up with that
report's measurement rather than being a fresh unrelated window.

| vendor | generator | manifest at base | manifest at head | resolves to |
|---|---|---|---|---|
| `anthropic` | Stainless | `4152f950f8ee` | `4192ec5956e8` | two distinct URLs |
| `openai` | Stainless | `cda4aeff166d` | `e7badae36205` | two distinct URLs |
| `cloudflare` | Stainless | `0c574f6137a6` | `99c24bb73e11` | no URL at either commit |
| `vercel` | Speakeasy | `9e62dc177a3c` | `9e62dc177a3c` | **one URL, both ends** |

Manifest digests are the sha256 of the fetched bytes, truncated. Anthropic's and OpenAI's
`openapi_spec_url` embeds a per-revision hash and rotates on every commit; Vercel's
`.speakeasy/workflow.yaml` names `https://openapi.vercel.sh/` and **the whole file is byte-identical
at both commits** — the same `9e62dc177a3c` at the six-week base, the adjacent-window base, and the
head. Cloudflare publishes `configured_endpoints` (1292 → 2521) and no URL, which
`SpecSource.is_fetchable` already reported.

Widened to the 12 commits that touched `vercel/sdk`'s `.speakeasy/` between 2026-06-19 and
2026-07-28: `workflow.yaml` carries git blob SHA `06bdcfc3ebfa` at **every one of them**. The file
has not changed in six weeks while the specification it names moved on every commit.

**The live endpoint, fetched by hand on 2026-07-29.** Two `GET https://openapi.vercel.sh/` three
seconds apart:

```
fetch1 http=200 bytes=9757380
fetch2 http=200 bytes=9757380
7223643ef04ae18e984162ccb49974cd0f323d3f8e8ce68a4da8c13e51bbec4e  v1.json
7223643ef04ae18e984162ccb49974cd0f323d3f8e8ce68a4da8c13e51bbec4e  v2.json
BYTE-IDENTICAL
```

That reproduces §5 of the noise report exactly — same byte count, same `7223643e…`. No test performs
this fetch; it was run from the shell and the bytes are recorded here.

## 2. Generator or manifest? The manifest, and it is checkable

Speakeasy's `location` field is not inherently unversioned. Read on 2026-07-29 across five
Speakeasy-generated SDK repositories:

| repository | `sources.*.inputs[].location` | versioned? |
|---|---|---|
| `vercel/sdk` | `https://openapi.vercel.sh/` | no — live endpoint |
| `dubinc/dub-node` | `https://api.dub.co` | no — live endpoint |
| `polarsource/polar-js` | `https://api.polar.sh/openapi.json` | no — live endpoint |
| `gleanwork/api-client-typescript` | `registry.speakeasyapi.dev/glean-el2/sdk/glean-api-specs` | no — untagged reference |
| `mistralai/client-ts` | `registry.speakeasyapi.dev/mistral-dev/…/mistral-openapi-azure:v2` | **yes — tagged revision** |

So the generator is not the thing to condition on: Speakeasy manifests carry versioned references,
and three of the five above happen not to. The symmetric case holds too — a Stainless manifest whose
`openapi_spec_url` stopped rotating would sit in exactly Vercel's position, which is why
`test_a_stainless_manifest_naming_one_url_is_equally_unobservable` exists and why the condition is
written against the resolved locations rather than against `generator`.

**Fixing "Speakeasy" would have been wrong in both directions.** It would refuse Mistral, whose
manifest names a real revision, and it would miss a Stainless vendor that stopped rotating.

One gap this surfaced and did not close: a tagged registry reference is not an absolute URL, so
`_is_absolute_url` rejects it and `_parse_speakeasy` returns `None` for Mistral and Glean entirely.
Those vendors are unservable rather than merely unobservable. Neither is configured here, so nothing
regressed; it is named in §8.

## 3. What the lock file turned out to be, and why it does not change the answer

`vercel/sdk` commits `.speakeasy/workflow.lock` beside the manifest, and it looked like it might
supply the versioned document the manifest lacks. It does not, and the distinction is worth
recording because the file genuinely does carry a per-version pin.

The lock publishes `sourceRevisionDigest` and `sourceBlobDigest`, and both **move on every commit**
while `workflow.yaml` holds still:

| commit | date | `workflow.yaml` | `sourceBlobDigest` | `vercel-spec.json` |
|---|---|---|---|---|
| `142fa1bd976e` | 07-28 | `06bdcfc3ebfa` | `824dee93d491` | `6792c33b7d00` (9,719,062 B) |
| `e8b9e0fa1831` | 07-27 | `06bdcfc3ebfa` | `587656d1b058` | `7a266d77a8e9` (9,727,026 B) |
| `9e192047596a` | 07-25 | `06bdcfc3ebfa` | `ae9ce42387f1` | `fb5789e02c8c` (9,725,946 B) |
| `fd90a245764e` | 07-03 | `06bdcfc3ebfa` | `5d28aecda362` | `3077898d4857` (8,914,138 B) |
| `ae5e29a3544d` | 06-19 | `06bdcfc3ebfa` | `11c6f7bdeb5a` | `887417fc1735` (7,780,528 B) |

Across all 11 adjacent pairs of the 12 commits sampled, the blob digest moved exactly when the
document moved. Document identity is git's own blob SHA for `vercel-spec.json`, which the contents
API returns without transferring the 9 MB body.

**Two honest limits on that.** The sample contains no pair where the document did *not* move — the
lock is only rewritten when Speakeasy regenerates — so the "holds still when nothing moved"
direction is untested rather than confirmed. And the digest is of the *resolved* document: 9,719,062
bytes at head against the live endpoint's 9,757,380, because `overlays: [overlay-title.yaml]` is
applied before it is stored. It pins the generation input, not the vendor's published artifact.

**Why it still does not rescue this task.** The lock names a versioned *identifier*, not a
retrievable versioned *document*. Its `registry.speakeasyapi.dev/…` reference is not anonymously
fetchable — every path under that host, digest-qualified or not, returns the same 4,848-byte
single-page-app HTML shell (`text/html`, HTTP 200), confirmed against both the bare location and a
`…/manifests/sha256:de4e5bde…` form. A hash that says "it moved" without a second document to diff
makes the coverage defect *more* expensive, not less: `changed_from` would answer "changed" and the
adapter would still fetch the live URL twice for zero records.

The lock file is a real follow-up for the **cost** half, and §8 specifies it.

## 4. The three options, and the two rejected

### Rejected: recover a versioned document another way

The candidate was `vercel-spec.json`, committed at the repository root — the pair M3-W81 used to get
its 424 records. It is not the document the manifest points at: it is the live endpoint with an
overlay applied, and the byte counts in §3 confirm they are different artifacts. That alone is
survivable, since both ends would get the same treatment.

What kills it is structural. `GeneratedSpecAdapter` receives `sources: Mapping[str, SpecSource]` and
a `fetch: Callable[[str], str]`. It does not know the repository, it does not know that a version
string is a git ref, and it has no business knowing either — `_RAW_CONTENT` and the repo live in
`sync.signals.registry`, one layer up. Implementing this inside the adapter means the shared path
composing `raw.githubusercontent.com` URLs and assuming a version is a commit SHA, which is host
knowledge and layout knowledge in the module that must hold neither.

It is also unverified past one vendor. `output:` names a generator output path, and whether it is
committed is a per-repository accident: `vercel/sdk` puts it at the root, `dubinc/dub-node` and
`gleanwork/api-client-typescript` both write theirs under `.speakeasy/`, which is a different path
and one nobody has checked is committed. Building the mechanism on one observation and calling it
general is the shape of mistake `2026-07-29-sync-adaptive-vendor-substrate.md` records twice.

Sound where it applies, and it applies to one vendor by luck rather than by contract. **Convenient,
not sound.**

### Rejected: snapshot the live URL each scan and diff against the previous snapshot

This one makes the vendor observable and I am rejecting it anyway, on three counts.

**Provenance.** A `vendor_change` row today means "the vendor shipped this between v1 and v2". A
snapshot-derived row means "Sync noticed this between two scans", which is a claim about our polling
schedule and not about the vendor's releases. `CLAUDE.md`'s three rungs — `static`, `resolved`,
`observed` — describe how a *binding* was derived and none of them accommodates it. The honest
provenance would be a fourth rung meaning "observed by us, at a time of our choosing", and inventing
a rung to make one vendor reportable is a large change to the evidence model bought for a small
gain.

**Idempotence.** `CLAUDE.md` requires every stage to converge on the same rows when re-run over the
same input, with exactly one named exemption for oasdiff-derived rows. Snapshot diffing makes the
wall clock an input: two runs over identical configuration produce different rows depending on when
they happened. That needs a second exemption, and the first one was granted against a measured
external defect rather than a design choice of ours.

**It contradicts the cache.** `_spec`'s docstring rests on "a version names an immutable artifact",
which is what makes a populated cache file safe to reuse and what makes the stale-fallback branch
unreachable rather than merely absent. Snapshots make a version name a mutable one, quietly
invalidating that reasoning wherever it is relied on.

### Taken: report the vendor as unobservable

Sync cannot diff two versions of a document it can only fetch one version of, and saying so is more
useful than reporting no changes. It is the same judgement `_spec` already makes about a fetch
outage — *"an outage that reads as 'this vendor changed nothing' is the exact failure this adapter
exists to catch, arriving from our own side"* — arriving from a third direction, and the noise report
made the identical call about noise filters. Three routes to the same silent-vendor failure, three
refusals, one rule.

It also closes the cost half outright, which neither rejected option does: a pair that cannot be
compared is no longer downloaded.

And it leaves the recovery available without code. The check is asked of the URL a run will
**actually fetch**, after `vendor_spec_urls` is consulted, so a deployment that supplies a versioned
URL per version restores the vendor with a configuration entry and no vendor name anywhere in the
path. `test_a_versioned_vendor_url_makes_a_one_document_manifest_observable` holds that open.

## 5. What was done about `spec_hash`: nothing, deliberately

**`_parse_speakeasy` still sets no `spec_hash`, and this is the argued position rather than an
omission left standing.**

The brief's standard is that a hash which moves when the document did not, or fails to move when it
did, is worse than no hash — it converts the early-out into a silent skip. Measured against the two
candidates available without a fetch:

- **The manifest text.** Fails in *both* directions. It moves when the workflow configuration
  changes — a ruleset edit, a target rename, an overlay path — none of which is the specification
  moving. And it does not move when the specification does: §1's measurement is that
  `workflow.yaml` is byte-identical across 12 commits spanning six weeks while the document it names
  changed on every one of them. The second direction is the fatal one, and this is a direct
  measurement of it rather than an argument about it.
- **A live fetch.** Answers the right question and cannot be the trigger for its own fetch. The
  early-out exists to avoid the download; hashing the download to decide whether to download is
  circular.

`sourceBlobDigest` from `.speakeasy/workflow.lock` is a genuine third candidate and §3 has the
evidence for it, but it lives in a file the configured manifest path does not name, and reading it
requires `generated-vendors.yaml` and `sync.signals.registry` — neither owned by this task. It is
specified as follow-up work in §8.

**The cost problem is closed anyway, and better than a hash would have closed it.** With the pair
reported unobservable, `fetch_changes` returns before resolving a URL. Vercel goes from two fetches
of 9,757,380 bytes per scan to zero, which is a stronger result than a correct hash would give — a
hash saves the fetch only while the document sits still, whereas refusing to diff a document against
itself saves it always. `test_an_unobservable_pair_fetches_nothing` asserts it with a counter.

## 6. How a caller distinguishes unobservable from unchanged

`fetch_changes` returned an empty list for four unrelated reasons and named none of them. It now
consults one verdict, and a caller can ask for the same verdict directly:

```python
adapter.observability(from_version, to_version)  # -> Observability
```

`Observability` carries `observable: bool`, a `reason` code, and a `detail` for an operator. The
three unobservable reasons are three different repairs, which is why a bare boolean was not enough:

| reason | what happened | the repair |
|---|---|---|
| `no-manifest` | no manifest parsed for one of the versions | name a version whose manifest parses |
| `no-specification` | the manifest names an endpoint count and no URL | this vendor needs a hand-written adapter |
| `one-document` | both versions resolve to the same location | supply a versioned specification URL per version |

An unmoved hash returns `observable=True` with no reason: the pair was examined and found unchanged.
That is the distinction the whole change exists to draw, and
`test_a_caller_can_tell_unobservable_from_unchanged` is where it is pinned — two adapters, both
answering `fetch_changes` with `[]`, disagreeing on `observability`.

**The ordering is load-bearing.** The hash is consulted *before* the locations. An agreeing hash is
positive evidence the specification did not move, and evidence is an answer however few documents
back it; checking locations first would relabel a vendor Sync can genuinely answer for as one it
cannot. Mutation M5 in §7 is that reordering, and
`test_an_agreeing_hash_answers_even_when_one_url_serves_both` kills it.

`fetch_changes` still returns `[]` and still logs rather than raising. A vendor outside this
adapter's reach is a coverage gap and not a fault; raising would let one such vendor abort a scan
across every other, which is the behaviour Cloudflare already depends on.

## 7. Mutation table

Nine mutations, each a plausible wrong implementation rather than a random character swap. All nine
killed, each by the test written for it.

| mutation | killed by |
|---|---|
| M1 the `one-document` branch never fires | `test_every_reason_carries_a_detail…[one-document]` (+6 more) |
| M2 the `one-document` branch always fires | `test_a_hash_missing_on_either_side_is_treated_as_changed[missing-after]` (+38 more) |
| M3 the `is_fetchable` guard removed | `test_every_reason_carries_a_detail…[no-specification]` (+4 more) |
| M4 `observability` always returns observable | `test_every_reason_carries_a_detail…[no-manifest]` (+12 more) |
| M5 locations checked before the hash | `test_an_agreeing_hash_answers_even_when_one_url_serves_both` |
| M6 locations read from the manifest, ignoring `vendor_spec_urls` | `test_a_versioned_vendor_url_makes_a_one_document_manifest_observable` |
| M7 `fetch_changes` ignores the verdict | `test_a_non_fetchable_vendor_does_not_raise` (+5 more) |
| M8 `no-manifest` and `no-specification` reasons swapped | `test_the_three_ways_of_not_looking_are_told_apart` (+1) |
| M9 `one-document` reported observable but empty | `test_one_url_at_both_commits_is_unobservable_rather_than_zero_changes` (+4) |

M3 and M5 are the two worth singling out, because both are orderings rather than conditions. M3
removes the `is_fetchable` guard that sits *in front of* the location comparison; without it, two
sources that each name nothing compare equal and Cloudflare gets reported as `one-document` — the
wrong repair, since that vendor needs a hand-written adapter and not a versioned URL. M5 moves the
location check ahead of the hash, which relabels a vendor whose own hash answers the question as one
Sync cannot answer for. Neither is a wrong comparison; both are a right comparison asked at the
wrong moment, which is the class of defect a coverage number cannot see.

M2's blast radius (39 tests) is the guard the brief asked for in a different form: a change that
refuses everything fails almost the entire generated-adapter suite rather than passing quietly.

**`manifest.py` is untouched, and the repository's own linter is why.** The first implementation put
a `names_the_same_document_as` helper on `SpecSource` and had the adapter compare resolved URLs
directly, so nothing called the helper. `lint_dead_links.py` failed the suite naming it — *"reached
from nowhere in the scanned tree; a component only a test calls is not wired in"* — which was
correct: the condition has to be asked of the URL a run will actually fetch, and only the adapter
knows about `vendor_spec_urls`, so a `SpecSource` method could never be the thing that decides.
Removing it also removed a `spec_url is not None` guard for a state `is_fetchable` already prevents.
The whole change is now one module.

**The first run of this harness reported all nine as survivors, and the harness was at fault.**
pytest wraps the `FAILED` token in ANSI escape codes, so a `startswith("FAILED")` match against the
raw line never fired and every mutation looked survived. `CLAUDE.md` says to suspect the mutation
before the test when one survives; that generalises to the harness, and nine-for-nine survival is
the tell. Fixed by stripping escapes and asserting a non-zero exit parses to at least one name.

## 8. What this did not fix

**A tagged registry reference is not fetchable and not parseable.** `_is_absolute_url` rejects
`registry.speakeasyapi.dev/…:v2`, so `_parse_speakeasy` returns `None` for Mistral and Glean and
those vendors cannot be served at all. Neither is configured, so nothing regressed. Closing it needs
a resolver for registry references, and §3 established the registry is not anonymously readable —
so this is blocked on credentials rather than on parsing.

**`.speakeasy/workflow.lock` would give Speakeasy a real cheap change trigger.** The evidence is in
§3: `sourceBlobDigest` moved in step with the document across all 11 adjacent pairs measured. The
lock also embeds the entire workflow under a `workflow:` key, so one parser keyed on that filename
could read both the location and the digest. It needs `generated-vendors.yaml` to name the lock and
`sync.signals.registry` to fetch it — neither owned by M3-W85. Worth taking, and worth taking with
the untested direction from §3 measured first: find two commits whose document did **not** move and
confirm the digest holds still, because a digest that churns per regeneration is merely wasteful
while one that misses a change is a silent skip.

**Nothing consumes `observability` yet.** It is queryable and no caller asks. The natural consumer
is the dependency-intake report `2026-07-29-sync-adaptive-vendor-substrate.md` sequences at step 2 —
its three-way split of watched, watchable-but-unconfigured and not-watchable is exactly the
distinction this verdict draws, and a vendor that is configured but unobservable belongs in the
middle bucket rather than the first. That report is not this task's to build.

**No dead-link baseline entry was added.** Nothing here introduces a link `lint_dead_links.py`
cannot resolve.

## 9. Commands, so a reader can re-run this

The two probes in §1 to §3 reach GitHub and the vendors' hosts, which is why they are shell work
recorded here rather than tests. They are not committed; the facts they produced are the tables
above.

```bash
uv run pytest tests/test_generated_observability.py -q
uv run pytest tests/test_generated_adapter.py tests/test_generated_manifest.py -q
```

The second is the regression check that matters most: `test_generated_adapter.py` is unmodified by
this task and its cases still pass, which is a stronger statement that the Stainless path is
unaffected than any assertion this task could have added.
