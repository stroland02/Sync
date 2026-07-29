# Provenance for the three measurements that read a gitignored cache

`docs/superpowers/specs/2026-07-29-sync-spec-audit-log-2.md` groups the claims it could not verify
by the reason it could not verify them. One of those groups is a single sentence:

> **It derives from a gitignored cache.** The 105-of-414 symbol coverage, the 327,124-record depth
> measurement, and the three dated Stripe versions all read `.cache/specs/`.

`.cache/` is gitignored deliberately, so a fresh checkout could not re-derive any of the three, and
a figure nobody can re-run is a figure nobody can challenge. This document records the path from an
empty checkout to each input, and `scripts/fetch_measurement_inputs.py` walks it.

Nothing here re-states or corrects a documented figure. One of the three was cheap enough to
re-derive as a check on the path itself, and it agreed; that is recorded below and changes nothing.

## The path

```
uv run python scripts/fetch_measurement_inputs.py            # all three measurements
uv run python scripts/fetch_measurement_inputs.py --list     # what would be fetched, fetching nothing
uv run python scripts/fetch_measurement_inputs.py --measurement symbol-coverage-105-of-414
```

It needs the authenticated `gh` CLI, which `CLAUDE.md` already assumes. It writes into
`.cache/specs/` under the names `sync run`, `sync ingest` and `sync shapes` already look for, so a
reader who runs it once is in a position to re-take any of the three measurements with the
commands those documents describe.

## What each measurement reads, and how it is pinned

Eight artifacts, all from `stripe/openapi`. Each is pinned four ways: the tag to fetch by, the
commit that tag resolved to on 2026-07-29, the git blob hash of the file at that commit, and its
length in bytes.

| measurement | inputs | source document |
|---|---|---|
| `symbol-coverage-105-of-414` | `spec3.json` and `spec3.sdk.json` at `v2330` | `2026-07-25-sync-self-maintaining-apis-design.md` |
| `breaking-record-depth-327124` | `spec3.json` at `v2320` and `v2330` | the same document |
| `three-dated-stripe-versions` | `spec3.json` at all seven tags | `2026-07-28-sync-ground-truth-count.md`, `2026-07-29-sync-ground-truth-quality.md` |

| tag | commit | `spec3.json` blob | bytes | `info.version` |
|---|---|---|---:|---|
| `v2200` | `a62576f6c21328289aec64935b6fd3cb81118ed6` | `7546a97be72fbadc9bdb1bae3cd561286b8c5ecd` | 7,598,844 | `2026-02-25.clover` |
| `v2300` | `a7e607228d9579adf9f0367128bb5539a793827d` | `c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3` | 7,830,636 | `2026-05-27.dahlia` |
| `v2320` | `c5dcebd5209b9d34974a4101a3de604998f88558` | `c5d6078dd0b1392623a0d0c7a579f828ccb3a1f3` | 7,830,636 | `2026-05-27.dahlia` |
| `v2330` | `62d4d7c732ca9603130284866b00ba267bf93a10` | `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d` | 7,866,866 | `2026-06-24.dahlia` |
| `v2331` | `b9e97324c782479a93798fbe7c0ce110439c051b` | `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d` | 7,866,866 | `2026-06-24.dahlia` |
| `v2340` | `635a63d3abcfa7fef32c3788451e5a5c1caaaa03` | `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d` | 7,866,866 | `2026-06-24.dahlia` |
| `v2345` | `86b6ae4db114ff06968dcc191ff4a898e9b5db7c` | `634a4b329a8e6f0d1dd13373d9f92458d0e6ee6d` | 7,866,866 | `2026-06-24.dahlia` |

`spec3.sdk.json` is pinned at `v2330` only — commit as above, blob
`3e278ec902d488bf3aa41eb0294b8c1fd15ddc14`, 10,059,776 bytes. No documented measurement reads it at
any other tag, and it is the largest single artifact here.

### Why a tag is not the pin

A tag is a pointer and a commit is not. A script that fetched by tag alone would look reproducible
while quietly producing different bytes if Stripe ever re-pointed one. The blob hash is what does
the work: it is computed from the bytes themselves, so a moved tag, a truncated response and a
proxy that rewrote the document all fail the same check, before anything is written to disk. The
commit is recorded beside it because it is what still names the tree if a tag does move.

## What is committed and what is left to a fetch

**Left to a fetch: the specifications.** Seven `spec3.json` and one `spec3.sdk.json` is 55 MB of
vendor document. `.gitignore` excludes `.cache/` for a reason, and vendoring megabytes of a third
party's artifact to make a number checkable is the wrong trade when the number can be made
checkable with 24 KB instead.

**Committed: the evidence a fetch is checked against.** Two files, both under
`tests/fixtures/measurement_inputs/`, following the pattern `generated-vendors.yaml` and
`tests/fixtures/sdk_packages/` already set — the declaration lives in code, the vendor's own
statement lives beside it as a fixture, and a test holds the two in step.

- `stripe-openapi-github.json`, 23 KB. GitHub's answers about the seven tags, captured verbatim on
  2026-07-29: the tag ref, the annotated tag object it dereferences to, and the contents envelope
  for both files at each tag. This is where every blob hash, byte count and commit in the table
  above came from. It is what makes the pins checkable against the vendor rather than against a
  copy of themselves.
- `stripe-spec3-info.json`, 1.4 KB. The `info` object lifted verbatim from each of the three
  distinct specifications, keyed by the blob hash it came from. This is about 200 bytes apiece and
  it is the only part of a 7.8 MB document that any of the three measurements quotes — the three
  dated versions are exactly `info.version` at three tags. Its provenance matters more than its
  size, which is the criterion that separates it from the specifications themselves.

