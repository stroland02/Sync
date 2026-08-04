# system-design-primer and awesome-scalability

Second pass, 2026-08-04. The first pass read both repositories as text from
`raw.githubusercontent.com`. This pass cloned them (`--depth 1`), read the files on disk
including the directories the first pass never opened, ran an HTTP survey over a sample of the
links, and read Sync's own `src/sync/graph/store.py`, `src/sync/api/app.py`,
`src/sync/mcp/tools.py` and `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md`
alongside them so the judgements below are about code rather than about chapter titles.

Clone state at the time of reading: `donnemartin/system-design-primer` at `ae9bbd7`, last
commit 2026-03-20 ("Fix link for UDP vs TCP"); `binhnguyennus/awesome-scalability` at
`c9ca9f2`, last commit 2026-01-04 ("Fix dead links and remove obsolete resources (2026
cleanup)"). Both VERIFIED via `git log -1`.

**Verdict, unchanged in shape from the first pass and strengthened by the evidence:
`donnemartin/system-design-primer` is SKIP as a whole, REFERENCE for three named sections.
`binhnguyennus/awesome-scalability` is REFERENCE, narrow — now six named entries rather than
four, and still nothing that blocks M4.** What changed is the confidence and the reasons. Two
of the first pass's judgements are corrected below, and one entry it never named turned out to
be the best thing in either repository for Sync's idempotence rule.

## 1. What these references actually are

`donnemartin/system-design-primer` is a single README of 1,839 lines that teaches the
vocabulary of large-scale web architecture — DNS, CDN, load balancers, replication, sharding,
caching, queues — and then applies it to eight worked interview problems such as "Design
Pastebin.com" and "Design the Twitter timeline and search" (VERIFIED: heading list, `README.md`
lines 89–353). Its two stated goals are "Learn how to design large-scale systems" and "Prep for
the system design interview", and a large fraction of the document exists only to serve the
second (VERIFIED: `## Motivation` line 12, `## Study guide` line 182, `## Anki flashcards` line
46). It is CC BY 4.0, Copyright 2017 Donne Martin (VERIFIED: `## License`, lines 1832–1839).

What the first pass could not see, because it read only the README: the repository also carries
a `solutions/` directory of 26 Python files, 6 Jupyter notebooks and 16 markdown write-ups
(VERIFIED: `find solutions -name "*.py" | wc -l` and siblings, run this session). Section 5
below is mostly about what is in those files, because it changes how the primer should be
cited.

`binhnguyennus/awesome-scalability` is a curated link list, MIT-licensed, describing itself as
"An updated and organized reading list for illustrating the patterns of scalable, reliable, and
performant large-scale systems" whose "Case studies are taken from battle-tested systems that
serve millions to billions of users" (VERIFIED: `README.md` line 3). It has eleven top-level
sections — Principle (36), Scalability (96), Availability (515), Stability (587), Performance
(608), Intelligence (688), Architecture (828), Interview (877), Organization (900), Talk (941)
— and every leaf is a hyperlink to somebody else's engineering blog post, conference talk, or
paper (VERIFIED: heading line numbers from `grep -n "^## "`). It contains no prose of its own
beyond the headings, so "reading it" means reading other people's articles. It holds 921 unique
URLs (VERIFIED: extracted and deduplicated this session).

## 2. What Sync should take, and where it lands

### The three questions this pass was asked

**Question 1 — the HTTP transport shares one `GraphStore` across requests. What do these
references say about that, and when does it stop being safe?**

They say nothing. That is the finding, and it is worth stating flatly so nobody goes looking
again. In the primer, the string "connection pool" occurs exactly once, at `README.md` line
1417, and it is not about databases: it sits in the TCP section and concerns web-server-to-
memcached connections — "It can be expensive to have a large number of open connections between
web server threads and say, a memcached server. Connection pooling can help in addition to
switching to UDP where applicable" (VERIFIED, quoted verbatim). In awesome-scalability, the
strings "connection pool", "thread safe", "thread-safe" and "concurrency" return **zero
matches** across all 976 lines (VERIFIED: grep run this session). Neither reference has a
chapter on connection lifecycle, on per-request versus shared handles, or on whether a database
handle may be touched by two units of work.

So the answer has to come from Sync's own code, and reading it gives a sharper answer than
either reference would have. The safety of the current arrangement rests on three independent
properties stacked on top of each other, and the note is which one breaks first:

