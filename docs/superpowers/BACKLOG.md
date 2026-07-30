# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

## Milestone status

Percentages are judgement over measured facts, not a burndown. Each says what it counted. The
milestone names come from
[the design document](specs/2026-07-25-sync-self-maintaining-apis-design.md); the mapping below is
by content, because items were never tagged with a milestone as they landed.

| | Milestone | % | The one sentence that matters |
|---|---|---|---|
| **M0** | Walking skeleton, one real PR | **~90%** | Every component exists; the proof is ~200 commits stale |
| **M1** | Runtime signals, efficiency detector | **~85%** | Built; the dollar estimate is deliberately unbuilt |
| **M2** | Production error detector | **~85%** | Built; never exercised against real telemetry |
| **M3** | Multi-vendor, MCP, plugin SDK | **~95%** | Packaging closed 2026-07-30; nothing structural left |
| **M4** | Hosted control plane (**the front end**) | **0%** | Not started, and has no plan file yet |
| **M5** | Integration layer | **~35%** | Sources exist; the correlation join does not |
| **M6** | Show it, rather than describe it | **0%** | Needs a UI to film |

### M0 — Walking skeleton, one real pull request · ~90%

**Done.** Stripe adapter, TypeScript indexer, vendor-change detector, LangGraph remediation graph and
GitHub forge all ship. The verification path is the part that got hardened most: a push lease that
refuses a tip Sync did not author, refusal to discard any non-Sync commit rather than only one at the
tip, branch deletion on abandonment, a guard catching a patch that edited an installed dependency,
support for a patch that must create a file, dependency-tree discarding, checkpoint serialiser
registration, and the tier cascade.

**Remaining — one item, and it is a decision rather than a build.** `B7`, the acceptance run.
`tests/test_e2e_stripe.py` is `@pytest.mark.e2e` and deselected by `addopts`, so it has not executed
since roughly two hundred commits landed underneath it. It opens a real pull request against a real
repository and spends `xhigh` model time, so it needs the user's go-ahead. **It is also the only
thing that gives three of the five quality axes their first sample** — `migration_outcome` holds 3
rows and **0** carry a `pr_number`.

### M1 — Runtime signals and the efficiency detector · ~85%

**Done.** The span store (`observed_call`), OTLP ingest, correlation behind a `RequestCorrelator`
protocol, loop context on `call_site` as a depth rather than a flag, and the efficiency detector
itself — calls in a loop, absent caching, retry storms via `resend_count`. Efficiency findings state
that a cost is shared across call sites rather than counted once per site.

**Remaining.** The design document says these findings carry a dollar estimate. They do not, and
`detect/efficiency.py` says why in its own docstring: a saving is a call count times a price per
call, and no table here holds a price. That is a data-sourcing decision, not missing code, and
inventing a price would be worse than reporting none.

### M2 — Production error detector · ~85%

**Done.** `status_rate.py` reports a level rather than a bare rate; `observed_drift.py` catches a
response that no longer matches the indexed specification; `observed_shape` stores what was actually
seen. A Sentry source exists, which the design document calls the fastest route to this milestone.

**Remaining.** None of it has run against real telemetry, so the detectors are correct by
construction and unproven in the field. Same root as M0: no real run has happened.

### M3 — Multi-vendor, MCP, and the public plugin SDK · ~95%

**Done.** Twilio as the second adapter — the first real second implementation of
`operation_for_symbol`, which inverted an assumption the symbol map was built around. A Python
language adapter. An MCP vendor adapter. A generated-SDK adapter family with the Stripe symbol map
derived from `x-stableId` rather than URL shape. The conformance kit covering **all five protocols**
against nineteen shipped implementations, with each rule proved able to fail — it has caught itself
three times, most recently certifying its own reference detector.

And the last structural piece: **`sync-core` is now a second distribution.** An adapter author
installs six packages instead of eighty-one, with psycopg, LangGraph, mcp, the Claude Agent SDK and
the tree-sitter grammars all demonstrably absent. CLAUDE.md's first non-negotiable is now true at the
packaging level, not only the import level.

**Remaining.** Publishing `sync-core` anywhere is public and irreversible and is the user's call. The
wheel builds and installs; nobody has uploaded it.

### M4 — Hosted control plane · 0% — **this is where the front end lives**

Nothing started. No plan file exists either: every other milestone got a spec before it got built,
and M4 has only its design-document section.

**Nothing in the engine blocks starting it.** What is missing is data: a dashboard renders findings,
runs and merge outcomes, and today every panel would read zero. `B7` is what changes that.

### M5 — The integration layer · ~35%

**Done.** Sentry and Datadog sources, the signed public change feed with its consumer and cache, the
vendor registry and its tiering, and the deprecations catalogue.

**Remaining.** The correlation join itself — the thing the milestone is actually for. Nothing yet
joins a Sentry spike to a deploy to a vendor change to the call sites affected. That is a build, not
a defect, which is why nothing here is queued.

### M6 — Show it, rather than describe it · 0%

Remotion videography of the product working. Needs a working UI to film, so it sits behind M4.

### Measurement, which cuts across all of them

Two of five quality axes are measured: **binding precision and recall, both 1.0000 at n=26** over a
frozen corpus of 17 pairs across 5 repositories, gated by four floors that have each been proved able
to fire. Merge rate, routing accuracy and cost per merged patch have **never had a sample**.

Most of the `Done` list below is this: the corpus, the binder defects it caught, the rung a finding
carries, and a long family of encoding defects that all shared one shape — a text read that answered
confidently instead of refusing.

---

## Ready

### B7 — The M0 acceptance run has not executed since the pipeline changed underneath it

`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request` is the
milestone's definition of done and it is `@pytest.mark.e2e`, deselected by default, so
nothing in CI or in any worker's gates has exercised it. Since it last ran the pipeline
gained: the tier cascade, the property-omit codemod, a push guard over the discarded-commit
range, branch deletion on abandonment, checkpoint serialiser registration, the
dependency-edit guard, staged-new-file support, and dependency-tree discarding. Every one of
those sits on the acceptance path.

Re-checked cheaply on 2026-07-30 at `bc1afdb` and it is still not obviously broken: the test
collects, and the production graph compiles with the real `StripeAdapter`, `TypeScriptAdapter`,
`TieredRemediator`, `GitHubForge` and a store. It now exposes **ten** nodes rather than the eight
this entry used to claim — `locate`, `prepare`, `patch`, `static_verify`, `push_branch`,
`await_ci`, `replay`, `open_pr`, `report`, `abandon`. Four of those postdate the last acceptance
run, which is the point: the wiring survived, and that establishes nothing about behaviour.

`build_graph` also refuses a store that cannot record a migration outcome, naming the missing
`record_migration_outcome(outcome)` and calling it the single write every benchmark axis reads
from. So the corpus wiring is checked at construction rather than at the end of a run.

**Run it with `-n0`.** `addopts` now carries `-n auto`, which applies to the e2e test too.

**This one is not a worker's to run unattended.** It opens a pull request on a real GitHub
repository and spends `xhigh` model time on the patch agent. It needs a human to decide
when, which is why it is recorded here rather than dispatched.

**Closes when:** one `sync run` produces a CI-green pull request again, or the failure is
recorded with which change broke it.

## In flight


- **B61** — `task_12ccee12fd98`, worktree `sync-solo-b`.
- **B55** — re-dispatched as `task_3746257e4c0a` into `sync-solo-b`. The first attempt
  (`task_e03a2a5bb93f`) produced nothing in 94 minutes and was stood down.

