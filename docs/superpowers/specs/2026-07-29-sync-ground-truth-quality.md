# Ground truth by mining: the reading

**Date:** 2026-07-29
**Status:** Verdict reached. **Mined Stripe migrations cannot serve as ground truth for binding
precision and recall.** The recommendation is the fallback the benchmark specification already
names: synthetic mutation of real repositories, at the cost of realism.
**Scope:** Label quality only. `2026-07-28-sync-ground-truth-count.md` settled sample size and
is not revised here — it is a dated record of what was measured that day, and this is what was
measured the day after.

## What the count left open

The count answered the question the benchmark specification demanded be answered before anyone
built a harness, and returned a verdict in two halves: *"The approach is viable on sample size
and unproven on label quality."*

Sample size is settled. What it could not settle is whether the findable commits are worth
labelling with. It sampled the repositories behind one page of results — 23 of 29 with zero
stars, 27 of 29 created in 2026, commit messages formulaic and multilingual — and drew the only
conclusion available from message shape: the plausible author is a coding agent. It said so
carefully, as an inference rather than a finding, because nothing in a search response
distinguishes an agent from a person.

That inference is now measured. It is correct, and the reading found a second reason the
approach fails that has nothing to do with authorship.

## What was read, and how it was chosen

`scripts/read_stripe_migrations.py` is the instrument, a sibling of the counting one rather than
an addition to it: that module reduces a search response to a total, this one reads a commit and
reports who wrote it and what it touched.

The pool is every commit GitHub returns for each of the three dated versions the repository can
observe, taken at both ends of an author-date sort rather than from the top of a relevance
ranking. That is not a random sample and this document does not claim it is — it is a different
slice from the one the count took, which is the most that is cheaply available, and taking both
ends is what stops the sample being the newest commits or the oldest.

Six queries returned 600 hits and 584 distinct commits. Every fifth was read in full through the
commits API: **117 commits, 0 unreadable**.

The count's own standard applies to this figure too. A sample drawn this way flatters nothing in
particular, but it cannot represent commits whose message never names a version — and by
construction there is no way to reach those through commit search at all, which is itself one of
the findings below.

## Authorship: measured, not inferred

Three signals, and they fail differently. A `Co-authored-by` trailer is a written statement. A
`Bot` account type is GitHub's own classification. A login matching a known agent catches a human
account driven by one.

| Signal | Commits | Share |
|---|---:|---:|
| Agent co-author trailer | 68 | 58% |
| Bot author or committer | 21 | 18% |
| Either | 74 | 63% |
| Neither — *unsignalled* | 43 | 37% |

The trailers are not ambiguous. Across the sample they name, in order of frequency:

```
55  Claude Sonnet 4.6 <noreply@anthropic.com>
16  Claude Opus 4.6 <noreply@anthropic.com>
12  Claude Opus 4.7 <noreply@anthropic.com>
10  Claude Opus 4.7 (1M context) <noreply@anthropic.com>
10  Claude Opus 4.8 <noreply@anthropic.com>
 9  Claude Fable 5 <noreply@anthropic.com>
 7  dependabot[bot]
 2  Cursor <cursoragent@cursor.com>
```

Twenty-eight distinct trailer identities, of which all but four name an agent or a dependency
bot. The count's suspicion was right and it was understated.

**Unsignalled is not the same as human-authored**, and the 37% must not be read that way. An
agent that leaves no trailer is indistinguishable from a person, and three of the unsignalled
commits carry agent tooling in the diff itself — `.cursor/rules/`, `.opencode/skills/`, and one
carrying `docs/superpowers/plans/`, this repository's own workflow layout. The file-path signal
is weak, catching 6% of the sample, because tooling directories are usually gitignored or
committed once. It corroborates; it does not bound.

## What the diffs actually are

The benchmark needs a commit where the human moved the version **and then changed the code the
move broke**. That is the correct answer Sync's output would be scored against. A commit that
moves a pinned string and nothing else is not a migration — it either compiled by luck or broke
silently, and as a label it asserts that the right response to a breaking release is to touch no
call site.

| Shape | Commits |
|---|---:|
| Touch a line matching `api_version` | 89 |
| — of those, the pin and nothing else | 30 |
| — of those, the pin and some other line | 59 |
| Unsignalled **and** reaching a source file that is not dependency bookkeeping | 20 |