- The connection is opened with `autocommit=True` (`src/sync/graph/store.py:117`), so a read
  issued outside `transaction()` opens no transaction at all. VERIFIED.
- `GraphSurface` is a structural Protocol over four read-only methods — `open_findings`,
  `get_call_site`, `get_vendor_change`, `all_vendor_changes` (`src/sync/mcp/tools.py:49–55`).
  Nothing the transport can reach writes. VERIFIED.
- Every handler in `create_app` is declared `async def` and contains **no `await` anywhere**
  (`src/sync/api/app.py:76–149`). A coroutine that never yields runs to completion before the
  event loop schedules another, so in a single-worker process two requests can never be inside
  a psycopg call simultaneously. VERIFIED by reading all five handlers.

The store's own docstring already anticipates the failure mode the references do not:
"psycopg serialises statements on a shared connection, so concurrent callers corrupt nothing --
but they share a transaction as well as a connection, which is a sharper edge than it sounds"
(`store.py:104–107`), and `transaction()` spells out the consequence — "A write issued through
the same store from another thread joins the block whether it means to or not, and is rolled
back with it without raising anything" (`store.py:132–135`). VERIFIED, quoted.

It stops being safe at any one of these, in roughly this order of likelihood:

1. **The first `await` placed inside a handler between two surface calls.** That reintroduces
   interleaving on one connection. Today no handler awaits; this is one line of maintenance
   away.
2. **Changing a handler from `async def` to `def`.** Starlette runs a synchronous handler in a
   threadpool, so two threads then share one connection. psycopg3 serialises statements, so
   nothing corrupts — but `store.py:130–136` is explicit that they would also share any
   `transaction()` block, silently.
3. **The first write route, or any route that reaches something calling `transaction()`.** The
   read-only property is doing more work than it looks, and it is not enforced anywhere in
   `app.py` — it is a property of which methods `GraphSurface` happens to expose.

INFERENCE, from reading `app.py` rather than from either reference: connection sharing is not
what will bite first. `_SCAN_LIMIT = 10_000` (`app.py:32`) means both `overview` (line 80) and
`finding_detail` (line 113) perform a full page scan of up to ten thousand rows per request,
synchronously, on the event loop. That is a self-imposed concurrency ceiling of one request at
a time, and it arrives long before anything about the connection matters. The comment at
`app.py:29–32` already says the intended remedy — "past this, the console pages instead."

**Question 2 — what do these references say about idempotency that Sync's rule does not already
capture?**