**Workers keep landing in the wrong worktree.** Three times today a worker has written into a tree
its brief did not name, twice into one another worker already held. The brief names the path and
`dispatch.py` picks whichever terminal is free, and nothing ties those two together — so the
assignment is advisory and the terminal's own working directory wins. Assume any tree may hold
someone else's work: stage by explicit path, and check `git status` before any reset.

**Briefs go in a file now, not in the dispatch spec.** Long message bodies are being truncated in
delivery — three briefs today, and B52 received a correction paragraph while the four numbered
answers that followed it in the same message never arrived. Write the brief to
`.claude/<task>-brief.txt` and let the spec carry a short summary and that path.

Entries stay under **Ready** above with their full reasoning until they land, because the reasoning
is what a reviewer needs and duplicating it here would let the two copies drift.

## Done

- **B69** — CLAUDE.md described a gap `aeecde4` had closed. Landed by the coordinator after four
failed dispatches. The stale sentence claimed `git add -u` never stages a new file, so a patch
needing one could not ship. Re-derived rather than taken from the earlier report: `_UNSHIPPED` is
`frozenset({"??", "!!"})` and a staged addition reports `A `, so `shipped_tree` never holds it
aside; and in a scratch repository `git add -u` followed by `git checkout -B` preserved a staged
new file, which the commit then carried. The gap did not vanish so much as change shape, and the
replacement says so: a created file ships only if the agent staged it, an unstaged one fails the
gate, and that staging is deliberately the only route because nothing can separate a module a fix
requires from a byproduct beside it. **The audit of the file's other claims found nothing else
stale** — all seven `ClaudeAgentOptions` fields present with no `output_config` and no
`max_tokens`, both named shas still describing what the text says, yarn genuinely absent while npm
and pnpm resolve, Postgres on 5433, and `python3` resolving to the WindowsApps shim. The HTTP 400
claim for `temperature`/`top_p`/`budget_tokens` was not checked: verifying it costs a model API
call.


- **B70** — the core wheel ships the licence it asserts, and a page worth landing on. Landed
`e249247`. `dist-info/licenses/LICENSE` is present, `METADATA` carries `License-File: LICENSE` and
`Description-Content-Type: text/markdown` with a rendering body, and the six-package install is
unchanged. **The worker declined my instruction not to check in a second copy of the licence, and
measured why:** PEP 639 forbids the parent-directory operator in a `license-files` glob and uv
rejects `../LICENSE` verbatim, so the text must sit under `src/` — which must be the core project
root for the reason B68 documented. A build-time copy is worse still: `src` is a workspace member,
so declaring `license-files` with the file absent makes `uv run` itself fail, and a fresh clone
could not run its own suite. My stated reason for the prohibition was divergence, and a byte-equality
test on every run closes it at zero build cost. Both claims mutation-tested here — diverging the copy
fails `test_the_two_licence_copies_cannot_drift_apart`, removing `license-files` fails
`test_the_built_core_wheel_carries_the_licence_and_a_description`.


- **B49** — the corpus is now a **superset** of what the rule proposes rather than equal to it. The
  four differences were classified before anything moved: one genuine addition
  (`virtual-lab-GetBalance`, filling a response slot nothing occupied) and **three substitutions** —
  and all four were added while none was replaced, so nothing measured was discarded.

  Floors all moved **up**: precision and recall **n=18 to n=27**, falsifiable negatives 5 to 6,
  pairs scored 13 to 17. Symbol map digest unmoved. Byte-identical across two clean databases.

  The rates held at 1.0000 over half again as many labelled positives, which is the part worth more
  than the count — a perfect rate at n=18 and a perfect rate at n=27 are different amounts of
  evidence for the same claim.

- **B48** — operation selection now follows the change's own side. An operation qualifies on
  `args_keys` for a request pair and `response_fields_read` for a response one, through a shared
  `_judged_by` that `hold_back` also calls.

  The diagnosis in one line: **selection was the only clause that never followed the side**, which
  is why response coverage had been a side effect of request coverage.

  The closing condition was met exactly — the rule proposes `GetProductsId` for `virtual-lab`, and
  the specification it writes is *identical in parsed payload* to the pair that had to be
  hand-written: same field `created`, same held-back position. Ten tests cover the symmetry in both
  directions, including that an object argument does **not** qualify an operation for a response
  pair, so it did not swap one blindness for another.

  No floor moved and `benchmark/corpus/` is byte-untouched, which was the constraint: the four
  differences it would propose for the TypeScript repositories were measured into a scratch
  directory and left there. See B49.

- **B47 — the corpus measures Python.** `virtual-lab-GetProductsId-response-property-removed`:
  two labelled positives, both found, no false finding, and one held-back site the detector could
  have fired on and did not.

  **Every floor moved up**, which is the only direction that needs no argument: precision and
  recall n=16 to **n=18**, falsifiable negatives 4 to **5**, pairs scored 12 to **13**, symbol map
  digest unmoved. Byte-identical across two clean databases.

  The question it was sent to answer was whether an honest pair could exist at all. Of 21 call
  sites, **five** bind a result directly — the other sixteen bind through
  `list(...auto_paging_iter())`, a comprehension, a `for` header, or nothing, and are correctly
  unreachable. Three of the five sit on one operation, which is what makes it a *pair* rather than
  merely a reachable site: two targets and one held back, so it contributes a falsifiable negative
  rather than only denominators.

  It also had to restate the gate's own tests, which asserted the old floors — the same lesson as
  the symbol-map re-pin: when a floor moves, everything that records it moves with it. See B48 for
  why the pair had to be written by hand.

- **B44** — a Python repository is pinned and **none of the pairs it would have produced were
  written**. `openbraininstitute/virtual-lab-api`, Apache-2.0, 563 files, digest validating. Twelve
  pair specs unchanged, all four floors clear, symbol map digest unmoved.

  It set out to give Python its first measurement and instead caught the corpus about to certify a
  number about itself. Its rule produced two pairs; both mutated
  `customers = list(client.customers.list().auto_paging_iter())` into an assertion on
  `customers.has_more`, which is an `AttributeError` on a list. Removing `has_more` from that
  response cannot break that code, so the binder was right to record nothing and right to emit
  nothing.

  **It refused to land them rather than lower `RECALL_FLOOR` from 1.0000 to 0.8889 to accommodate
  ground truth it had proved wrong** — the act the gate exists to prevent. Python precision and
  recall stay `null` over `n=0`: unmeasured, not zero. See B47.

- **B46** — the generator now requires the value to **be** the call rather than merely contain it,
  matching both binders. `customers = list(client.customers.list().auto_paging_iter())` no longer
  gets a response guard attached to a name that never held the response.

  **It fixed both languages, and said so up front rather than letting it be discovered.** The brief
  asked whether TypeScript had the same asymmetry; it did, in the same function — the walk climbed
  to the statement and took whatever declarator it held without asking what that declarator's value
  was, so `const customers = Array.from(client.customers.list(...))` carried the identical defect.
  Its argument for one commit: *two grammars, one rule, one mistake — separating them would have
  described the code's layout rather than the change.*

  **The twelve TypeScript pairs survive the stricter rule unchanged.** All four floors clear:
  precision 1.0000 n=16, recall 1.0000 n=16, falsifiable negatives 4, pairs scored 12. So the
  corpus was not carrying mislabelled TypeScript pairs — the defect existed and had not yet been
  exercised there.

  One line from its reasoning worth keeping: a generator that consulted the binder would be scoring
  the binder against its own opinion. The two must agree by construction and not by consultation.

