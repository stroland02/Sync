# Ground truth by mining: the count

`docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md` proposes labelling binding
precision and recall from migrations that already happened, and then forbids building the
harness until someone counts what is out there. This is that count. It was run on
**2026-07-28** with `scripts/mine_stripe_migrations.py` against GitHub's search API through
an authenticated `gh` CLI.

Nothing was cloned, no parent commit was checked out, and no part of Sync's pipeline was
run. The instrument issues searches and counts responses.

## What "breaking release" could be established, and what could not

The spec asks for repositories that bump their pin *across a release Stripe classifies as
breaking*. **Stripe's own classification is not in this repository, and no list of release
dates was invented to stand in for it.**

The committed fixtures carry no release dates at all.
`tests/fixtures/specs/charges_base.json` and `charges_revision.json` both declare
`"version": "base"`, and `tests/fixtures/specs/stripe_v2330_shape.json` has no `info` block.
They are trimmed shapes, not dated specifications.

Three real dated versions were observable, read from the `info.version` field of the
specifications in `.cache/specs/`:

| tag | `info.version` |
|---|---|
| `v2200` | `2026-02-25.clover` |
| `v2300`, `v2320` | `2026-05-27.dahlia` |
| `v2330`, `v2331`, `v2340`, `v2345` | `2026-06-24.dahlia` |

Two qualifications travel with that table. `.cache/` is gitignored, so this list is **not
reproducible from a fresh clone** — it is what this machine happened to hold. And a release
train changing name (`clover` to `dahlia`) is an observation about naming, not Stripe's
statement that the release was breaking. The boundary used below is therefore *the three
dated versions this repository could observe*, and it is a proxy.

That proxy has a consequence that shapes the rest of this document: all three observable
versions fall in 2026, so every version-specific number below describes migrations from the
last five months only.

## The numbers

Every count is `total_count` as GitHub reported it, not the length of the returned page.

### Repositories pinning a Stripe API version

Code search, endpoint `search/code`, run 2026-07-28:

| query | total | outcome |
|---|---:|---|
| `"apiVersion: '20" language:typescript` | 11,268 | complete |
| `"apiVersion: '20" language:javascript` | 10,880 | complete |
| `"stripe.api_version" language:python` | 1,336 | complete |
| `"Stripe.api_version" language:ruby` | 442 | complete |
| **sum** | **23,926** | |

**23,926 is a count of files, not repositories.** Code search indexes files, and the spec's
question is about repositories. The only place the ratio is observable is the returned page:
the TypeScript page held 30 files across 30 distinct repositories, JavaScript 30 across 27,
Python 30 across 21, Ruby 30 across 19. The true repository count is lower than 23,926 by a
factor this measurement cannot establish.

### Commits that bump the pin

Commit search, endpoint `search/commits`, run 2026-07-28:

| query | total | outcome |
|---|---:|---|
| `apiVersion stripe` | 4,991 | complete |
| `stripe api version bump` | 30,096, then 30,098 | truncated, then complete |
| `"2026-02-25.clover"` | 728 | complete |
| `"2026-05-27.dahlia"` | 531 | complete |
| `"2026-06-24.dahlia"` | 349 | complete |

The three version-specific queries are the closest available answer to the spec's second
question: **1,608 commits name one of the three observable dated versions.**

The second row is recorded with both its answers on purpose. The identical query returned
30,096 with `incomplete_results` set, and then 30,098 settled, minutes apart in the same
session. GitHub's search totals are approximate and move between runs; a single figure
quoted from one run overstates its own precision.

### The measurement that changes the verdict

**GitHub commit search matches commit messages, not diffs.** Every result in the sampled
pages carried the searched version string in its message. A commit that changes `apiVersion`
under the message `chore: update dependencies` is not findable by any query in this document,
and a commit whose message names a version may not have changed a pin at all. The 1,608 is
therefore neither a subset nor a superset of the real population — it is the population that
happened to announce itself.

Sampling the repositories behind those commits is what makes this concrete. Of the 29 distinct
repositories on the first page for `"2026-06-24.dahlia"`:

- **23 have zero stars.**
- **27 of 29 were created in 2026.**
- The two highest-starred are `stripe/openapi` (Stripe's own specification repository) and
  `simontreanor/FunStripe` (an F# SDK port). Neither is a customer integration, and both
  would have to be excluded.

The 12 distinct repositories sampled for `"2026-05-27.dahlia"` were the same shape: every one
had zero or one star, and every one was created between 2026-05 and 2026-07. Their commit
messages are formulaic and multilingual — `fix: update Stripe apiVersion to 2026-05-27.dahlia`,
`fix: actualizar version Stripe API a 2026-05-27.dahlia`,
`fix: aligne apiVersion Stripe webhook sur 2026-05-27.dahlia`.

The *pin* population looks nothing like this. Of the 30 distinct repositories on the first
TypeScript pin page, 7 have 100 or more stars, 16 have 10 to 99, 6 have 1 to 9, and 1 has
none, with creation dates spread from 2017 to 2025. That page is ranked by relevance and is
not a random sample, so it flatters the population — but the contrast with the bump cohort is
not subtle, and it is the finding that matters.

## Verdict

**The approach is viable on sample size and unproven on label quality.**

On the spec's own stated test — *if the answer is a handful, the approach fails on sample
size* — the answer is not a handful. Tens of thousands of files carry a pin and 1,608 commits
name an observable version boundary. Sample size is not the binding constraint, and the
fallback the spec names for that failure, synthetic mutation of real repositories at the cost
of realism, is not triggered by this count.

What the count does establish is that the deciding question has moved. It is no longer *are
there enough migrations?* but *are the ones a search can find worth labelling with?* In the
only window this repository can observe, the findable migrations are overwhelmingly
zero-star projects created within the last three months, carrying commit messages uniform
enough to suggest they were written by coding agents rather than by engineers with full
context. That is not the labelled reference the spec was reaching for, and this count cannot
tell whether an older, healthier cohort exists, because the three dated versions available
here are all from 2026.

## The three weaknesses, against what was measured

**Survivorship.** The spec expected successful migrations to be over-represented. The
measurement found something more specific and more troublesome: the two search surfaces have
*opposite* biases. Code search ranks by relevance and returned a pin cohort skewed healthy —
7 of 30 repositories with 100 or more stars, spanning 2017 to 2025. Commit search returned a
bump cohort skewed to the floor — 23 of 29 with zero stars, 27 of 29 created this year.
Treating 23,926 pins and 1,608 bumps as two measurements of one population would be wrong;
they describe different populations selected by different rankings. Abandoned integrations
remain invisible to both, as the spec says, and so does any repository that was deleted, made
private, or had its history rewritten.

**The human is not always right.** The spec's concern was that a merged migration commit may
be incomplete and fixed later. That concern stands and this count cannot address it — nothing
in a search response says whether a migration was later corrected. But the sampling surfaced a
sharper version the spec did not anticipate: **the author may not be a human.** In a cohort of
zero-star repositories created weeks before the commit, with messages as templated as
`fix: update Stripe apiVersion to <version>` across four languages, the plausible author is a
coding agent. An agent's patch is not a labelled correct answer; it is another tool's output,
which makes the label circular in exactly the way the spec was trying to avoid by not using
Sync's own corpus. Nothing in the GitHub search response distinguishes the two.

**Commit granularity.** This could not be measured here, and the reason is itself a finding.
Establishing whether a migration is isolable requires reading each commit's diff, which is
outside this task's scope and outside what search returns. Because commit search matches
messages, the numbers above are already filtered toward commits whose message is *about* the
version bump — which plausibly correlates with the bump being the whole commit, and would bias
the found population toward the simple migrations the spec warns about. The exclusion rate for
bundled migrations is unknown and applies to the 1,608 as an undetermined discount.

## What could not be measured, and why

- **Repositories, as opposed to files.** Code search counts files. No query returns a distinct
  repository count, and per-page ratios (30 files to 30, 27, 21, and 19 repositories) are the
  only evidence available.
- **Private repositories.** Invisible. The whole count describes public GitHub only.
- **The 1,000-result retrieval cap.** GitHub reports `total_count` but serves at most 1,000
  results per query. Every total above 1,000 in this document is a number that can be read but
  whose members cannot be enumerated from that query alone.
- **Total instability.** As recorded above, one query returned two different totals minutes
  apart, one of them flagged incomplete. These are estimates.
- **Rate limits.** This account allows 10 code searches and 30 searches per minute. The count
  fits inside that; a full enumeration would not.
- **Stripe's breaking-release classification.** Not present in the repository in any form. The
  three dated versions used here came from a gitignored cache, and whether Stripe classifies
  the transitions between them as breaking was not established.
- **Whether an older, healthier migration cohort exists.** The observable boundary is three
  2026 dates. Migrations across earlier releases, by the established repositories visible in
  the pin cohort, are outside what this measurement could reach.