The primer says nothing usable. The string "idempotent" appears exactly once in 1,839 lines, at
`README.md` line 1384, and it is a **column header in the HTTP verb table**, footnoted "*Can be
called many times without different outcomes" (VERIFIED, quoted). There is no material on
pipeline stages, natural keys, conflict clauses, upserts, deduplication, grain, backfill,
lineage, or dead-letter queues — all of those greps return nothing but that one table row.
awesome-scalability is nearly as empty: zero matches for `idempot`, `natural key`, `upsert`,
`grain` or `backfill`, and exactly one for `lineage` ("Building and Scaling Data Lineage at
Netflix", line 736 — an entry the first pass did not name, and the only thing in either list
adjacent to Sync's rule 4).

But awesome-scalability carries one entry that answers the question completely, and the first
pass missed it: **"Life Beyond Distributed Transactions" at `README.md` line 73**, under
*Principle*. This is Pat Helland's CIDR 2007 position paper. The ACM Queue link in the list
returns 403 to an automated fetch; I retrieved the CIDR PDF and extracted its text, so the
quotations below are VERIFIED from the primary source read this session.

Three things it gives Sync that the current rule does not have:

- **"Substantive change" as the thing idempotence is defined against.** Helland: "The
  processing of a message is idempotent if a subsequent execution of the processing does not
  perform a substantive change to the entity. This is an amorphous definition which leaves open
  to the application the specification of what is and what is not substantive." Sync already
  implements exactly this distinction and has no word for it. `record_observed_shape`
  (`store.py:589–642`) adds `sample_count` for a source in `TRAFFIC_SOURCES` and takes
  `GREATEST` otherwise, and its docstring concedes the point in Sync's own vocabulary:
  "`sample_count` is the one of them whose merge is not idempotent" (`store.py:606`). Under
  Helland's definition it is idempotent — a re-ingest of a synthetic row makes no substantive
  change, and a fresh traffic observation is a different message rather than the same one
  twice.

  This matters because it exposes a real defect in the *written* rule, not in the code. The
  pipeline-discipline spec's verification bullet says: "run INDEX twice against the same
  fixture repository, assert the row count and every row identity are unchanged"
  (`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md:214–215`, VERIFIED). Applied
  to `observed_shape` under a traffic source, that assertion fails by construction. The
  spec is stricter than the behaviour the code is right to have. Adopting Helland's word is a
  documentation fix: the assertion should be that no *substantive* column changes, with each
  table naming which of its columns are substantive.

- **Reordering, not merely repetition.** Helland: "we see scale-agnostic applications are
  evolving to support idempotent processing of all application-visible messaging. This implies
  reordering in message delivery, too." Sync's rule 2 says a stage "converges on the same rows"
  and says nothing about arrival order — yet the code already handles order in three places,
  each with a docstring explaining why: `first_seen = LEAST(...)` / `last_seen = GREATEST(...)`
  at `store.py:635–636` and `store.py:676–677`, and the COALESCE-by-emptiness on `url_template`
  at `store.py:673–675` ("an uncorrelated span writes an empty template, and a later correlated
  one must be able to fill it in without an earlier blank erasing what is already known").
  The implementation is ahead of the rule text. Rule 2 should say "converges regardless of
  arrival order", because that is what three conflict clauses already enforce and a fourth
  author has no way to infer it from the rule as written.

- **"Remembering messages as state", and its cost.** Helland: "the entity must remember they
  have been processed. This knowledge is state. The state accumulates as messages are
  processed." That is precisely `observed_call.spans` — `spans = observed_call.spans ||
  EXCLUDED.spans` (`store.py:670`), whose docstring calls it "idempotence by natural key" and
  notes "There is no counter to double, because every count this table answers is derived from
  the map rather than stored beside it" (`store.py:653–656`). Helland names the general pattern
  and, unlike Sync's docstring, names what it costs: the dedup state grows without bound and
  has to travel with the entity. The `spans` map has no eviction and no bound. INFERENCE: that
  is fine at today's volume and is the first thing to revisit when telemetry ingest grows,
  and it is a better-founded worry than anything in the Scalability section of either list.

A fourth idea from the same paper is worth recording even though nothing acts on it yet.
Helland argues that "the uniquely identified entity is the scope of serializability" and that
"atomic transactions cannot span entities". Sync's `repo_id` is an entity key in exactly this
sense — `replace_call_sites` is scoped to it and its docstring says why ("one customer's scan
must not be able to erase another's rows", `store.py:277–279`). INFERENCE: if the graph ever
has to shard, `repo_id` is the shard key the code has already chosen, and the thing that would
have to go first is any `transaction()` block spanning two of them. That is a ready-made
argument to reach for rather than re-derive.

**Question 3 — the critical path is dominated by the customer's CI run, minutes not
milliseconds. Which of their latency material applies?**

Two sections apply and are named in the next subsection: *Performance vs scalability* and
*Availability in parallel vs in sequence*. Almost everything else in either repository's
latency material is aimed at request-response systems and should be ignored here. Specifically:

- **The latency-numbers table** (`README.md` lines 1600–1637) tops out at "Send packet
  CA->Netherlands->CA 150,000,000 ns / 150 ms" (VERIFIED, quoted). Sync's dominant term is a
  customer CI run measured in minutes. The whole table sits three to four orders of magnitude
  below the thing that decides Sync's latency.
- **Latency vs throughput** (lines 426–436) advises "you should aim for maximal throughput with
  acceptable latency" (VERIFIED). That is a request-response framing. Sync runs one pipeline at
  a time for one operator; there is no throughput to maximise.
- **Back pressure** — see the correction in section 3. The first pass credited it and this pass
  withdraws that.

The genuinely relevant material for a pipeline shaped like Sync's is not in the primer at all;
it is awesome-scalability's **Airflow subsection, lines 195–206**, twelve entries on batch
workflow orchestration, of which **"Auditing Airflow Job Runs at Walmart" (line 204)** is the
closest thing in either repository to what M4's console does — rendering a completed multi-stage
run to an operator after the fact. The first pass named none of these and they are more
M4-relevant than anything it did name. REPORTED: I have not fetched the Walmart article, so this
is a title-level judgement about relevance, not a finding about contents.

### Named entries in awesome-scalability worth an hour

**Spotify Fleet Management, parts 1–3** — `README.md` line 501, under *Distributed
Repositories, Dependencies, and Configurations Management*, linking to
<https://engineering.atspotify.com/2023/5/fleet-management-at-spotify-part-3-fleet-wide-refactoring>.

Still the single most valuable entry in either repository, re-fetched and re-verified this
session. Spotify built the closest public analogue to Sync's `PATCH → VERIFY → PR` tail.
**Fleetshift** runs a Docker image against each target repository's checked-out code and opens
a pull request with whatever the image changed. **Fleetsweep** validates a change before any PR
exists, by creating temporary branches and running the tests across the targeted repos.
An **automerger** merges automatically when checks pass, and Spotify deliberately inverted who
decides: "We invert control on who decides what is automerged, from the repo owner to the
change author." Risky shifts roll out in **cohorts**, reaching the next cohort only once the
previous one shows enough success. **Firewatch** watches after the merge, correlating failed
deployments against automerged changes and deciding whether a cohort is ready to proceed. In
2022 Fleetshift produced over 270,000 pull requests, 77% automerged and 11% merged by hand —
241,000 merged PRs totalling 4.2 million lines changed (all VERIFIED, fetched this session).

Where it lands: Fleetsweep is `static_verify` plus the customer-CI gate, and Spotify reached
independently the conclusion Sync's latency spec states — that verification happens on a
throwaway branch before anything is proposed
(`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md:88`: "The CI wait cannot be
shortened. It can be removed from the user's critical path." VERIFIED). Firewatch is the piece
Sync has no analogue for; `migration_outcome` is where that data would live, and
`set_merge_outcome` (`store.py:557–582`) is already the hook — its docstring says "Merge outcome
is the one measurement that tests the product claim, and a column that silently stays null
destroys it." Cohorts are the answer to the fan-out question below.

**Merging Code in High-velocity Repositories at LinkedIn** — `README.md` line 497. The first
pass named this and admitted it had not read it; this pass fetched it, and the contents
**contradict the use the first pass implied for it**. The list's URL 301s to
<https://www.linkedin.com/blog/engineering/optimization/continuous-integration> (VERIFIED).

LinkedIn **explicitly rejects batching**: batching twenty or more commits means "a single bad
commit could cause unnecessary reruns". Instead they use a "first to the finish" model — an
internal `git submit` CLI runs pre-merge validation, then pushes and rebases on the developer's
behalf, validating multiple commits in parallel and merging them independently without
preserving submission order. Post-merge validation catches "soft conflicts", commits that build
individually but fail together. The one number given: "roughly 5 soft conflicts/year for the
highest-velocity repository at LinkedIn" (VERIFIED, fetched this session).

Where it lands, and why it does not displace Spotify: these solve different shapes. LinkedIn's
problem is *many changes fanning into one repository*; Spotify's is *one change fanning out
across many repositories*. Sync's fan-out is Spotify's shape, so cohorts remain the answer. The
value of the LinkedIn entry is the negative result — do not reach for batching when the fan-in
is into a single repository, because one bad member invalidates the batch.

A small correction to the first pass while we are here: it placed line 497 in the *Scaling
Continuous Integration and Continuous Delivery* subsection. That subsection begins at line 502.
Line 497 is in the *Distributed Repositories* subsection, the same one that ends with Spotify
Fleet Management at line 501 (VERIFIED by reading lines 490–514).

**Reliable Reprocessing and Dead Letter Queues at Uber** — `README.md` line 300. Note that the
list's own link, `https://eng.uber.com/reliable-reprocessing/`, **returns 404** (VERIFIED by
curl this session); the article lives at `https://www.uber.com/blog/reliable-reprocessing/`.

Uber routes a failed message to a retry topic and lets the original consumer commit its offset
immediately, so one failure does not block the batch, and messages that exhaust their retries
land in a dead letter queue. Two details earn the mention. Error classification decides the
route — "network flakiness to be re-attempted, while null pointer exceptions and other code bugs
should go straight into the DLQ", so a failure's *kind* is part of the record. And the DLQ is an
operated surface with three verbs: list, purge, merge-to-reprocess (REPORTED: these quotations
are carried forward from the first pass, which fetched the article; I verified the list entry
and the broken link but did not re-fetch the article this session).

Where it lands: `abandon_reason` and the `abandon` node. The principle is already on the record
— `docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md:136`: "That is a dead-letter
queue, and it must be queryable rather than terminal" (VERIFIED). What Uber adds is the verb
list. M4's console has "list"; "reprocess this abandoned attempt now that the classifier
improved" is the one worth designing for. INFERENCE, cheap: reprocessing is safe precisely
because every stage is idempotent, and `record_migration_outcome`'s `ON CONFLICT (finding_id,
attempt_index) DO NOTHING` (`store.py:546`) means a retried attempt converges rather than
inflating the corpus.

**Life Beyond Distributed Transactions** — `README.md` line 73. Covered at length under
question 2 above. This is the entry to read if only one is read.

**The Calculus of Service Availability** — `README.md` line 70, linking to ACM Queue. NOT
verified; the ACM Queue host returns 403 to automated fetches. Named because it is the Google
SRE treatment of how a service's availability target composes with its dependencies', which is
the same arithmetic as the nine-stage sequential point below, worked properly. Treat as a lead.

**Building and Scaling Data Lineage at Netflix** — `README.md` line 736, the only lineage entry
in the list, and adjacent to Sync's rule 4 ("lineage is a column, not a derivation"). NOT
verified; not fetched. Named so that whoever revisits the rung columns has a starting point.

### The three sections of system-design-primer worth reading, and nothing else

**Performance vs scalability** (`README.md` lines 412–424). Four sentences, one of which is the
most useful sentence in the document for this project: "If you have a **performance** problem,
your system is slow for a single user. If you have a **scalability** problem, your system is
fast for a single user but slow under heavy load." (VERIFIED, quoted verbatim from the clone.)

Where it lands: this is the sentence to cite when someone proposes caching, sharding, queuing,
or a second service. Sync has, and for years will have, only the first kind of problem — one
operator, one Postgres on port 5433, a pipeline whose slowest stage waits on somebody else's
CI. Every technique in both repositories' scalability chapters treats the second kind.
INFERENCE, and the load-bearing one in this note.

**Availability in parallel vs in sequence** (`README.md` lines 557–578). Components in sequence
multiply: `Availability (Total) = Availability (Foo) * Availability (Bar)` (line 566).
Components in parallel compose as `Availability (Total) = 1 - (1 - Availability (Foo)) * (1 -
Availability (Bar))` (line 576). VERIFIED, both quoted from the clone at the stated lines.

Where it lands: Sync's pipeline is nine stages — INDEX, RESOLVE, OBSERVE, SIGNAL, DETECT,
LOCATE, PATCH, VERIFY, PR (VERIFIED: the table at
`docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md:28–38`) — and they are strictly
in sequence. INFERENCE from the verified formula: at 99.9% per stage the pipeline completes
99.1% of the time (0.999^9 ≈ 0.9910); at 99% per stage it completes 91.4%. That is the
arithmetic behind why "dead-letter, never drop" is a rule and not a nicety — at nine sequential
stages, run-level failure is common enough that discarding failures discards a large share of
everything the system produces. This remains the one place where a formula from either
repository produces a number that changes how Sync is built.

**The HTTP verb table** (`README.md` lines 1384–1391), and only as a caution. It is the
primer's entire treatment of idempotence, it concerns HTTP methods rather than pipeline stages,
and its presence is the reason someone might believe the primer has something to say about rule
2. It does not. Five minutes, read so the question stays closed.

## 3. What to skip, and what skipping saves

**Two corrections to the first pass before the skip list.**

*Back pressure is a skip, not an adoption.* The first pass placed the primer's *Asynchronism*
section under "what Sync should take" and landed it on M4's API. Read verbatim from the clone,
the back-pressure paragraph is about queues outgrowing memory: "If queues start to grow
significantly, the queue size can become larger than memory, resulting in cache misses, disk
reads, and even slower performance... Once the queue fills up, clients get a server busy or HTTP
503 status code to try again later" (`README.md` line 1357, VERIFIED). Sync's console has one
client and no queue. There is nothing to bound and no 503 to issue. The idea the first pass was
reaching for — deliver the `tsc`-passed patch before CI finishes, rather than holding a request
open — is real, but it comes from Sync's own latency spec at line 88, not from the primer, and
the primer contains no analogue of it. Little's law appears in this section only as a bare link
in the Source(s) list (line 1367) with no explanation. Cost of adopting: an afternoon
implementing a queue bound for a queue that does not exist.

*The Flexport entry is dead, not merely unverified.* The first pass named "Auto-scaling CI/CD
cluster at Flexport" (`README.md` line 513) as an unfetched lead. `flexport.engineering` does
not resolve at all — curl returns 000 with redirects followed (VERIFIED this session). Strike
the lead rather than carrying it forward.

**All of system-design-primer's interview apparatus.** The study guide (line 182), the eight
system-design questions with solutions (287–352), the six object-oriented design questions
(353–371), the Anki decks (46), and the additional-questions appendix (VERIFIED: distinct
top-level sections). Competently written, and for passing interviews at companies Sync is not.
Cost of adopting: several days, returning nothing to the codebase.

**Everything in the primer between DNS and NoSQL** — DNS (581), CDN (619), load balancer (660),
reverse proxy (730), horizontal scaling (703), replication (526 and 829–872), federation (874),
sharding (895), denormalization (923), consistent hashing, the NoSQL taxonomy (991), and the
five cache-update strategies (1199) (VERIFIED: heading line numbers from the clone). Sync runs one Postgres 16 instance and
serves one operator. Cost of adopting any of it: a second moving part plus its failure modes,
to solve a load problem that does not exist. The specific trap is sharding — those sections are
written for a database under write pressure, and Sync's write volume is documents per day.

**The primer's SQL tuning section, in particular** (`README.md` lines 941–990). Read in full
from the clone this session, and it is entirely MySQL: "MySQL dumps to disk in contiguous
blocks for fast access. Use `CHAR` instead of `VARCHAR` for fixed-length fields", the MySQL
slow query log, and a "Tune the query cache" subsection pointing at MySQL 5.7 documentation
(VERIFIED, quoted). INFERENCE: Postgres has no query cache to tune and the `CHAR`/`VARCHAR`
storage argument does not hold there, so following this against Postgres 16 produces schema
changes that are at best inert. Sync's schema discipline lives in `schema.sql` grain comments
and natural keys, and this section addresses neither.

**The primer's latency-numbers table** (lines 1600–1637). Covered under question 3. A fine
table that will never change a decision here.

**Most of awesome-scalability's Scalability section** (96–514). Distributed caching, locking,
tracing, searching and storage, the NoSQL and time-series subsections, and the whole
Intelligence section (688–827). Two concrete costs. Distributed locking would add Redis or
ZooKeeper and a class of fencing-token bugs to a single-writer pipeline where a Postgres unique
index and an `ON CONFLICT` clause already give the guarantee — a call the repository has already
made (`2026-07-27-sync-pipeline-discipline.md:90`, "every table gets a natural key and an
explicit conflict clause", VERIFIED). Distributed tracing would add a collector and a sampling
policy to observe a pipeline whose every stage already writes a row.

**Availability and Stability, nearly all of it** (515–607). Failover, load balancing,
autoscaling, circuit breakers, bulkheads, throttling, rate limiting. One nuance so nobody
re-derives it: rate limiting genuinely matters to Sync as a *client* of vendor APIs and of the
Anthropic API, but the entries under *Rate Limiting* are about building a limiter to protect a
service you operate, not about obeying somebody else's (REPORTED: this reads entry titles, not
contents). INFERENCE on circuit breakers: one in front of a daily vendor poll is a retry policy
wearing more vocabulary, because there is no live request path to fail fast for.

**Segment's deduplication / exactly-once entry** (`README.md` line 309). Segment deduplicates on
a `messageId` UUID against a per-worker RocksDB store around 1.5 TB, with a nominal four-week
window that the size bound can collapse to under 24 hours under load (REPORTED: quotations
carried from the first pass, which fetched it; I confirmed the URL still resolves 200). Sync has
ruled this out on the record: `2026-07-27-sync-pipeline-discipline.md:193` names "Exactly-once
stream delivery" under *What deliberately does not apply* (VERIFIED). The cost is not the hour;
it is reopening a settled decision with an article whose apparatus exists to serve a volume Sync
does not have. Helland at line 73 is the better read and reaches the opposite, cheaper
conclusion.

**The Interview, Organization, and Talk sections** (877–974). Engineering career frameworks,
levels, scaling decision-making across teams. Sync is one person.

**Nobody should spend a week here.** Anyone tempted should read awesome-scalability's own
*Principle* entries "Avoid Over Engineering" (line 76) and "Scalability Worst Practices" (line
77) — VERIFIED as present at those lines, contents not fetched — and then stop.

## 4. Who should consult this, and what question it answers

**Not M4, for the console itself.** The operator console has one user and no traffic tier, and
neither reference addresses a read-only Starlette API serving a single React client — question 1
above establishes that with greps rather than impressions. Two M4-adjacent questions do have
answers here. *What does an operator need to see about an abandoned attempt?* — the Uber DLQ
entry (list, purge, reprocess; record the failure's kind, not only its existence) and Spotify's
Firewatch (someone must watch after the merge, not only up to it). *What does a console over a
completed multi-stage batch run look like?* — the Airflow subsection at lines 195–206,
particularly the Walmart auditing entry at line 204. Perhaps two hours total, while the Solution
Workflow view is being designed.

**The store's owner, once, for Helland.** Consult `README.md` line 73 when the question is *what
exactly does our idempotence rule assert*. It produces two concrete edits to
`2026-07-27-sync-pipeline-discipline.md`: rule 2 should say "converges regardless of arrival
order", and the verification bullet at lines 214–215 should assert that no *substantive* column
changes rather than that every row is identical, because `observed_shape.sample_count` makes the
current wording false against correct code.

**The remediation pipeline, when the fan-out question arrives.** Consult Spotify Fleet
Management when the question is *the same vendor change affects fifty call sites or fifty
repositories — do we open fifty pull requests at once?* The answer is cohorts: gate each batch on
the previous batch's outcome, and invert who decides what auto-merges. Read the LinkedIn entry
alongside it as the boundary condition: batching is wrong when the fan-in is into one
repository. This belongs with `docs/superpowers/specs/2026-07-27-sync-routing-matrix.md`.

**The latency spec's owner, once, for the sequential-availability arithmetic.** Consult
`README.md` lines 557–578 when the question is *how often does a nine-stage pipeline complete
end to end*. The formula is three lines and the answer changes how seriously you take
abandoned-run capture.

**Nobody, for anything else, until Sync is multi-tenant with a real traffic tier.** INFERENCE,
stated plainly so it is not reopened every milestone: the load-balancing, sharding, caching,
failover, autoscaling and distributed-coordination canon becomes relevant when Sync serves many
customers concurrently from hosted infrastructure. That is at least two milestones out, the
designs will have moved, and re-reading a 2017 primer then costs less than pre-reading it now.

### Suggested update to `.claude/skills/sync-external-resources/SKILL.md`

That skill lists `binhnguyennus/awesome-scalability` as "provisionally M4, possibly SKIP" with
the open question *is a scalability case-study list premature by two milestones … or is there a
specific case study on API versioning at scale, schema evolution, or large-scale codemod worth
reading now?*

The answer, now on primary sources: **REFERENCE, narrow, not M4-blocking.** A grep for
`versioning`, `deprecat` and `schema` across all 976 lines returns **five matches total**, and
not one is about API contract evolution (VERIFIED, run this session): Protobuf schema validation
on a stream at Deliveroo (line 270), S3 versioning for image recovery at Trivago (374), and two
that merely contain Uber's datastore name "Schemaless" (403, 409). The fifth is the closest the
list comes — "API Best Practices: Webhooks, Deprecation, and Design" at Zapier, line 888 — and
it is filed under **Interview**, not under any architecture section, which tells you how the
list's author weighted the topic. There is exactly one entry on large-scale codemod (Spotify,
line 501). The best entry in the list for Sync is not a case study at all but a 2007 position
paper (Helland, line 73), which the first pass missed and which bears directly on the
idempotence rule. `donnemartin/system-design-primer` was not among that skill's nine; if added,
add it as SKIP with three sections carved out, and with the warning in section 5 attached.

## 5. What the source says that the documentation does not

**The primer ships 26 Python files that no test has ever run, and several do not work.** This is
the finding that justified the pass, and it is invisible from the README. The repository has no
test files anywhere (`find . -iname "*test*" -not -path "./.git/*"` returns empty) and no CI:
`.github/` contains a single `PULL_REQUEST_TEMPLATE.md` and no workflows (both VERIFIED this
session). The `solutions/` tree is laid out as executable Python — `__init__.py` in every
package, `if __name__ == '__main__':` entry points, accompanying notebooks — and reads as
runnable reference code. It is not. Defects found by reading four of the files end to end:

- `solutions/system_design/query_cache/query_cache_snippets.py:74` — `node = self.map[query]`,
  but the constructor at line 53 sets `self.lookup`. `Cache.set` raises `AttributeError` on
  every call.
- Same file, lines 61–63 — `node = self.lookup[query]` followed by `if node is None: return
  None`. A missing key raises `KeyError` on line 61, so the guard on 62 is unreachable. The
  method cannot do the thing its docstring describes.
- Same file, line 21 calls `self.memory_cache.set(query, results)` against the signature `def
  set(self, results, query)` on line 67. The arguments are swapped.
- `solutions/system_design/sales_rank/sales_rank_mapreduce.py:24–37` — `quantity` comes from
  `line.split('\t')` and is therefore a string; `reducer` then does `sum(values)` over those
  strings, which raises `TypeError`. The docstring at lines 31–36 asserts sums the code cannot
  produce.
- `solutions/system_design/web_crawler/web_crawler_snippets.py:66` and `:73` — `crawl()` calls
  `extract_max_priority_page()` twice per iteration and the page fetched at line 73 is
  overwritten at line 66 on the next pass. If extraction removes the page from the store, as its
  name says, every other page is silently dropped.
- `solutions/system_design/pastebin/pastebin.py:40` and `sales_rank_mapreduce.py:69,71` — both
  build steps with `self.mr(...)`, an mrjob API removed around mrjob 0.5. These files cannot
  import-and-run against any mrjob a person would install today.

The consequence for Sync is a citation rule, not a bug report. **Cite the primer for names,
definitions and the two formulas. Never cite it for how something is implemented, and never
lift its code.** The prose in the README is peer-reviewed by thousands of readers; the
`solutions/` tree is illustrative pseudocode wearing a `.py` extension, and the repository has
no mechanism that would ever notice. The first pass's SKIP verdict was right for a reason it
did not know.

**awesome-scalability's most recent commit claims a link cleanup that did not happen.** Head is
`c9ca9f2`, 2026-01-04, "Fix dead links and remove obsolete resources (2026 cleanup)" (VERIFIED).
I sampled every fifteenth of the 921 unique URLs — 62 links — and checked each with curl,
following redirects, 25-second timeout. Results: 39 returned 200, 18 returned 403, 3 returned
404, 1 returned 406, and 1 failed to connect at all (VERIFIED, run this session).

The honest reading has two halves. Most of the 403s are bot-blocking rather than death — 13 of
the 18 are `medium.com`, plus one each from `uber.com`, `queue.acm.org`, `engineering.coinbase.com`,
`codeascraft.com`, `blog.twitter.com` and `badoo.com` — and a human with a browser will reach
most of them. But roughly 6% of the sample is hard dead, and the rot is *systematic at the host
level* rather than scattered: every `eng.uber.com` URL tested returned 404 (3 of 3, including
the Uber dead-letter-queue entry at line 300 which is one of this note's own recommendations),
and that hostname appears **33 times** in the file. `medium.com/netflix-techblog` appears 36
times, `yahooeng.tumblr.com` 15, `code.facebook.com` 9, `githubengineering.com` 7 (all VERIFIED
by grep count). `flexport.engineering` does not resolve at all, which kills line 513 outright.
The January cleanup touched none of these.

So the practical instruction is sharper than the first pass's "budget for link rot": for any
entry on `eng.uber.com`, rewrite the URL to `www.uber.com/blog/<slug>/` before trying, and
expect roughly one entry in fifteen to be unrecoverable. This also means the list's *index
value* has decayed faster than its *curation value* — the titles still tell you which company
solved which problem, and finding the article is now a search rather than a click.

**Neither repository has a word to say about the concurrency question a single-operator service
actually faces.** Established under question 1 above: one incidental mention of connection
pooling in the primer's TCP section, zero mentions of pooling, thread safety or concurrency in
awesome-scalability's 976 lines. These are documents about scaling *out*, and the failure mode
Sync's `GraphStore` docstring worries about — two units of work sharing one connection and
therefore one transaction — is a failure mode of scaling *within a process*, which neither
addresses. `store.py:94–146` is better documentation of that hazard than anything in 235 KB of
curated material, which is worth knowing before anyone goes looking again.

**The best idea in either repository for Sync is a 2007 paper, not a case study.** Both
repositories present themselves as collections of modern, battle-tested, large-scale practice.
The entry that changes Sync's rule text is Helland's CIDR 2007 position paper at line 73 of the
Principle section — the part of awesome-scalability that is not case studies at all, is
nineteen years old, and is the only place either repository defines idempotence in a way a
pipeline can act on. The "Case studies from systems serving millions to billions of users"
pitch in the README's first line is pointing away from the thing that was worth reading.