- **B43** — the pair generator can build a Python pair, and the router still cannot codemod one.
  Landed with the corpus untouched: all four floors clear, symbol map digest matching.

  The design question was the task, and it was separated the right way. `language_for` stays in
  `sync.route.templates` answering the router's question — *can a codemod patch this file?* — and
  still returns `None` for `.py`. The generator got its own `_language_for` answering a different
  question — *can I parse and edit this to build a labelled pair?* — which returns `python`. One
  function answering both with one answer was the bug.

  **Both router guards are tested**, which was the closing condition:
  `test_the_router_still_reads_python_as_a_language_it_cannot_codemod` and
  `test_the_codemod_declines_a_python_call_site_by_name`. That regression would have been
  completely silent — a Python finding routed to a tier whose codemod matches nothing, abandoning
  as "the remediator produced no change".

  It also covered hazards it was warned about and one it was not: the response guard occupies no
  new line, so the displaced-label interaction cannot fire; a result nobody binds is `unreachable`
  rather than labelled; a call already passing the field is refused; and the mutated Python still
  parses.

  **Then it found a corrupting defect in its own landed work.** The keyword insertion mirrored the
  TypeScript literal insertion and placed the field first, which is `SyntaxError: positional
  argument follows keyword argument` in Python — and `create(customer_id)` is an ordinary shape the
  corpus candidate writes.

  Worse than a failed mutation, because it would not have failed: **tree-sitter recovers from a
  syntax error and returns a tree**, so the dependency would have been read back out of a file that
  is not Python and the pair labelled affected. A corrupt pair rather than a refused one — the one
  unrecoverable mistake this generator has, since ground truth is what every future score is
  measured against.

  Fixed by writing the break last, and the tests now `ast.parse` the mutated source rather than
  comparing strings, which is the only check that could have caught it. This is the same trap the
  design document already records from the other side: a codemod cannot verify its own work by
  re-parsing, because the parser will not tell you it is wrong.

- **B45** — an unreadable `requirements.txt` now answers "declares nothing" rather than taking the
  run down at adapter selection. Landed with the front-page work. The `pyproject.toml` branch had
  always honoured that promise; the `requirements.txt` branch two lines below read with a bare
  `utf-8` decode.

  Verified across four encodings, two of them outside the brief: UTF-16 `requirements.txt` returns
  `[]` where it used to raise, UTF-8 is unchanged, UTF-16 `pyproject.toml` still works, and a
  latin-1 manifest is also handled — so the fix generalises rather than special-casing the byte
  order mark that found it.

  Worth knowing about the trade: a manifest with one non-UTF-8 byte anywhere now declares
  *nothing*, so a repository with an accented comment loses adapter selection entirely. That is the
  contract the docstring states and the safe direction — a missing binding is recoverable, a wrong
  one spends reviewer trust — but it is a real cost and not a free fix.

- **B42** — the Python blocker moved from the binder to the generator. B38 and B39 are visible in
  the counts: one repository went from zero to five call sites through the `self`-attribute
  receiver, another gained two through the Python spellings the map had lacked.

  **It repeated the search rather than only the measurement**, and the reason is the sharpest thing
  in the report: B37 assembled its seventeen candidates by searching for the shape the *old* binder
  could index, so re-measuring only those would have asked the new binder a question shaped by the
  old one's limits. That found a repository none of the seventeen matched.

  It did not pin it, because `mutate.language_for` returns `None` for `.py` — and it did not fix
  that either, because teaching the generator Python and pinning the repository it unblocks in one
  change is one worker moving both the corpus and the thing measured. That constraint has held all
  day and it applied it without being told. See B43 and B44.

- **B40** — the once-in-eight failure has a name:
  `test_a_database_that_cannot_be_dropped_does_not_fail_the_run`, caught on run 5 of 14 and failing
  in its own setup with `database "sync_test_22000_gw2" does not exist`.

  **A race between two pytest runs, not between two tests.** The sweep is server-wide and drops
  every `sync_test_%` database whose embedded pid is dead; three tests deliberately create databases
  named for a dead pid, because that is the only thing the sweep will consent to drop. That is the
  bait every *other* run's `pytest_configure` eats. Reproduced deterministically — a second run's
  `--collect-only` is enough, because the sweep happens before any test executes.

  Alternatives falsified with evidence rather than dismissed: not connections (the server answers
  "does not exist" *after* a successful connect, where a limit says "too many clients already", and
  the peak-54-of-300 measurement stands), not order dependence inside a run (the sweep runs once in
  the controller before any test), not product code (everything involved is under `tests/`). Load
  widens the window — the red run took 354.96s against 108–122s for the four green ones.

  **Two workers converged on the identical fix independently**: name the bait for a live pid and
  inject a probe that calls it dead, so the `DROP` and the in-use refusal stay real while the
  database is invisible to other runs. The other coordinator's landed first as `bf3356a`, so only
  this one's capture harness and report were taken.

- **B41** — the corpus's second frozen input is pinned. `benchmark/corpus/symbol_map.yaml` records
  a digest beside `repositories.yaml`, the score carries the digest of the map that actually ran,
  and both the scorer and the gate refuse a mismatch. A deleted map now exits 2 naming the pin
  instead of a `FileNotFoundError` from inside the Stripe adapter.

  **The digest covers content, not bytes**, and that distinction was proven both ways rather than
  argued: reserialised with reversed key order and seven-space indent it digests identically; one
  symbol repointed is refused naming both digests. A checkout is its bytes because the indexer
  reads the files it was handed; a map is a mapping, and indentation is how a serialiser felt on
  the day.

  The scorer refuses **before scoring a single pair**, because that is where a wrong number would
  be created and it is indistinguishable from a good one by the time anything reads it.

  Re-pinned by the coordinator in the same act: the worker's pin named a 179-symbol artifact that
  predated B39 and no run could stage, so it refused on every current cache — correctly and
  uselessly. Rebuilt to 272, scored, floors measured unmoved, digest and recording landed together.
  Its own test `test_the_gate_clears_the_score_the_scorer_actually_records` caught the incomplete
  half of that re-pin, which is exactly what its docstring says it is for.

- **B39** — the Stripe symbol map now carries the spelling Python actually writes. 179 symbols to
  **272**, all 93 previously-unreachable operations addressable, `paymentIntents` and
  `payment_intents` both resolving, and every TypeScript resolution unchanged — corpus floors all
  cleared.

  **The spelling was never missing; it was being discarded.** `payment_intents` is the
  specification's own path segment from `/v1/payment_intents`, and `_camel` was converting it and
  throwing the original away. So snake_case is the source and camelCase the derivation — nothing
  was inverted and nothing transformed, which is exactly what the brief forbade.

  Checked against the vendor before code was written: `StripeClient.payment_intents` is declared in
  `stripe/_v1_services.py`, a file whose header reads "File generated from our OpenAPI spec", and 31
  of 34 multi-word segments match letter for letter.

- **B38** — Python binds the client shapes people actually write. `stripe.StripeClient(k)` and
  `self.client...` both resolve now; the bare imported name is unchanged. Landed `4656d92`.

  The guards are the valuable half, and each is **asserted not to bind** rather than left to
  discovery — `notstripe.StripeClient(k)` (the object is checked, never the attribute),
  `config.client = stripe.StripeClient(k)` (only `self`), and a client received as a parameter and
  stored on the instance (nothing statically says a parameter is a Stripe client, and binding it
  would count any attribute assigned from any parameter). All four verified independently here.

  A rule loose enough to match any `x.Something(...)` would have reintroduced false attribution at
  the binding step — the same defect this file was fixed for earlier today, one layer earlier. It
  did not.

- **B37** — no Python repository was pinned, and the negative result is worth more than the pin
  would have been. Seventeen candidates cloned and indexed against the real adapter and the real
  symbol map; the corpus is unchanged, no floor was restated, and the gate is green for the same
  reason it was this morning. What it found is B38 and B39.

  The sharpest line in its report is about today's own work: both Python fixes landed today concern
  what happens *after* a call site is bound, and every limitation it measured concerns whether one
  is bound at all. **A Python corpus existing today would not have exercised either fix** — sixteen
  of the seventeen repositories bind nothing, and the seventeenth binds one call of neither shape.

