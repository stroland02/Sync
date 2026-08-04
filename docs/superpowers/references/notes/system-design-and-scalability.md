# system-design-primer and awesome-scalability

Audited 2026-08-04 against the primary sources. Both repositories were read directly from
`raw.githubusercontent.com` rather than through any summary of them.

**Verdict: `donnemartin/system-design-primer` is SKIP as a whole, REFERENCE for three named
sections. `binhnguyennus/awesome-scalability` is REFERENCE, narrow — four named entries, none of
which blocks M4.** Neither is load-bearing. Together they are roughly 235 KB of index, and the
part that survives contact with Sync's actual shape is about three hours of reading.

## 1. What these references actually are

`donnemartin/system-design-primer` is a single 110 KB README that teaches the vocabulary of
large-scale web architecture — DNS, CDN, load balancers, replication, sharding, caching,
queues — and then applies it to eight worked interview problems such as "Design Pastebin.com"
and "Design the Twitter timeline and search" (VERIFIED: the file's own heading list, lines
5–1831 of `README.md`). Its two stated goals are "Learn how to design large-scale systems" and
"Prep for the system design interview", and a large fraction of the document — the study guide,
the eight system-design questions, six object-oriented design questions, and Anki flashcard
decks — exists only to serve the second (VERIFIED: `## Motivation`, `## Study guide`, and
`## Anki flashcards` sections). It is CC BY 4.0, Copyright 2017 Donne Martin (VERIFIED:
`## License`, README lines 1831–1840).