Twenty is the optimistic upper bound, and it does not survive reading. Narrowing to commits with
no agent signal, no agent tooling, a pin line, a source-file change that is not a lockfile, and
five files or fewer — so the migration could plausibly *be* the commit rather than be buried in
one — leaves **five**. All five were read by hand:

- **A revert.** `apiVersion` moved *backwards*, from `2026-05-27.dahlia` to `2024-06-20`, to
  unblock `tsc`, because — in the committer's own words — "the 2026 bump shipped without
  upgrading the stripe SDK". The correct answer this commit encodes is *undo the last bump*.
- **A republication fix.** A dynamic `Stripe.API_VERSION` replaced with a literal because npm
  republished a tarball under the same version. No call site changed.
- **An addition.** A pin added where none existed, alongside an unrelated metadata field.
- **A documentation entry.** The matching lines are prose in a `DEVLOG.md` describing version
  drift. The code change is unrelated logging and typing.
- **A typo repair.** `2025-06-24.dahlia` corrected to `2026-06-24.dahlia` — a wrong year, not a
  release boundary.

**Zero of the five is a migration across a breaking release.**

### The strongest candidate, read in full

The best case in the cohort deserves to be shown rather than summarised. Its subject is
literally what the benchmark is looking for — *"Upgrade stripe api version to 2026-06-24.dahlia
and resolve card funding bugs"* — it is unsignalled, it touches ten files, and its body claims
the upgrade was applied "across all session creation, status checking, polling, verification, and
stuck reconciliation endpoints".

What it contains is `const STRIPE_API_VERSION = "2026-03-25.dahlia"` replaced with
`"2026-06-24.dahlia"`, nine times, in nine files. The only other change is a CSS offset and a
height in an unrelated component.

Nine copies of one string is what "upgraded across all endpoints" means here. There is no call
site adaptation to score against, and a harness would record this commit as a labelled migration
because every automatable signal says it is one.

It also names `2026-03-25.dahlia`, a fourth dated version the count could not observe, which
bounds the count's version list rather than its method: the three dates came from a gitignored
cache and were never claimed to be complete.

## The pin denominator is roughly half what it looks like

The count reports 23,926 files carrying a Stripe API version pin, and flags that this counts
files rather than repositories. There is a second correction it could not have made without
reading the files.

The TypeScript query is `"apiVersion: '20" language:typescript`. **`apiVersion` is also the AWS
SDK's client option.** Reading all 100 files on the first page:

| Content | Files |
|---|---:|
| Mentions Stripe | 50 |
| Mentions AWS | 34 |
| Neither — Sanity, and others | 16 |

So the pin cohort's Stripe half is around 50% on this page, and the healthy-looking repositories
the count cites as evidence of a better population include `node-athena`,
`step-functions-draw.io` and `gatsby-source-s3-image`, which do not consume Stripe at all. This
does not change the count's verdict on sample size — half of 23,926 is still not a handful — but
any figure derived from that number needs halving before it is quoted.

## Does a healthier cohort exist, and is it reachable

Two questions, and they have different answers.

**Reachable by commit search: no.** For the ten highest-starred Stripe-pinning repositories on
the pin page, `repo:{owner}/{name} apiVersion` returns **zero hits in nine of ten** and one in
the tenth. Commit search matches messages, and an established repository's migration does not
announce itself in a subject line. This is the count's own finding — *"the population that
happened to announce itself"* — measured from the other end.

**Reachable by path: yes, and it is what shows the population is not there.** The commits API
filters by path, so the full history of each pinned file is retrievable without any search. It
worked for ten of ten repositories, and this is what it returned:

| Repository | Stars | Commits touching the pinned file, all time |
|---|---:|---:|
| `Kanba-co/kanba` | 633 | 1 |
| `nizzyabi/nizzy-starter` | 210 | 4 |
| `samarbadriddin0v/google-drive-clone` | 104 | 2 |
| `RubricLab/maige` | 103 | 7 |
| `brendansudol/punchlines-ai` | 61 | 2 |
| `drivly/ai` | 38 | 1 |
| `grepsoft/gatelessparking` | 35 | 1 |
| `ruxin23/ai-saas` | 26 | 2 |
| `un/srm` | 21 | 3 |
| `Hombre2014/Genius` | 20 | 1 |

Twenty-four commits across ten repositories over their entire lifetimes, and their subjects are
`start`, `Stripe integration`, `added clerk, stripe and resend integration`, `feat(auth): added
stripe to better-auth`, `misc tidy`. They are the commit that *introduced* Stripe, plus
incidental edits. Not one is a migration across a version boundary.