- **B36** — the first quality gate this project has. `scripts/gate_corpus.py` floors binding
  precision and recall at the recorded 1.0000 over n=16, and it **recomputes both rates from
  `true_positives` and `false_positives` rather than reading the stored value**, so a stale or
  edited number cannot satisfy it.

  It floored two things beyond the brief, both guarding the gate rather than the binder.
  `falsifiable_negatives` at 4: if that count silently returns to zero, precision's false-positive
  term has no candidates again and the precision floor stays green while gating nothing.
  `pairs_scored` at 12: an exclusion regression shrinks both denominators while leaving both rates
  at 1.0000, so the gate would pass over a corpus that had quietly stopped covering a third of
  itself.

  Verified by seeded regression rather than by report — precision to 0.8889, recall to 0.8889,
  negatives to 0, pairs to 8, each exits 1 naming the floor it broke; the clean tree exits 0; a
  missing score file exits 2 rather than passing.

  Recall was floored on an argued judgement, not by default: it moved twice on the day the corpus
  was frozen, both times through deliberate corpus authoring, and a frozen corpus is authored rarely
  and on purpose. Leaving it open would have gated the less important half, since a missed break is
  the failure the product exists to prevent.

- **B30** — a checkout's undecodable files are skipped and **named**, rather than one PNG ending
  the run. The fetcher's own pre-filter is gone, so the corpus scores the vendor's subtree instead
  of a locally transformed copy of it, and both components walk the tree through one shared
  function (`src/sync/benchmark/checkout.py`) so the digest cannot come to cover a set of files the
  score was not taken over.

  **The axes are unchanged, measured rather than argued.** With the tree pre-filtered (0 skipped)
  and with it verbatim (64 skipped): precision 1.0000 n=16, recall 1.0000 n=16, falsifiable
  negatives 4, 12 of 12 pairs — identical. That is the same-criterion prediction confirmed.

  Two `tree_digest` values moved and no pinned commit did. The manifest now records that the
  digest's *coverage* changed on a date and the commits did not, so a future mismatch is not
  misread as a vendor moving a commit.

  All 64 skipped paths are images, fonts or an icon — no legacy-encoded source file among them.
  That is a property of these four repositories rather than a guarantee, which is why they are
  **named and not counted**.

- **B35** — a walrus-bound result is now credited to the call that produced it. Landed with B34's
  work. Verified across `if` and `while`, with the wrapped form (`charge := dict(create(...))`)
  still recording nothing, so B34's fix is not reopened.

  **The brief was wrong and two workers caught it independently.** It said to add
  `named_expression` to the transparent-wrapper set. A wrapper is something a result passes
  *through* on its way to a name further up the tree; the walrus is where the name already is. As a
  wrapper the walk steps over it and climbs to whatever assignment encloses the `if` — a false
  attribution, which is exactly the defect B34 had just removed. B34's worker predicted this from
  the grammar; B35's worker measured it as a silent no-op before writing anything, with all four
  recall tests staying red.

  Also caught: B34's "recording more would be wrong" reasoning is disqualifying for a precision
  task and is the *point* of a recall one. A worker carrying that sentence across unexamined would
  have done nothing at all.

- **B34** — the Python binder no longer credits a call with fields read off whatever wrapped it.
  Landed `a11c3be`, with its report. Two false attributions removed, six correct cases
  byte-identical, and **nothing anywhere records more than it did** — the check that mattered on a
  precision task.

  The wrapper set is `await` and `parenthesized_expression`, and it was derived from
  `tree_sitter_python`'s grammar rather than translated from TypeScript's, because the worker that
  found the defect had verified behaviour and said explicitly it had not verified node names. Every
  rejected form carries its own reason: `boolean_operator` and `conditional_expression` choose
  between two values and only one is the call's; collection literals bind a container; `argument_list`
  *is* the defect. Annotated assignment needed nothing — it is the same node with the annotation as
  a field. See B35 for the one form it declined to add.

- **B33** — the binder now sees fields read off a result the code assigns rather than declares.
  Landed in `67db957`. Recall **0.8000 to 1.0000 at the unchanged n=20**, every response-side miss
  found, and precision held at 1.0000 while its sample grew 16 to 20 — the check that mattered,
  since recall bought by claiming unread fields would have been worse than the defect.

  It also found and fixed an **unbriefed precision bug** its own test caught:
  `const c = wrap(await stripe.charges.create(...))` was crediting `wrap`'s return value to the
  Stripe call. Widening the binding forms without that guard would have doubled false attribution
  rather than fixed anything. And it refused to write under `benchmark/corpus/recorded/` on the
  grounds that recording into the instrument's directory is editing the instrument — a stricter
  reading than the constraint it was given, and the right one.

- **B32** — a pair specification can hold a call site out of the mutation, so precision has
  something it could fail on. Landed in `67db957`. **Falsifiable negatives 0 to 4, and the binder
  declined all four**, which is the first evidence that axis has ever carried. Its own recording
  was taken against a corpus B29 had already replaced; the coordinator rebased and re-measured.

- **B29** — the response half of the corpus now measures something, and it immediately caught a
  production defect. Landed `4a00841`. Two causes, not the one diagnosed: `_result_binding` reading
  only `const`/`let` accounted for 4 of 11 unreachable targets, and the larger cause was the guard
  occupying three lines, which displaced every call below it. Appending the guard to the statement
  it follows removed the interaction rather than trading one failure for another — **zero**
  `displaced-label` exclusions afterwards, where the naive fix would have created more.

  12 pairs scored, none excluded. Precision 1.0000 n=16, **recall 0.8000 n=20** — down from 1.0000
  n=12, and not a regression: all twelve request-side positives are still found and all four misses
  are response-side. See B33.

  The worker declined to fix the defect it found, because the corpus is what measures the fix and
  it was changing the corpus. That judgement is the most valuable thing in the task.

- **B28** — the decision-table row a run routed on now reaches `migration_outcome`. Landed
  `47cca19`, written by the coordinator after its worker went silent with no edits across two
  ticks. The seam is the recorder, not `on_route`, which still has no caller: `_record` already
  receives the state the row lives on. Required rather than defaulted, and the mutation showed
  why — with a default, removing the writer left the jurisdiction test still passing because the
  default equalled what it asserted; required, the same mutation fails it.
- **B31** — diagnosed why binding precision cannot fail and built `falsifiable_negatives` to say
  so in the output. Landed `67ab335`. It corrected the coordinator's evidence: the rung on an
  unaffected label is a literal `mutate.py:190` writes, and `binding.py:223` never reads it, so
  counting it proved nothing. Real cause is `cli.py:1473`. Follow-up is **B32**.

- **B31** — diagnosed and closed; `falsifiable_negatives` reads 0 for all ten pairs and the
  cause is `cli.py:1473`. The follow-up is **B32**, deliberately a different number.
- **B27** — a specimen corpus is frozen and scored: 12 pairs across 4 repositories pinned by commit
  SHA, checkouts materialised into gitignored space, exclusions counted by reason. Landed
  `c6e18a0` after its worker died holding 1091 lines uncommitted; preserved as `4631c01` on the
  worker branch first, then verified and landed.

  **Determinism is measured, not assumed** — two runs byte-identical, which is what the only
  safely-addable tier C gate rested on and nobody had ever tested.

  Two caveats that must travel with the number. Both axes are computed over the **request side
  only**: every `response-property-removed` pair scored 0 affected and 0 findings, with 11 labels
  unreachable. And **precision 1.0 is a constant, not a measurement** — `cli.py:1473` targets
  every same-operation site, so no negative the detector could have fired on exists. Recall 1.0 at
  n=12 is real. See B31.

