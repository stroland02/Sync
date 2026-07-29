# A third deprecation vendor, and the two rules that turned out to be facts about two pages

`parse_deprecation_table` was written against Anthropic and OpenAI. Both publish pipe tables,
both name models with a bare identifier, and both put the date in a cell. None of that is a fact
about vendor deprecation pages, and until a third page arrived there was no way to tell which of
the parser's rules were general and which were a coincidence between two documents.

Cloudflare's Workers AI retirement notice broke two of them and left seven untested. The parser
now reads it, the two existing vendors parse byte-identically, and nothing in `sync.index`,
`sync.detect` or `sync.route` had to change.

## The vendor, and why this one

**Cloudflare**, `developers.cloudflare.com`. Two properties decided it, and brand decided none of
it.

**Sync already knows the vendor.** `generated-vendors.yaml` registers `cloudflare` against
`cloudflare/cloudflare-python`, so `available_vendors()` already returns it and a finding raised
against it has somewhere to land. The alternative candidates were the other registered vendors —
Stripe and Twilio deprecate endpoints and products rather than models, and Vercel publishes no
model retirement list at a stable documented URL.

**It publishes the same information a different way.** This was the deciding property. A third
Markdown table would have tested almost nothing, because `_ROW` would have matched it and the
exercise would have confirmed a rule rather than examined it. Cloudflare publishes **no table at
all**: a heading names the date, and the models are a bulleted list beneath it. The model ids are
namespaced paths — `@cf/meta/llama-3.1-8b-instruct` — which the parser's identifier rule rejected
outright.

The page was **unreadable as fetched**: it parsed to zero rows, which the adapter correctly turns
into a raised `RuntimeError` rather than an empty change list. That is the honest starting point
this task existed to produce.

## What was captured

| | |
|---|---|
| URL | `https://developers.cloudflare.com/changelog/post/2026-05-08-planned-model-deprecations/index.md` |
| Fetched | 2026-07-29, once, by hand |
| Bytes | 4159 |
| sha256 | `c2cb3e804cf4befd5f7fd683f2a5ec18144e27ba054a638da7c8fa1df2f68013` |
| Committed as | `tests/fixtures/deprecations/cloudflare-workers-ai.md` |

The hash is of the bytes **as served**, which are LF-terminated. This repository runs with
`core.autocrlf=true`, so a working copy holds the same file with CRLF and hashes differently; no
test asserts the hash for that reason.

Cloudflare serves clean Markdown when `index.md` is appended to a documentation URL — the same
property the two existing sources rely on, so no HTML parser was introduced. The bare `.md`
suffix that works for Anthropic and OpenAI returns 404 here; the directory-plus-`index.md` form is
the one that works.

Two further pages were captured the same day and committed for the regression evidence below:

| Page | Bytes | sha256 |
|---|---|---|
| `https://platform.claude.com/docs/en/about-claude/model-deprecations.md` | 12764 | `2f7aba21d8f296d1b8add1c888040171221d9a53396f417b7cdf4f0de555c7d5` |
| `https://developers.openai.com/api/docs/deprecations.md` | 36257 | `cd2d867e201d3c4969ad42dcbad02464b96d2a091fb9c6c9b110bbce78fd6108` |

The OpenAI capture is worth its size for a second reason. `CLAUDE.md` records that every fixture
in this repository is ASCII, so no test can catch a missing `encoding="utf-8"`; this one writes
DALL·E with an interpunct, and `test_the_openai_page_carries_a_byte_that_is_not_ascii` pins that
property so the fixture cannot be quietly replaced with an ASCII trim.

**No test fetches any of them.** The three fetches above were manual and are recorded here.

## The prefixes, derived rather than guessed

`OPENAI.prefixes` carries a comment about `code-`, `codex-` and `ft-` being absent until somebody
checked, leaving sixteen real deprecated models unindexed. The same check was run here rather than
reasoning from the vendor's name, by extracting every namespaced identifier the page contains and
grouping by first segment.

```
distinct model ids named anywhere on the page: 27

distinct prefixes required:
  '@cf/'  covers 23 ids
  '@hf/'  covers 4 ids

if the prefix list had been guessed as ('@cf/',), 4 ids would never be indexed:
  @hf/google/gemma-7b-it
  @hf/meta-llama/meta-llama-3-8b-instruct
  @hf/mistral/mistral-7b-instruct-v0.2
  @hf/nousresearch/hermes-2-pro-mistral-7b
```