`binhnguyennus/awesome-scalability` is a curated link list, MIT-licensed (VERIFIED:
[LICENSE](https://raw.githubusercontent.com/binhnguyennus/awesome-scalability/master/LICENSE)),
describing itself as "An updated and organized reading list for illustrating the patterns of
scalable, reliable, and performant large-scale systems" whose "Case studies are taken from
battle-tested systems that serve millions to billions of users" (VERIFIED: README line 3). It
has eleven top-level sections — Principle, Scalability, Availability, Stability, Performance,
Intelligence, Architecture, Interview, Organization, Talk, Book — and every leaf is a hyperlink
to somebody else's engineering blog post, conference talk, or paper (VERIFIED: `## Content`,
README lines 23–34). It contains no prose of its own beyond the section headings, so "reading
it" means reading several hundred external articles.

## 2. What Sync should take, and where it lands

### The four entries in awesome-scalability that are actually about Sync's problem

**Spotify Fleet Management, parts 1–3** — listed at `README.md` line 501 under *Distributed
Repositories, Dependencies, and Configurations Management*, linking to
<https://engineering.atspotify.com/2023/5/fleet-management-at-spotify-part-3-fleet-wide-refactoring>.

This is the single most valuable thing in either repository, and it is buried in a subsection
whose title gives no hint of it. Spotify built the closest public analogue to Sync's
`PATCH → VERIFY → PR` tail. **Fleetshift** clones each target repository and runs a Docker image
against the checked-out code, commits whatever the image changed, and opens a pull request
against the original repository. **Fleetsweep** validates a change before any PR exists, by
creating a short-lived branch and triggering a build of that branch in CI, then reporting
aggregate results back to the change author. An **automerger** merges the PR automatically when
tests pass, and Spotify deliberately inverted who decides that: "We invert control on who decides
what is automerged, from the repo owner to the change author." Risky shifts roll out in cohorts,
where the change reaches the next cohort only after it applied successfully to enough repositories
in the previous one. **Firewatch** watches after the merge, correlating failed backend deployments
and failed data-pipeline executions against automerged changes and alerting the change owner. In
2022 the system produced over 270,000 pull requests, 77% automerged and 11% merged by hand,
totalling about 4.2 million lines changed (all VERIFIED: fetched the part-3 post this session;
quotations are from it).

Where it lands in Sync: Fleetsweep is `static_verify` plus the customer-CI gate, and Spotify
reached the same conclusion Sync's latency spec states independently — that the CI run is the
verification and it happens on a throwaway branch before anything is proposed
(`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md` line 88: "The CI wait cannot be
shortened. It can be removed from the user's critical path." VERIFIED). Firewatch is the piece
Sync does *not* have an analogue for: it closes the loop after merge, and `migration_outcome` is
where that data would live if Sync ever grows it. The cohort mechanism is the answer to a question
Sync will hit the first time one vendor change fans out across many call sites or many customer
repositories — do not ship all of them at once, gate the next batch on the previous batch's
outcome. INFERENCE: none of this is adoptable as code; it is adoptable as a set of names for
stages Sync already has or will need, which is worth something when arguing about the shape of the
remediation graph.

**Reliable Reprocessing and Dead Letter Queues at Uber** — `README.md` line 300, linking to
<https://www.uber.com/blog/reliable-reprocessing/>.

Uber routes a failed message to a retry topic and lets the original consumer commit its offset
immediately, so one failure does not block the rest of the batch, and messages that exhaust their
retries land in a dead letter queue. Two details earn this a mention. First, error classification
decides the route: "network flakiness to be re-attempted, while null pointer exceptions and other
code bugs should go straight into the DLQ" — a failure's *kind*, not just its existence, is part
of the record. Second, the DLQ is an operated surface with three verbs: listing to view contents,
purging to clear them, and merging to reprocess them (VERIFIED: fetched this session).

Where it lands in Sync: `abandon_reason` and the `abandon` node of the remediation graph. The
repository already states the principle — `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md`
§6 "Dead-letter, never drop", line 136: "That is a dead-letter queue, and it must be queryable
rather than terminal" (VERIFIED). What the Uber post adds is the *operations* list. If M4's
console shows abandoned attempts, "list" is the one Sync has; "reprocess this abandoned attempt
now that the classifier improved" is the one worth designing for, and it is the direct analogue of
merging a DLQ back into the stream. INFERENCE, but a cheap one: an abandoned run whose reason is
now understood is exactly the retry case, and reprocessing it is free because every stage is
idempotent.

**Merging Code in High-velocity Repositories at LinkedIn** (`README.md` line 497) and
**Auto-scaling CI/CD cluster at Flexport** (line 513). These are the two entries in the *Scaling
Continuous Integration and Continuous Delivery* subsection whose titles match Sync's actual
bottleneck — the customer's CI run, minutes not milliseconds. **I could not verify their contents;
I did not fetch either article.** They are named here so that whoever asks "the CI wait dominates
the critical path, what have other people actually done about it" has a starting point rather than
a search. Treat the titles as a hypothesis about relevance, not a finding.

### The three sections of system-design-primer worth reading, and nothing else

**Performance vs scalability** (README lines 412–424). The whole section is four sentences and
one of them is the most useful sentence in the document for this project: "If you have a
**performance** problem, your system is slow for a single user. If you have a **scalability**
problem, your system is fast for a single user but slow under heavy load." (VERIFIED, quoted
verbatim.)

Where it lands: this is the sentence to cite when someone proposes caching, sharding, queuing, or
a second service. Sync has, and for years will have, only the first kind of problem — one
operator, one Postgres, a pipeline whose slowest stage is a subprocess waiting on somebody else's
CI. Every technique in both repositories' scalability chapters treats the second kind. INFERENCE,
and the load-bearing one in this note.

**Availability in parallel vs in sequence** (README lines 557–578). Components in sequence
multiply: `Availability (Total) = Availability (Foo) * Availability (Bar)`. Components in parallel
compose as `1 - (1 - Availability (Foo)) * (1 - Availability (Bar))` (VERIFIED, both formulas
quoted verbatim).

Where it lands: Sync's pipeline is nine stages — INDEX, RESOLVE, OBSERVE, SIGNAL, DETECT, LOCATE,
PATCH, VERIFY, PR — and they are strictly in sequence. INFERENCE from the verified formula: at
99.9% per stage the pipeline completes 99.1% of the time (0.999^9 ≈ 0.9910); at 99% per stage it
completes 91.4% of the time. That is the arithmetic behind why "dead-letter, never drop" is a rule
and not a nicety — at nine sequential stages, run-level failure is common enough that discarding
the failures discards a large share of all information the system produces. This is the one place
where a scalability formula produces a number that changes how Sync is built.

**Asynchronism, specifically back pressure** (README lines 1324–1369). Message queues, task
queues, back pressure, and the pointer to Little's law. The back-pressure paragraph is the
relevant one: bound the queue and reject when full, rather than letting it grow past memory
(VERIFIED).

Where it lands: M4's read-only Starlette API at `src/sync/api/`. INFERENCE: a console watching a
pipeline whose stages take minutes must never hold a request open across a stage; it reads run
state and polls. The primer's framing — the client is told the job's status and is not blocked —
is the correct shape, and it is worth one read precisely because it is the only part of the
asynchronism chapter that applies when there is exactly one client.

## 3. What to skip, and what skipping saves

**All of system-design-primer's interview apparatus.** The study guide, the eight system-design
questions with solutions, the six object-oriented design questions, the Anki decks, and the
"Additional system design interview questions" appendix (VERIFIED: these are distinct top-level
sections of the README). They are competently written and they are for passing interviews at
companies Sync is not. Cost of adopting: several days, returning nothing to the codebase.

**Everything in the primer between DNS and NoSQL.** Domain name system, content delivery network,
load balancer, reverse proxy, horizontal scaling, master-slave and master-master replication,
federation, sharding, denormalization, consistent hashing, the four-way NoSQL taxonomy, and the
five cache-update strategies (VERIFIED: heading list). Sync runs one Postgres 16 instance on port
5433 and serves one operator. Cost of adopting any of it: a second moving part, plus the failure
modes that come with it, to solve a load problem that does not exist. The specific trap is
sharding — the primer's own sharding and federation sections are written for a database under
write pressure, and Sync's write volume is documents per day.

**The primer's SQL tuning section, in particular** (README lines 941–990). It is entirely MySQL:
it recommends `CHAR` over `VARCHAR` on the grounds that "MySQL dumps to disk in contiguous blocks",
cites the MySQL slow query log, and devotes a subsection to tuning the MySQL query cache
(VERIFIED, quoted). INFERENCE: Postgres has no query cache to tune and the `CHAR`/`VARCHAR`
storage argument does not hold there, so following this section against Postgres 16 would produce
schema changes that are at best inert. Sync's schema discipline lives in `schema.sql` grain
comments and natural keys, and this section has nothing to say about either.

**The primer's latency-numbers table** (README lines 1600–1637). The largest number in it is 150
ms for a California–Netherlands round trip (VERIFIED). INFERENCE: Sync's dominant term is the
customer's CI run, measured in minutes, so the entire table sits three to four orders of magnitude
below the thing that actually decides Sync's latency. It is a fine table. It will never change a
decision here.

**Most of awesome-scalability's Scalability section.** Distributed caching, distributed locking,
distributed tracing, distributed searching, distributed storage, the NoSQL and time-series
database subsections, and the whole Intelligence section (Big Data, Distributed Machine Learning)
— VERIFIED as present from the subsection list. Two concrete costs. Distributed locking would add
Redis or ZooKeeper and an entire class of fencing-token bugs to a single-writer pipeline where a
Postgres unique index and an `ON CONFLICT` clause already give the guarantee — and the repository
has already made that call in
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` line 90 ("every table gets a
natural key and an explicit conflict clause", VERIFIED). Distributed tracing would add a
collector and a sampling policy to observe a pipeline whose every stage already writes a row.

**Availability and Stability, nearly all of it.** Failover, load balancing, autoscaling, circuit
breakers, bulkheads, throttling, and the rate-limiting subsection (VERIFIED as present, lines
515–607). One nuance worth stating so nobody re-derives it: rate limiting genuinely matters to
Sync as a *client* of vendor APIs and of the Anthropic API, but all eight entries under *Rate
Limiting* — Cloudflare, Yahoo, Stripe, Allegro, Twilio, Grab, Figma — are about building a limiter
to protect a service you operate, not about obeying somebody else's (VERIFIED from the entry
titles at lines 557–564; I did not fetch the articles, so this reads titles, not contents). They
answer a question Sync does not have. INFERENCE on circuit breakers: a circuit breaker in front of
a daily vendor poll is a retry policy wearing more vocabulary, because there is no live request
path to fail fast for.

**Segment's "Deduplication" / exactly-once-delivery entry** (`README.md` line 309). I fetched it
because it looked adjacent to Sync's idempotence rule. It is not, and the reason matters. Segment
deduplicates on a `messageId` UUID against a per-worker RocksDB store sized to about 1.5 TB, with
a nominal four-week window that the size bound can collapse "to under 24 hours" under load
(VERIFIED, quoted, fetched this session — note the `segment.com` URL now 301s to
`twilio.com`). Sync has already ruled this out on the record:
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md` line 193 names "Exactly-once
stream delivery" under *What deliberately does not apply*, on the grounds that "idempotence plus a
natural key gets the same guarantee (rule 2) against a workload measured in documents per day"
(VERIFIED). The cost of reading it is not the hour; it is the risk of reopening a settled decision
with an article whose entire apparatus exists to serve a volume Sync does not have.

**The Interview, Organization, and Talk sections of awesome-scalability.** Engineering career
frameworks at Dropbox, engineering levels at SoundCloud, scaling decision-making across teams at
LinkedIn (VERIFIED from the entry list, lines 878–905). Sync is one person.

**A structural warning about awesome-scalability that is worth more than most of its entries.**
The list is a bibliography of other people's blogs, and it has aged. The one link I followed from
it had moved host entirely (`segment.com/blog/exactly-once-delivery/` → `twilio.com`, VERIFIED as
a 301 this session), and the list is dense with hostnames belonging to properties that have since
been retired or rebranded — `yahooeng.tumblr.com`, `code.facebook.com`, `githubengineering.com`,
`medium.com/netflix-techblog`, `eng.uber.com` (VERIFIED that these hostnames appear throughout the
file; NOT verified that each specific link is dead, since I fetched only three). Budget for link
rot before planning any reading session against it.

**What is missing from both, which is the finding that decides the verdict.** I grepped
awesome-scalability for the concepts Sync's pipeline discipline is actually built on:
`idempot`, `schema`, `versioning`, `codemod`, `refactor`, `static analys`, `deprecat`, `backfill`,
`exactly.once`, `outbox`, `dead.letter`. Twenty-two lines matched across 125 KB, and almost all of
them are datastore migrations — moving Mongo data at Addepar, MySQL 5.6 to 8.0 at Facebook,
Postgres to MySQL at Uber — not API schema evolution (VERIFIED, grep run this session). There is
**no** entry on idempotent pipeline stages as a discipline, **no** entry on breaking-change
detection in an API contract, and exactly **one** entry on large-scale automated code
modification, which is the Spotify one already named above. Sync's central problems are simply not
what these lists collect. That is the honest answer to "does a scalability case-study list serve
an API-binding engine": mostly no, and specifically no on the parts that make Sync distinctive.

## 4. Who should consult this, and what question it answers

**Not M4.** The operator console has one user and no traffic tier, and neither reference has
anything to say about a read-only Starlette API serving a single React client. The one M4-adjacent
question — *what does an operator need to see about an attempt that was abandoned* — is answered by
the Uber DLQ entry (list, purge, reprocess; and record the failure's kind, not only its existence)
and by Spotify's Firewatch (someone must watch what happened after the merge, not only up to it).
That is perhaps ninety minutes of reading and it should happen while the Solution Workflow view is
being designed, not before.

**The remediation pipeline, when the fan-out question arrives.** Consult Spotify Fleet Management
when the question is *the same vendor change affects fifty call sites or fifty repositories — do we
open fifty pull requests at once?* The answer the post gives is cohorts: gate each batch on the
previous batch's outcome, and invert who decides what auto-merges. This belongs in the same
conversation as `docs/superpowers/specs/2026-07-27-sync-routing-matrix.md`.

**The latency spec's owner, once, for the sequential-availability arithmetic.** Consult
system-design-primer's *Availability in parallel vs in sequence* when the question is *how often
does a nine-stage pipeline complete end to end*. The formula is three lines and the answer changes
how seriously you take abandoned-run capture.

**Nobody, for anything else, until Sync is multi-tenant with a real traffic tier.** INFERENCE, and
stated plainly so the question is not reopened every milestone: the load-balancing, sharding,
caching, failover, autoscaling, and distributed-coordination canon in both repositories becomes
relevant when Sync serves many customers concurrently from hosted infrastructure. That is at least
two milestones out, the designs will have moved by then, and re-reading a 2017 primer at that point
costs less than pre-reading it now costs. Anyone tempted to spend a week here should read
awesome-scalability's own *Principle* entries "Avoid Over Engineering" and "Scalability Worst
Practices" (`README.md` lines 76–77, VERIFIED as present; contents not fetched) and then stop.

### Suggested update to `.claude/skills/sync-external-resources/SKILL.md`

That skill currently lists `binhnguyennus/awesome-scalability` as "provisionally M4, possibly
SKIP" with the open question *is a scalability case-study list premature by two milestones … or is
there a specific case study on API versioning at scale, schema evolution, or large-scale codemod
worth reading now?* (VERIFIED: read the skill this session.)

The answer: **REFERENCE, narrow, and not M4-blocking.** There is no entry on API versioning at
scale and none on schema evolution. There is exactly one on large-scale codemod — Spotify Fleet
Management, `README.md` line 501 — and it is worth an hour when the automated-PR fan-out question
comes up. Three further entries are named above. Everything else in the list is aimed at a scale
Sync will not reach for years. `donnemartin/system-design-primer` was not on that skill's list of
nine; if it is added, it should be added as SKIP with the three named sections carved out.