- **B26** — the conformance kit no longer certifies what it never exercised. `check_vendor_adapter`
  refused nothing when `known_symbol` was `None` or resolved to `None`; `check_remediator` read an
  empty diff as a decline, so a remediator claiming everything and writing nothing passed. Landed
  `f297e47`. The two refusals carry distinct messages, because "you gave me no symbol" and "your
  adapter did not resolve it" are different problems and an author who conflates them edits the
  wrong thing.

  The new rule fails four generated vendors, and the exemption's wording was the hard part. They
  are **not** unable to resolve: `_load_generated` (`registry.py:362`) passes `sources={}` because
  it promises to reach no network, while `_prepare_generated` (`registry.py:319`) passes
  `sources=sources` and is the path a real run takes. The kit is handed the offline one. Its
  staleness test fails in **both** directions — verified by mutation, dropping a vendor and adding
  one that resolves.

  The limit worth remembering: **this suite certifies an adapter shape no customer ever meets.**
  That closes with a staged fixture, not a bug fix.

- **B24** — nineteen shipped implementations are now asserted against the conformance kit, with
  every list derived from the registry rather than restated and a registered implementation that
  has no case failing **by name** rather than being skipped. Landed `52303b6`. No shipped
  implementation failed, and the worker did the more valuable thing: it asked why everything
  passed, and found **two checks that pass without exercising anything** — `check_vendor_adapter`
  certifies an adapter resolving no symbol when `known_symbol` is `None`, and `check_remediator`
  reads an empty diff as a decline. Both confirmed independently. B26 moves those fixes into the
  kit, where outside authors will actually meet them.

- **The flaky database failures were never flaky.** Measured with a sampler through one full
  suite: peak **105** concurrent connections, mean 67.6, against the postgres default ceiling of
  **100** — `-n auto` gives one xdist worker per core and several worktrees run suites at once.
  Over the ceiling the failure is a `psycopg.OperationalError` on connect, landing on whichever
  database-touching test was running, which is why it moved between runs and never reproduced
  under a soak. Both coordinators lost time to it. `fba1f6e` raises the ceiling to 300 and takes
  effect on the next `docker compose up -d`. **The container was recreated and the ceiling is now
  live at 300**, confirmed against the running server.

  Re-measured after the recreate, same machine, same suite:

  | | before | after |
  |---|---|---|
  | result | 1 failed, 13 errors | **1851 passed** |
  | wall clock | 187s | **103s** |
  | peak connections | 105 of 100 | 75 of 300 |
  | sampler connections refused | 16 of 322 | 0 |

  The halved runtime was not expected and is the part worth remembering: exhausting the ceiling
  was costing refused connections and retries throughout the run, not only the visible failures.
  A resource limit read as both a flaky test *and* a slow suite, and neither symptom pointed at it.

  Peak 75 against 300 leaves real headroom, but that was one suite alone. Nobody has yet measured
  the peak with two or three concurrent suites, which is the case that broke the old ceiling.

- **B23** — the conformance kit covers all five protocols. `check_request_correlator` guards a
  privacy boundary rather than a correctness one: an observed path carries a live customer
  identifier and what comes back must address the operation with the vendor's published template.
  Verified by isolating the rule — a correlator returning the raw path is rejected, one returning
  `/v1/charges/{charge}` is accepted. Landed `ec080ee`. Two corrections from that worker, both
  right: the `cli.py` guards are at 1032 and 1102, and they should NOT call the kit, because the
  check needs a resolving request and its identifier that the ingest entry point cannot know.
- **B22** — the shipped `generated-vendors.yaml` is now gated. Its stale-exemption test fired
  against a real event within the hour: `symbols_speakeasy.py` landed, the one pending entry
  stopped describing anything, and the test named both the pair and the remedy. `PENDING_EXTRACTORS`
  is now empty. Landed `e5ee571`.

- **B21** — an existing database now gains columns added after it was created. `apply_schema`
  derives each table's columns from `schema.sql` and issues `ADD COLUMN IF NOT EXISTS` for
  whatever is missing, rather than executing a create-only script. The ALTERs are derived rather
  than hand-maintained, because a hand-kept list reintroduces the original bug the first time
  someone adds a column and forgets the migration. Landed `8a5cd89`, on main at `245382f`.
  Mutation-tested two ways before landing: reverting `apply_schema` to its create-only form fails
  2 of the 6 new tests, and the small SQL parser's documented limit is real — a semicolon inside a
  string literal fails 5 tests loudly rather than mis-parsing in silence.

- The conformance kit now covers four of five protocols, with 29 rules each proved to fire.
  Landed via `fc7090f`. It found the finding-collision defect below.
- `Finding.claim` joins the natural key, so three detectors stop overwriting themselves.
  Landed `c88f240`. Reproducing first revealed a second, unnamed axis in efficiency that a
  key-only fix would have turned from silent loss into a flood of rows.
- The indexer takes the SDK package from the vendor adapter rather than a module constant,
  delivered by the other coordinator's workers; `symbol_root` followed after a scoped-package
  defect that no fixture could see.

- An MCP vendor adapter, M3's last unstarted item. Landed via `28b0772`.
- The status-rate detector, M2's missing half. Landed via `28b0772`. It reports a *level* rather
  than a change, because `cli.py` truncates `observed_call` every run so "earlier" means earlier
  within one ingested window — and said so rather than quoting a trend it does not have.
- A language axis on the binding path. Landed `19834b6`.
- Efficiency findings state that a cost is shared across call sites rather than counted once
  each. Landed `0f980da`.
- The plugin SDK conformance kit and authoring guide. Landed `bb425ba`. Running it against the
  real adapters disproved one of its own rules within a minute.
- The orchestration archive: 147 worker reports, escalations and decisions, exported before the
  terminals were cleaned up. Landed `aef675a`.

- A language axis on the binding path. Landed `19834b6`. Every Twilio map key is snake_case
  (`twilio-python`), so a TypeScript call site could never resolve and failed silently. A
  mismatched spelling now refuses rather than being rewritten into a match. Written by the
  coordinator after the dispatched worker never started.

- The efficiency detector, M1's second half. Landed via `cb0ee3e`. Three findings — calls in a
  loop, uncached repeats, retry storms — and deliberately **no dollar figure**: a call count is
  a fact, a cost needs a price per call no table here holds.
- Loop context on `call_site`. Landed `e8076be`. A depth rather than a flag, counting array
  callbacks alongside loop statements. Written by the coordinator after two dispatched attempts
  had their work destroyed in shared worktrees.

- The M1 span store: `observed_call`, OTLP ingest, and correlation behind a `RequestCorrelator`
  protocol. Landed `ecab0bd`. Grain is one row per trace — per unit of work — which is what lets
  a loop be told apart from ordinary traffic, and what makes ingest idempotent with no counter.
- A second vendor adapter (Twilio), the first real second implementation of
  `operation_for_symbol`. Landed `14394e4`. It inverted the assumption the symbol map was built
  around; the design document now records it.

- Run the suite in parallel, one database per worker. Landed `b590a5e`. Measured **2.18x** on
  an idle 12-core machine, not the 3.0x first reported — that baseline was taken while other
  workers were running. The load-bearing find was `conftest` returning early on a set
  `SYNC_DSN`, which put all twelve workers on one database and deadlocked them on `TRUNCATE`.
- Discard a dependency tree the previous finding doctored. Landed `0fd1623`. Written by the
  coordinator after three dispatches to a worker failed to start.

