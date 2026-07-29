# Sync backlog

The queue an autonomous tick pulls from. Ordered by what unblocks the most, not by
size. When a tick has nothing else to do, it takes the topmost unclaimed item, dispatches
a worker against it, and moves the item to **In flight** with the task id.

An item is only **Done** once it is on `main` with all three gates green
(`uv run pytest`, `uv run lint-imports` unredirected, `uv run python scripts/lint_encoding.py src tests`).

Every item states what is wrong, why it matters, and what evidence would close it. An
item that cannot say what evidence closes it is not ready to dispatch.

## Ready

### B44 — Pin the Python repository B42 found (blocked on B43)

`openbraininstitute/virtual-lab-api`, Apache-2.0, **21 call sites over 12 operations**, three of
them carrying enough sites for the hold-back rule to fire. It clears every bar B37 set.

**B43 has landed, so this is now dispatchable.** Today it would add pairs scoring zero affected and zero
findings — moving `pairs_scored` and its floor while contributing nothing to either rate. A Python
repository in the corpus that measures no Python is worse than no Python repository, because the
gate would then be defending a number that describes nothing.

**Closes when:** it is pinned, its pairs score, and Python binding precision and recall are
reported with their sample sizes — whatever they turn out to be.

### B7 — The M0 acceptance run has not executed since the pipeline changed underneath it

`tests/test_e2e_stripe.py::test_one_command_produces_one_green_pull_request` is the
milestone's definition of done and it is `@pytest.mark.e2e`, deselected by default, so
nothing in CI or in any worker's gates has exercised it. Since it last ran the pipeline
gained: the tier cascade, the property-omit codemod, a push guard over the discarded-commit
range, branch deletion on abandonment, checkpoint serialiser registration, the
dependency-edit guard, staged-new-file support, and dependency-tree discarding. Every one of
those sits on the acceptance path.

Checked cheaply and it is not obviously broken: the test still collects, and the production
graph compiles with the real `StripeAdapter`, `TypeScriptAdapter`, `TieredRemediator`,
`GitHubForge` and store, exposing all eight nodes. That establishes the wiring survived. It
establishes nothing about behaviour.

**Run it with `-n0`.** `addopts` now carries `-n auto`, which applies to the e2e test too.

**This one is not a worker's to run unattended.** It opens a pull request on a real GitHub
repository and spends `xhigh` model time on the patch agent. It needs a human to decide
when, which is why it is recorded here rather than dispatched.

**Closes when:** one `sync run` produces a CI-green pull request again, or the failure is
recorded with which change broke it.

## In flight

_Nothing._

## Done

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