**Guessing `@cf/` from the vendor's name would have been wrong**, and wrong in exactly the silent
way the OpenAI comment describes. Cloudflare re-hosts Hugging Face models under an `@hf/`
namespace, and three of those four ids are among the eighteen actually being retired. The
catalogue would have parsed, the detector would have run, and three findings would have pointed at
nothing.

`test_every_model_id_the_page_names_is_covered_by_the_prefixes` runs that extraction against the
committed fixture, independently of the parser — asking the parser which ids it found could only
ever confirm that the prefixes cover what already parsed.
`test_the_page_names_the_ids_this_check_expects` pins the count at 27, so a regex that stopped
matching would fail rather than pass over an empty set.

## Every rule, measured against the third page

**Silent is not agreement.** Seven of the parser's fourteen behaviours are simply not exercised by
this page, and recording that is more useful than a green tick would have been.

| Rule | Third page | What the page does |
|---|---|---|
| `_ROW` — a row is a pipe-table row | **Disagrees** | No pipe table anywhere on the page |
| `_looks_like_a_model_id` — no path separator | **Disagrees** | Every id is `@cf/…` or `@hf/…` |
| `_parse_date` — a date fills a whole cell | **Disagrees** | The date sits inside heading prose |
| Replacement comes from a third table column | **Disagrees** | An arrow on the bullet: `` `a` --> `b` `` |
| Cells arrive unescaped | **Disagrees** | Markdown-escaped as `\-->` |
| `_looks_like_a_model_id` — no brackets, parens or whitespace | **Agrees** | The three "Recommended replacements" bullets are Markdown links and are correctly excluded |
| `_strip_code` — ids are wrapped in backticks | **Agrees** | Every bullet wraps its id in backticks |
| `_DATE_FORMATS` — `%B %d, %Y` | **Agrees** | "May 30, 2026" |
| `_derived_state` — infer state from the date | **Agrees** | No lifecycle column, so the date decides |
| `_state_of` — a state is a word in a cell | **Silent** | The page says "remain active" in a heading, in prose, where no cell rule could see it |
| `_NOT_BEFORE` — "not sooner than" is a floor | **Silent** | The page states no floor |
| `_is_placeholder` — `---`, `N/A`, em dash | **Silent** | The page omits a replacement entirely rather than writing a placeholder |
| `_SEPARATOR` — skip a table's rule row | **Silent** | No tables |
| `_DATE_FORMATS` — `%b %d, %Y` and `%Y-%m-%d` | **Silent** | Only the full month name appears |
| Explicit state wins over a derived one | **Silent** | No explicit state is published |

The two disagreements that mattered are the first two. The other three were mechanical once the
shape was understood.

**On `_state_of` being silent rather than agreeing** — this one is worth naming, because the page
*does* publish lifecycle information and the parser cannot see it. "Variants that remain active"
is a heading over six models that are explicitly not being retired. Nothing reads it as a state;
what keeps those six out of the results is that their heading carries no date, not that the parser
understood the word "active". A page that listed them under a dated heading would produce six
wrong rows, and no rule currently in the parser would prevent it.

## What changed in `catalogue.py`

Three changes, each admitted only because a test proved the parser could not read a real page.

**1. A namespaced id may contain a separator.** `_looks_like_a_model_id` returned False for any
text containing `/`, which excluded every Cloudflare model. The rule existed to keep OpenAI's
endpoint deprecations — `/v1/edits`, `/v1/engines` — out of a signal that cannot repair them, and
that purpose is intact: what separates the two is the **leading** character. A path starts at the
root; a namespaced id does not. A slash now disqualifies a cell only when nothing namespaces it.

Proved necessary by `test_the_published_page_parses_to_the_models_it_lists` and
`test_a_namespaced_model_id_survives_intact`, both of which failed with a `KeyError` on every
Cloudflare id before the change. The narrowness is held by
`test_an_endpoint_path_is_still_not_a_model` and the pre-existing
`test_an_endpoint_is_not_a_model`.

**2. A third published shape: `_parse_dated_lists`.** A heading carrying a date opens a section;
bulleted lines within it name retired models; an arrow on the bullet names the replacement. The
retirement date comes from the heading.

The load-bearing detail is that **an undated heading closes the section.** The same page lists
"Variants that remain active" in the identical bullet shape directly beneath the retirements, and
a parser that ran to the end of the document would emit six breaking findings against models the
vendor has just promised to keep. `_date_in` finds a date inside a heading's prose and hands every
candidate to `_parse_date`, so `_DATE_FORMATS` stays the single place that decides which spellings
are accepted.