- Let a patch ship a file it had to create. Landed `aeecde4`, with the install-mark fix at
  `12f9dc9`. Staging is the agent's assertion that the patch needs the file; untracked
  debris stays excluded because neither `git add -u` nor `git diff HEAD` reads it.
- Catch a patch that edited an installed dependency instead of the source. Landed `a891f65`.
  The cheap path guard's reasoning held but its mechanism did not — git cannot answer the
  question either way — so it compares filesystem mtimes instead. Residual recorded as B6.
- Refuse a push that would discard any non-Sync commit, not merely one at the tip. Landed
  `7adeb08`. The worker found a case the brief missed: a stranger's commit the push carries
  forward is not at risk, so refusing it would abandon findings needlessly.

- Register `sync.core` types with LangGraph's checkpoint serialiser. Landed `05c11f5`.
  The warning is read-side only and nothing fell back to pickle — the brief was wrong about
  that and the worker corrected it. Future failure returns a raw dict silently.

- Derive the SDK verb from `spec3.sdk.json`'s `x-stableId` rather than the URL shape.
  Landed `b289a9e`. Coverage unmoved at 105 of 414; one symbol corrected.
- Refuse a push lease against a tip Sync did not author; delete the branch an abandoned
  finding leaves behind. Landed `38ec2c7` and wired at `9627f65`.
- Run the tier cascade and give it the change class the acceptance run hit.

- Take the `hold_back` `turbo` earns and refuse the one `furever` earns. Landed `10f925b`. The
  worker stopped at the decision gate rather than adopting both, which is what caught it: adopting
  both put precision at 0.9615 over n=26, and the single false positive was the newly held-back
  site itself. The label was false, not the binder — two assignments to one name in one scope, so
  the guard's field read is credited to both and the held-back site genuinely depends on the
  removed property. Both rates hold at 1.0000 over n=26, falsifiable negatives 6 to 7, pairs
  unchanged at 17, so the only floor that moved moved upward. Verified by scoring the corpus from a
  fresh database independently, and all four floors were mutation-probed: injecting one false
  positive, one negative short, two false negatives and one dropped pair each fired, naming its own
  axis, with the unmutated control clean. The unsound-selection half is B52.

- Tell whether a decode handler has ever been entered. Landed `e804fe6`. Reads the handler inventory
  out of `src/` by AST and attributes entry by *exception type* using `sys.monitoring`'s
  `EXCEPTION_HANDLED`, so a handler reached by `JSONDecodeError` and the same handler reached by
  `UnicodeDecodeError` are told apart on one line — the distinction line coverage cannot make, which
  is the whole reason the defect class stayed invisible. Measuring the pre-existing suite this way
  found **9 of 14 decode handlers in `src/` had never been entered**; all 14 behave correctly on
  undecodable bytes, so the defect was only that nobody could tell. Nothing in `src/` changed and no
  lint or coverage configuration was weakened. Verified by dropping the driver for a *co-caught*
  handler — the arm a line-coverage check would still call covered — and watching the gate name
  `sync/signals/intake.py:275` exactly; a bogus driver naming a handler not in `src/` also fired.
  Two leave-behinds became B53; the 35 unhandled text decodes still need per-site triage.

- Decline a non-UTF-8 `package.json` instead of crashing on it. Landed `bdabe9c`, with the driver
  it omitted at `83825f6`. The worker measured two crash shapes rather than one — a UTF-16 manifest
  and a cp1252 `author` field failing on byte `0xe9`, the legacy-encoding case CLAUDE.md predicts —
  and both decline after. It also found B52's red suite and proved the five failures predate its own
  change by stashing its files at clean `34789db`, which is why that commit did not land with it.

  **What it missed is the more useful record.** Its change widened a guard to catch
  `UnicodeDecodeError`, which adds a row to `test_decode_handlers.py`'s AST inventory, and it did not
  register a driver — so `test_every_decode_handler_has_been_entered` failed naming
  `sync/index/typescript.py:201`, one hour after that gate landed. The worker correctly attributed
  the five failures it found to another commit and did not notice a sixth was its own. Proving the
  five were not its fault is not the same as proving nothing was. The driver was written here and
  probed by reverting the fix: the driver's own test then raises `UnicodeDecodeError` at
  `typescript.py:200`, so it genuinely enters the arm rather than passing beside it.

  Left behind and now B54: a BOM'd manifest, which decodes fine and defeats four readers instead.

- Refuse a hold-back whose site shares a scope and a result name with a target. Landed `9812313`,
  with the five callers `hold_back`'s new required `root` broke fixed at `0dfd09f`. A fresh
  generation now leaves `furever-PostPaymentIntents-response` without the unsound hold_back, which
  was the deliverable, and the four figures are unchanged: precision 1.0000 n=26, recall 1.0000
  n=26, falsifiable negatives 7, pairs scored 17, `Every floor cleared.`

  Probed in both directions, because a clause that refuses everything is as wrong as one that
  refuses nothing. Disabling the refusal fails `test_a_site_sharing_a_scope_and_a_name_with_a_target_is_refused`;
  dropping the path out of the scope identity — so two files holding the same text compare equal —
  fails `test_sites_in_different_files_are_still_held_back`, which is the case the docstring argues
  for. Regenerating the whole set changes one other file, and only its hand-written commentary:
  zero non-comment lines, `hold_back` key intact.

  **The worker did not land this itself.** It went silent for 53 minutes across two messages, and
  something reset its tree onto a stale main and orphaned `34789db` — 300 insertions reachable from
  no branch. Caught within a minute and preserved as `unreviewed/b52-hold-back-scope`, then
  finished here. Two habits earned from that: stage by explicit path, and run
  `git log --oneline main..HEAD` before any `git reset --hard`.

- Read a customer's manifest as `utf-8-sig`, so a byte-order mark stops changing the answer. Landed
  `9352dbe`. **Seven sites, not the four the brief named** — the brief counted `sync/index/` and the
  worker found `sync/signals/intake.py` reads the same three files for the intake report, correctly
  widened the scope, and said why. The worst instance is the one it added: intake *reported* a
  dependency called `﻿stripe` with an empty `unreadable` beside it, answering a wrong fact
  rather than an absence.

  The claim worth checking was that `utf-8-sig` narrows rather than decodes leniently, since a
  lenient decode would have made every unreadable manifest "readable" and turned the whole family of
  defects into silent mojibake. Verified here: BOM'd manifests now resolve to `stripe`, and UTF-16
  still refuses with `unreadable` set, on both `package.json` and `requirements.txt`.

  Landing it conflicted in three files, all of them "keep both halves" rather than a real
  disagreement: the worker's base predated B53's widened `except`, so `typescript.py` wanted its
  `utf-8-sig` read *and* main's `UnicodeDecodeError` clause. Its report said B53's fix was missing
  from `origin/main`; that was its stale base showing, not origin — `bdabe9c` is in origin's
  ancestry and the clause is there at line 201.

- Let the tokenizer decide a source file's encoding. Landed `b3fe71b`. **The worker refused the fix
  the brief prescribed and was right to.** The brief said `utf-8-sig`; it passed the file's *bytes*
  to `ast.parse` instead, on the argument the method's own docstring already made — deciding a
  file's encoding is part of parsing Python, so choosing one at the read bypasses the very authority
  the gate defers to. `utf-8-sig` fixes a byte-order mark and still fails a file that declares
  `latin-1` under PEP 263; bytes fixes both. Measured against `py_compile` over seven files: bytes
  agrees on all seven, the old `utf-8` read disagreed on two.

  Verified here across six shapes — valid, BOM'd, declared latin-1, undeclared non-UTF-8, UTF-16,
  and a real syntax error — with the gate and `py_compile` agreeing on every one, and the gate still
  rejecting two, so it discriminates rather than passing everything. Reverting the read to `utf-8`
  fails three tests including the property test that compares the two file by file.

  It also removed a clause and its driver rather than re-anchoring them: once the source is bytes,
  `UnicodeDecodeError` is unreachable because it is a `ValueError` subclass and a UTF-16 file raises
  `ValueError: source code string cannot contain null bytes` before the tokenizer. Deleting a driver
  is the right move when the handler is genuinely gone; the assertion moved to
  `tests/test_python_index.py` rather than disappearing.