**That is the deeper finding, and it is not a search problem.** Pinning is what Stripe's
versioning is for: a repository pins once and can sit on that version indefinitely, and these
repositories do. The population of real migrations by established consumers is small because
migrating is rare, not because it is hard to find. A better search would not produce a cohort
that does not exist.

## Verdict

**No.** Mined Stripe migrations cannot serve as ground truth for binding precision and recall.

Two independent reasons, either sufficient:

1. **The findable cohort is agent-authored.** 63% carry a machine authorship signal outright,
   and the unsignalled remainder cannot be assumed human. Scoring Sync against it would measure
   agreement with other coding agents, and binding precision and recall — the two axes the
   benchmark specification calls the ones that matter most — would rest on a reference whose
   provenance is another model's output. That is the circularity the specification was avoiding
   when it declined to use Sync's own corpus.

2. **Almost none of it is a migration.** Zero of five hand-read candidates, and zero of
   twenty-four commits touching the pinned file across ten established repositories. The
   artifact the benchmark needs — a version moved and the call sites it broke repaired in the
   same commit — is not in the population at either end of it.

The second reason is the one that closes the question. Authorship might be fixable with better
filters; the absence of migrations is not, because a filter cannot produce what nobody wrote.

### The three weaknesses, against what was read

The benchmark specification named three in advance. Reading the commits sharpened all three.

**Survivorship.** The specification expected successful migrations to be over-represented. What
the reading found is that neither cohort migrates: the bump cohort bumps a string, and the pin
cohort pins once and stops. Survivorship is not the bias that matters here — the absence of the
event is.

**The human is not always right.** The count anticipated an incomplete migration later fixed.
The reading found something worse and more common: a commit that *reverts* a version bump to
unblock the compiler, in a repository where an agent had bumped a version without upgrading the
SDK. As a label, that patch teaches the exact opposite of the correct answer.

**Commit granularity.** The specification asked for bundled migrations to be excluded and warned
that excluding them biases toward simple ones. In this cohort the bias is total: after excluding
bundles, what remains is not simple migrations but string replacements, and the strongest
unbundled candidate is nine copies of one literal.

## Recommendation

Take the fallback the benchmark specification already names — **synthetic mutation of real
repositories, at the cost of realism** — and take it knowing what it costs.

The trade it makes is now better understood than when it was written as a fallback. A synthetic
mutation is a change somebody chose, so it cannot demonstrate that Sync catches what real
vendors really ship. What the reading establishes is that the mined alternative does not
demonstrate that either: it would score Sync against string replacements written by agents. Real
provenance was the mined approach's only advantage, and it does not have it.

Two properties make synthetic mutation the stronger option on its own terms, not merely the
remaining one. The label is exact — the mutation is known, so a missed call site is
unambiguously a miss and precision needs no adjudication. And the repository is real: the
mutation is applied to code somebody wrote for their own reasons, which is where the binding
problem actually lives.

The cost to state alongside any score it produces: the distribution of mutations is chosen by
whoever writes the generator, so the resulting precision and recall describe performance against
that distribution and not against Stripe's release history. That belongs beside the number in
the same sentence, the way the sample size does.

**What is not recommended:** building the mining harness for a later re-check. The reading found
no population to mine, and a harness kept warm against a cohort that does not exist is
infrastructure with a maintenance cost and no output.

## What could not be measured, and why

- **Private repositories.** Invisible throughout. Everything here describes public GitHub.
- **Migrations whose message names no version.** Unreachable by commit search by construction.
  The path route reaches them per repository, and covering the pin cohort that way is one API
  call per repository per file — affordable, and the reading above spent ten of them to
  establish that the commits it finds are integrations rather than migrations.
- **Whether the pattern holds outside 2026.** The observable dated versions came from a
  gitignored cache and one commit in the sample names a fourth the cache did not hold. The
  reading of the pin cohort is the better evidence on this and it is not version-scoped: those
  repositories span 2017 to 2025 and do not migrate.
- **Whether authorship is changing over time.** The trailers name model versions spanning
  several releases, which suggests a moving population rather than a snapshot, but the sample is
  one window and cannot show a trend.
- **Vendors other than Stripe.** Stripe's pinning discipline is unusually strong, which is
  exactly what makes migrations rare in it. A vendor that breaks consumers without a pin might
  have a real migration population. Nothing here measures that, and it is the one question that
  could reopen mining as an approach — for a different vendor, not for this one.