Proved necessary by the same two tests, and its bound proved by the six-case parametrized
`test_a_model_the_page_says_remains_active_is_not_a_row`.

**3. Announcement rows now record what they stated.** The announcement loop did not add to
`stated` because it was the last loop and nothing read the set afterwards. The dated-list loop now
runs after it, so a model named in both an announcement table and a list would have produced two
rows with two retirement dates and nothing downstream able to say which is current — a violation
of the natural-key rule in `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md`.

Proved necessary by `test_a_table_row_is_not_repeated_by_the_list_beneath_it` and
`test_a_model_listed_under_two_dated_headings_yields_one_row`.

One thing was **removed** rather than added. The arrow pattern was first written requiring
whitespace on both sides, with a comment claiming that otherwise "every hyphen in
`llama-3-8b-instruct` is a candidate arrow". That comment was false — the pattern requires a `>`,
so a bare hyphen was never a candidate — and mutation M6 exposed it by surviving. The requirement
guarded nothing and was deleted along with the claim.

## The two existing vendors did not move

Counts and digests were taken from the parser **before** this task changed it, and asserted after.
The digest covers every field of every row, not merely the count: a count alone would miss a
replacement that stopped resolving or a date that shifted, which are the two ways this change
could have damaged a vendor it never mentions.

| Vendor | Rows before | Rows after | Digest |
|---|---|---|---|
| Anthropic | 29 | 29 | `a8ad11d8a49bb85f1ec1ea1b4c1bdf6f680c5104cf6356d9b971a1ed77f4e9ca` |
| OpenAI | 108 | 108 | `e0172d04f010cc10cb3716789e048e6c24be6d46a91eb8472a11a59026dde6f6` |

Those counts are the same 29 and 108 the design document recorded on 2026-07-28.

The reason the list parser cannot disturb them is structural rather than lucky, and was checked
before the code was written: Anthropic's page has nine dated headings and OpenAI's has thirty-one,
and **neither page has a single bulleted line under any of them.** Both vendors put their content
in tables. The new shape reads only bullets, so it is silent for both.

`test_an_existing_vendor_parses_exactly_as_it_did` is not a decorative assertion — mutations M2
and M11 both killed it, which is what proves it can fail.

## The adapter's structure held

Nothing in `adapter.py` changed except the addition of a third `DeprecationSource` constant.
`DeprecationAdapter` needed no new field, no branch and no flag: fetching, caching, the stale-cache
fallback and the raise-on-empty behaviour all serve the third vendor unchanged.
`test_a_third_vendor_needs_no_adapter_change` asserts that against the committed page.

**But the list of sources is in the wrong module, and that is the structural finding.**
`DEPRECATION_SOURCES` is a tuple in `src/sync/cli.py` (line 93), so a source added to the adapter
module reaches no scan. Adding `CLOUDFLARE` to the module made it importable and tested; it did
not make it *run*.

This is the same defect `sync/signals/registry.py` was written to fix for vendor adapters, and
that module's own docstring describes it exactly: `cli.py` constructed `StripeAdapter` by name, so
no run could reach the second adapter, and "what was unreachable there was not a feature but the
claim the project rests on."

There is a second problem in the same tuple. `DEPRECATION_SOURCES` feeds **two** call sites with
different needs — `_parameter_deprecations` at line 524 reads each source's page for a parameter
table, and `_model_deprecations` at line 624 reads it for model retirements. The tuple's own
comment says "Both publish one page carrying both a model lifecycle table and a parameter table",
which is true of Anthropic and OpenAI and false of Cloudflare: its page carries model retirements
and no parameter table at all. Registering Cloudflare in that tuple as it stands would hand a
parameter parser a page that has no parameters. The correct shape is two lists, or one list whose
entries declare which signals they carry.

`src/sync/cli.py` is outside this task's files, so neither was changed.

## Nothing is needed from `sync.index` or `sync.detect`

This was checked rather than assumed, because a namespaced id was the obvious candidate for
breaking the binding half.

`index_operation_literals` filters candidate literals with `value.startswith(prefixes)` and
imposes no shape of its own, so `@cf/meta/llama-3.1-8b-instruct` indexes exactly like
`claude-opus-4-1-20250805`. DETECT joins on `operation_id` equality. The tier-0 repair path also
works unchanged: `model_literal_swap` emits one `ast-grep` rule per quote style and both apply.