- Skip and name a `.ts` file that does not decode. Landed `2b2c29b`. The read used
  `errors="replace"` and fed the result to the literal indexer, where `operation_id` *is* the
  literal's value. **The phantom is the finding**: `.ts` is MPEG transport stream as well as
  TypeScript, so under leniency a binary file parsed into a call site. Reproduced here — a binary
  `.ts` carrying an embedded literal yielded `vendor=anthropic operation_id='claude-3-opus'
  path=video.ts`, and zero after the fix. My first probe found no phantom because random bytes
  happen to contain no vendor prefix; the anecdote needed a matching literal to show, which is
  worth remembering before dismissing one.

  The worker priced its own change rather than hiding it: a valid `.ts` in a legacy encoding holds
  literals leniency recovered and this no longer indexes, and telling that file from a binary
  cheaply is impossible. `read_checkout` had already argued the same and chosen the same way.

- Adapter selection stops blaming the repository for a binding we never declared. Landed `7290bc6`.
  The load-bearing finding was that the old message was **false**, not merely vague: four of six
  registered vendors are served by `GeneratedSpecAdapter` and declare no `sdk_bindings`, so a
  repository genuinely importing `@anthropic-ai/sdk` was told its own manifest was at fault.
  Verified both branches here — an undecodable manifest now says so and names the byte, a clean
  manifest says `declares 1 dependency and 'stripe' is not one of them`.

  It reached main the hard way. The worker wrote into the *other coordinator's* worktree and
  committed onto their branch, 86 commits behind main, re-fixing a defect B53 had already landed.
  Preserved as `unreviewed/b55-decline-reason`, then cherry-picked with five conflict hunks —
  every one resolved as "keep both halves", its reason-reporting over main's newer encodings — and
  five `DRIVERS` keys re-anchored from what the gate reported.

- Let Stripe's symbol map skip a malformed path item, as Twilio's already does. Landed `4c13681`.
  Stripe reached `.get` on whatever `paths` held, so one malformed entry cost the **entire** map —
  every call site for the vendor unresolved for one bad key — while Twilio skipped the path and
  built the rest. Verified across four shapes (null, list, string, number): the two now agree on
  all four, a well-formed document still yields its entries, and a mixed document keeps its good
  one. The pinned symbol-map digest is unchanged at `5f71dcd3bec1302c` and the corpus gate clears,
  which was the constraint that could have made this a much larger change.

  **The verdict was already in the repository.** `tests/test_symbol_map_declines.py` had recorded
  this exact drift and said the raise was the worse answer, because a path key names which document
  is bad and a type name does not. The worker inverted that test from asserting disagreement to
  asserting agreement, keeping it as a comparison because agreement is the property and the two
  halves can only drift again by one changing alone.

- The indexer read the customer's code more loosely than the vendor's. Landed `49a4a09`. Four copies
  of one node reader existed: the two over a vendor's SDK decoded strictly, the two over the
  customer's repository passed `errors="replace"`. **The measurement is the finding** — leniency
  recorded `response_fields_read` of `['st']` for a field spelled with an a-circumflex, truncated at
  the bad byte rather than marked, so the graph carried a dependency on a field that does not exist,
  which `ObservedDriftDetector` reads and `PropertyOmitRemediator` patches against.

  Landing it needed three corrections. It committed onto the other coordinator's branch 96 commits
  behind main (preserved as `unreviewed/b58-strict-node-decode`); it duplicated B57's `cli.py` fix,
  so main's landed version was kept with B58's two measured consequences grafted into the docstring;
  and it added two decode handlers without drivers, which the gate caught. Writing those drivers,
  the control caught the coordinator twice — first a driver with no manifest, so `index()` returned
  `[]` regardless of encoding and the assertion passed for the wrong reason, then a wrong call shape.
  Both are the exact failure every brief here warns about.

- Let a run say how much of the repository it could not read. Landed `a7c1057`. A run's entire
  report was `N finding(s)`, identical whether it read the whole repository or a third of it, so
  `0 finding(s)` over a tree of legacy-encoded sources was indistinguishable from one that
  genuinely calls nothing. The block prints **above** the finding count, because a reader who sees
  the number first has already drawn a conclusion from it, and prints nothing at all when
  everything was read — a heading that fires every run is one the next reader learns to skip.

  The worker took a tuple-return over an optional out-parameter despite nine mechanical call-site
  edits, on the grounds that an omittable channel leaves the coverage report something a caller can
  silently drop, which is the exact failure being closed. It also noted the benchmark harness has
  printed a counted block of unread paths since a PNG first ended a corpus run, so the run path was
  the half that had never caught up.

  Two things from its report did not hold on verification. It said the indexers still decode with
  `errors="replace"` — every occurrence left in those files is a docstring explaining the removal.
  And it reported two suite skips; only one reproduced here. The conclusion it drew was right for a
  different reason, and that reason is B61.

- Count the language indexers' skips in a run's coverage figure. Landed `116d1f6`. B60's figure
  counted only the literal pass over `*.ts`, while both indexers walk every source file and recorded
  their skips in `self._undecodable` where nothing read it. **Structurally blind, not merely
  partial:** over a Python tree with one PEP 263 cp1252 module the adapter had `['src/legacy.py']`,
  the literal pass had `[]`, and the run reported it could not read *zero* paths having skipped a
  module the interpreter runs fine.

  The two reports overlap on a TypeScript tree, so the worker unioned rather than summed them —
  "an over-count is its own wrong number, and the one a reader trusts for being larger". Read
  through `getattr` so the protocol is untouched; verified here that an adapter lacking the member
  returns `[]` and breaks nothing, that a clean repository still reports none, and that a latin-1
  module now appears. It also corrected two docstrings that earlier tasks had falsified.

- Key the decode-handler drivers by scope rather than by line. Landed `229a242`. The positional key
  cost five re-anchorings in one run, none of them a defect in `src/`, and the docstring justifying
  it claimed no stable identity existed — measured false: 18 handlers, 18 distinct
  `path::scope::caught` keys, zero collisions. Verified by the probe that matters: inserting a
  comment above a decode handler, the exact edit that broke keys five times, leaves all 25 tests
  green; removing a driver still fails and now names
  `sync/signals/intake.py::_read_npm::JSONDecodeError+UnicodeDecodeError`. The line survives in the
  failure message while leaving the key, which is the split that makes both properties hold.

  **Two agents worked this in one worktree and both errors were the coordinator's.** The original
  was stood down on the evidence that its assigned tree was clean; it had never been in that tree.
  The all-worktree scan is now the only liveness check worth running.