`.gitignore` needed no change. Everything committed sits under `tests/fixtures/`, which is already
tracked, and nothing that was ignored should now be tracked.

## Seven tags, three specifications

The blob hashes settle something the design document had to correct a measurement over. `spec3.json`
is byte-identical across `v2300` and `v2320`, and across `v2330`, `v2331`, `v2340` and `v2345` —
Stripe tags every SDK release whether or not the specification moved. The seven tags carry three
distinct documents, which is why there are three dated versions and not seven.

That was previously an observation about what one machine's `.cache/specs` happened to hold.
`2026-07-25-sync-self-maintaining-apis-design.md` states it as the reason `v2320→v2330` and
`v2300→v2330` are one window rather than two. It is now a statement about what Stripe published,
attested by GitHub's own blob hashes, checkable without downloading anything.

The fetcher acts on it: a tag whose blob is already on disk under another tag is copied rather than
fetched again. A full run downloads three specifications and one SDK document rather than eight
files, which is 30 MB it does not spend, and the copy is reported as a copy so the duplication is
visible in the output rather than asserted in a comment.

## Refusing rather than half-fetching

`verify` checks length, then blob hash, then — for the documents whose `info` excerpt is committed —
`info.version`, and raises `InputMismatch` before anything is written. Length is checked first
because it has the most misleading downstream behaviour: a truncated JSON document usually raises
somewhere far away and occasionally does not raise at all, and a measurement taken over one is wrong
by an amount nobody can see.

A destination that already exists is verified rather than trusted, and a cached file that fails is a
failure and not a cache miss. Silently replacing it would hide whatever wrote the wrong bytes. This
matters more than it looks: `sync.signals.stripe.adapter.fetch_spec` returns any non-empty
destination as-is without reading it, so before this script nothing in the repository ever checked
that a cached specification was the specification it claimed to be.

Demonstrated rather than asserted. Truncating `.cache/specs/v2331.json` to half its length and
re-running:

```
refused: v2331/spec3.json at v2331: expected 7866866 bytes, got 3933433
(exit 1)
```

## What was verified

- **Every pin against the vendor.** `tests/test_measurement_inputs.py` asserts each blob hash, byte
  count, path and commit in the table against the captured GitHub responses, and each declared
  `info.version` against the committed `info` excerpt.
- **The blob hashing itself against an outside reference.** `git_blob_sha` is asserted against
  `e69de29bb2d1d6434b8b29ae775ad8c2e48c5391` and `ce013625030ba8dba906f756967f9e9ca394464a`, the
  hashes every git repository contains for an empty file and for `hello\n`. A hash function that
  hashed content without git's `blob <length>\0` prefix would agree with nothing GitHub reports, and
  would agree with a test that computed the expectation the same wrong way.
- **The whole path, end to end.** A run from a cache holding three specifications produced all eight
  verified artifacts: three cached, four copied, one fetched.
- **That the pins are checkable in both directions.** Each of five mutations to the table — a blob
  hash digit, a byte count, a commit digit, an `info.version`, and a measurement naming an input
  nothing pins — was introduced in turn and failed the suite; the file was restored afterwards.

## The one figure re-derived, and it agreed

Not a re-measurement, and it changes nothing: the point was to check that the fetched inputs are the
inputs the documented figure was taken over. `build_symbol_map` over the fetched `v2330`, with and
without the SDK document:

```
with x-stableId: 179 symbols over 105 of 414 /v1/ paths
without:         179 symbols over 105 of 414 /v1/ paths
```

`2026-07-25-sync-self-maintaining-apis-design.md` states "179 symbols over 105 of 414 paths **before
and after**". It reproduces exactly. No document needs an edit and none was made.

## What is not reproducible, and why

**The 327,124-record depth measurement is re-runnable but was not re-run.** Its two inputs are now
pinned and fetched, which is what this task was for. Taking it needs `oasdiff` over a 7.8 MB pair and
runs in minutes rather than seconds, and re-running a measurement is a separate decision from making
it re-runnable. Anyone re-taking it should note that the numbers in this corpus disagree about which
window they describe: `src/sync/signals/stripe/adapter.py` records "86,368 of 107,396 records between
v2320 and v2330" beside `NOISE_KINDS`, while the design document records 672,286 raw and 327,124
filtered over what the duplicate specifications collapse to the same window. Both cannot be a count
of the same thing. That is a discrepancy between two documented figures rather than a defect in an
input, and it is reported rather than resolved.

**The ground-truth counts remain network facts.** Everything in
`2026-07-28-sync-ground-truth-count.md` that comes from GitHub's search API — the 23,926 files, the
commit totals per dated version — is a live query whose answer moves. The three dated versions were
the part of that document that read the gitignored cache, and they are now pinned; the search totals
were already run through `scripts/mine_stripe_migrations.py` and are dated rather than pinned,
because there is nothing to pin them to. `OBSERVED_API_VERSIONS` in that script is the same three
strings this document now attests, and its comment saying the list "is not reproducible from a fresh
clone" is, as of this commit, out of date in the direction of understating what exists.

**No test fetches anything.** GitHub is a vendor API and `CLAUDE.md` forbids a test calling one. The
split is the one `scripts/mine_stripe_migrations.py` already uses: fetching is impure and untested,
and everything that decides whether a fetched artifact is the right one is pure and is all that is
asserted on.