`test_a_path_shaped_model_id_survives_index_join_and_patch` runs the whole chain — three literals
indexed from a realistic Workers AI call, two joined to dying models, one swapped to its published
replacement, and the healthy model and the replacement-less model both left untouched.

Two exclusions the design document lists as deliberate were **not** reversed. Template literals
remain unindexed, and `operation_for_symbol` still returns `None` for every symbol.

## Mutation results

Eleven mutations, each applied to the shipped source and reverted afterwards.

The harness needed two fixes of its own before any result from it was worth reading, and both
produced the same false answer — *every mutation survives*, which is indistinguishable from a
suite that tests nothing. `CLAUDE.md` warns that a surviving mutation is more often the mutation's
fault than the test's, and it was right twice in a row here.

- The first run passed `-p no:xdist`, which collided with `-n auto` in `addopts`; pytest exited 4
  with a usage error and printed no `FAILED` lines at all.
- The second run parsed stdout with `line.startswith("FAILED")` while pytest was emitting ANSI
  colour codes, so no line ever matched.

The harness now refuses to report anything unless the unmutated suite is green **and** a sentinel
mutation kills at least one test, and treats any exit code outside {0, 1} as its own failure.

| # | Mutation | Result |
|---|---|---|
| — | **Sentinel**: no cell is ever a model id | killed 24 — a kill is detectable |
| M1 | Model id: forbid every slash again (restore the two-page rule) | killed 13 |
| M2 | Model id: allow a slash anywhere, namespaced or not | killed 3, incl. `test_an_endpoint_is_not_a_model` and the Anthropic/OpenAI digest |
| M3 | Dated list: an undated heading no longer closes the section | killed 3, incl. `test_a_model_the_page_says_remains_active_is_not_a_row` |
| M4 | Dated list: drop the Markdown unescape | killed 8 |
| M5 | Dated list: never split on the arrow | killed 8 |
| M6 | Arrow: accept only the exact `-->` the page writes | **survived** |
| M7 | Heading date: never find one | killed 12 |
| M8 | Dated list: drop the already-seen guard | killed 2 |
| M9 | Announcements: stop recording what they stated | killed 1 |
| M10 | Prefixes: guess one family from the vendor name | killed 4 |
| M11 | Dates: stop accepting an abbreviated month (control) | killed 7, incl. the OpenAI digest |

M11 was included as a control on the regression digest specifically — it changes an existing
vendor's parse and nothing about the third — and it killed
`test_an_existing_vendor_parses_exactly_as_it_did`, which is what licenses trusting that assertion.

**M6 survived, and the mutation was right.** Narrowing the arrow pattern from `-{1,2}>|→` to the
literal `-->` changes no result, because `-->` is the only arrow form any of the three pages
writes. The `->` and `→` alternatives are unexercised — silent, not agreed with. They are kept
deliberately: an unrecognised arrow does not merely lose the replacement, it loses the whole row,
because the unsplit bullet then contains whitespace and fails the model-id rule. That is a
one-character-class insurance against losing a finding entirely, and it is recorded here as
untested rather than left to look verified.

An earlier form of M6 also survived and was the defect described above — the whitespace
requirement that guarded nothing. That one was resolved by deleting the guard.

## Gates

Run on the final tree, unpiped, exit codes checked.

| Gate | Result | Exit |
|---|---|---|
| `uv run pytest -q` | 2157 passed, 2 skipped | 0 |
| `uv run python scripts/lint_encoding.py src scripts tests` | clean | 0 |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 1 contract kept, 0 broken | 0 |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | clean | 0 |

The suite collected 2126 tests at this branch's point on `origin/main` and 2159 afterwards, a
delta of exactly +33: 31 in the new file and one in `test_deprecation_adapter.py`, plus one more
parametrized case from adding `CLOUDFLARE` to the shipped-source check.

## What the next task should take

1. **Wire the third source.** `DEPRECATION_SOURCES` must leave `cli.py`, and it must split by
   which signal a source actually carries — Cloudflare publishes model retirements and no
   parameter table, and the current single tuple feeds both parsers.
2. **A state that is published as prose.** "Variants that remain active" is real lifecycle
   information this parser cannot read. Nothing depends on it today because the heading carries no
   date, but the safety is incidental rather than designed.
3. **A fourth vendor should be chosen for a shape none of these three use** — an HTML-only page, a
   JSON or YAML feed, or a page with no dates at all. Three pages now agree that a date exists and
   is findable; that is still only three pages.