- Retract ghost call sites without destroying findings. Landed `bb93176`, second attempt. The
  first removed the ghost and the `ON DELETE CASCADE` removed the finding with it; this one holds
  both properties at once by **retracting rather than deleting**. `call_site` gains `retracted_at`,
  its grain comment now reads *one row per position a call site has ever been indexed at*, and
  `call_sites_for_operation` excludes retracted rows with deliberately no opt-in flag — "a detector
  asking this question is asking what to raise a finding against, and a position the code no longer
  occupies is not one."

  Verified through the detector-facing query rather than the raw table, which matters: a raw
  `SELECT` still shows two rows and reads like a failure. What a detector sees:

      initial              detector 1 site at [5] | raw 1 | findings 1
      after the line shift detector 1 site at [6] | raw 2 | findings 1
      re-index unchanged   detector 1 site at [6] | raw 2 | findings 1   converges

  Corpus unmoved — precision 1.0000 n=26, recall 1.0000 n=26, negatives 7, pairs 17, every floor
  cleared. Suite `2507 passed, 1 skipped`.

  The lesson worth keeping is about the gate rather than the fix: the first attempt looked correct
  and was caught only because the brief had named the cascade as the thing that would make the
  change worse than the defect, and the check was run rather than assumed.

- Make the symbol-map pin check legible under concurrency. Landed `966d703`. `verify_staged_map`
  now reads the artifact **once** and decides parse, count and digest from those bytes, so a rewrite
  landing after the read cannot manufacture a refusal at all. When a refusal *is* raised the file is
  re-read, and a changed file raises `SymbolMapRewritten` — a `SymbolMapMismatch` subclass, so
  `score_corpus.py` and every other existing caller go on stopping.

  **The old code was worse than the brief described.** It called `read_staged_map(staged)` twice,
  once for the digest and once for the count, so it could compare two different files and refuse
  over neither. The brief only proposed narrowing a window; the window was a two-read race.

  Measured rather than argued: a two-thread writer produced 4000 concurrent refusals, **3726
  attributed to the rewrite and 274 falling on the loud side** — so the classification is good but
  not total, and roughly seven percent of concurrent rewrites still read as a real mismatch. Named
  as uncovered in the report, along with the case nothing can separate: a rewrite that completed
  before the read is indistinguishable from a stale artifact, because it is one.

  Verified here that the case the check exists for still fails loudly — one symbol repointed, refused
  naming both digests. It also settles the two-skips question that has been drifting between
  sessions: the second skip is a worktree lacking `.cache/specs/v2320.json` and `tools/oasdiff`, not
  the pin test.

- Record the rung a finding's binding came from. Landed `7cb4e95`. `finding.binding_rung` is a
  column rather than a join, `NOT NULL DEFAULT 'unattributed'` so rows written before it existed
  answer honestly, and all five detectors attribute by the rule that **the rung names the binding
  whose wrongness would make the finding wrong** — `static` for vendor_change, parameter_deprecation
  and observed_drift, the correlation's own rung carried through for efficiency, and status_rate
  folding a population to the weaker of the only two values that table holds.

  The subtlety the worker caught unprompted: the rung is deliberately absent from `_stable_id`, so a
  correlator improving from `unresolved` to `observed` converges on the row it already wrote instead
  of double-counting. Two idempotence tests pin it.

  Corpus verified here rather than taken on trust — the worker could not run that gate, because its
  worktree lacks the staged spec and the pin *correctly refused* to score against the wrong map,
  which is B64's work doing its job one task later. From a tree that has it: 1.0000, 1.0000, 7, 17,
  every floor cleared. Suite `2548 passed, 1 skipped`.

  Two coordinator errors it corrected: my preservation commit still called the work "unreviewed, not
  gated" after that stopped being true, and its schema comment still described the required field I
  had already reversed. It amended both. The enforcement half of that reversal is B66.

- Refuse to persist a finding that names no rung. Landed `f2c8275`. `insert_finding` raises
  `ValueError` naming the detector when `binding_rung` is `unattributed`, before the insert, with
  the argument for the placement in its own docstring — the check is at the store because `Finding`
  is exported from `sync.core` and a required field there breaks every third-party detector.

  Verified here: it refuses, names the detector, and **leaves no row behind** — the worker's second
  mutation existed specifically to prove that a write-then-check implementation would be caught, and
  it is the only test that catches it. The fourteen tests it had to touch each state the rung their
  detector attributes (four `observed`, three `static`, the efficiency fixtures commented as taking
  the correlated case) rather than a blanket value.

  It also closed the question B65 was asked and never answered: `insert_finding` is the only route
  that can set a rung. Two `INSERT INTO finding` exist — the store, and one test deliberately
  omitting the column to prove history reads back — `set_finding_status` writes status alone, there
  is no `COPY` or `executemany`, `psycopg.connect` appears in `src/` only in `store.py`, and
  `sync.benchmark` never persists a finding at all. That last fact is also why the corpus figures
  cannot move, and both sides measured 1.0000, 1.0000, 7, 17.

  `CLAUDE.md`'s rung bullet now names the mechanism, including why the check is not on `Finding` —
  the worker left that file to the coordinator deliberately, which was right.

- The conformance kit refuses what the store would. Landed `850854f`. `check_detector` gains a
  fifth rule, `_check_findings_name_a_rung`, rejecting `unattributed` and never asserting *which*
  rung is right — that is the detector author's judgement, and the kit cannot know it.

  **The accepting half caught what the failing half could not: `_CorrectDetector`, the kit's own
  published example of conformance, set no rung.** The kit was shipping an example whose findings
  the store would refuse. That is the third time this kit has been found certifying something it
  should not — `check_vendor_adapter` once passed an adapter resolving no symbol, and
  `check_remediator` read an empty diff as a decline — and the first time the miss was in its own
  reference implementation.

  Three mutations, each caught by a different test: removing the rule reddens both new tests,
  truncating to `findings[:1]` is seen only by the two-finding test, and inverting the predicate is
  caught by the accepting one. Verified here independently: two real rungs conform, no rung is
  refused naming the detector.

  It declined to check membership in `BindingRung`, correctly — the field is typed, so `banana`
  raises `ValidationError` at construction and never reaches a scan, leaving `unattributed` as the
  only member that is not a binder's rung. CLAUDE.md forbids validating conditions that cannot
  occur, and it applied that rather than adding a rule that could never fire.

  Two things beyond the ask: two fixtures had to name a rung because the new rule runs before the
  rule they exercise, and `docs/writing-a-vendor-adapter.md` still called the finding key a triple
  after `claim` had joined it.

- Make `sync.core` installable without the runtime. Landed `cf6031d`. `sync-core` is now a second
  distribution — a workspace member that `sync` depends on at `==0.1.0` — so an adapter author
  installs pydantic and nothing else. Verified independently rather than from the report, in a
  clean virtualenv holding only the built wheel:

      annotated-types, pydantic, pydantic-core, sync-core, typing-extensions, typing-inspection
      psycopg absent · langgraph absent · tree_sitter absent · mcp absent
      claude_agent_sdk absent · ast_grep_py absent
      sync.core imports, conformance kit reachable

  **Six packages against the eighty-one a checkout installs.** CLAUDE.md's first non-negotiable is
  now true in fact rather than in aspiration: it was enforced at the import level by `lint-imports`
  and false at the packaging level, which is the level the promise was made at.

  The worker took the hardest of the three shapes offered and documented the awkward part rather
  than hiding it: `src/` is the distribution's project root because `uv_build` refuses a module root
  outside the project it builds, and a backend that accepts one produces a wheel plus an sdist with
  no source in it. That reason is what stops the next person tidying it.

  `uv sync` still exits 0 for this repository and the suite is `2643 passed, 1 skipped`, which were
  the controls that mattered — a split that quietly changes what a developer here gets is not a win.

  Two coordinator near-misses worth recording. Diffed against a moved `main` the commit showed 506
  deletions including a whole test file; against its real base it is 449 insertions and zero
  deletions. And the first cherry-pick took only `HEAD`, which was the docs commit, missing the
  feature entirely — the six-file diff is what caught it.
