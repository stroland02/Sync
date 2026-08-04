# Data modelling and persistence

An audit of how nine reference repositories store what they derive, compared against Sync's own
rules. Written 2026-08-04 against clones taken the same day.

**Repositories examined for this dimension.** All nine were opened. Four persist structured data
and are the substance of this note: `codegraph`, `codebase-memory-mcp`, `code-review-graph`, and
`codegraph`'s separately-schema'd telemetry backend. Three persist unstructured state:
`Understand-Anything` and `PageIndex` are covered briefly because their *absence* of schema is
itself a data point, and `open-code-review` gets a section of its own (§2g) because it has the
sharpest thinking in the set about what belongs inside a key, despite having no schema to enforce it
with. Two persist nothing at all: `superpowers`, `skills`. `claude-cookbooks` contains DDL, but only
as tutorial fixture data, and is dismissed in one paragraph. Every claim below is labelled VERIFIED
(read this session), REPORTED (a comment or commit message in the repository says so and I did not
re-derive it), or INFERENCE.

**Revised 2026-08-04 after a second pass.** Three things changed. §2c's claim that
`codebase-memory-mcp` has no provenance was wrong and is corrected — it has one, inside a JSON blob,
which is a more useful finding than the original. §2g, §3.7 and §3.8 are new, all from
`open-code-review`, which the first pass under-read. Open questions 6 and 7 are new.

---

## 1. What this dimension covers, and why it matters here

Persistence design is the question of what a row *means* and what happens when you write it twice.
Three sub-questions decide whether a derived-data product is trustworthy:

- **Grain.** What is one row? A table whose grain is undeclared is a table whose queries will
  eventually count the wrong thing, and the failure is arithmetic rather than an exception — a
  number that is wrong by a factor nobody notices.
- **Convergence.** Does re-running a stage over the same input produce the same rows? If
  idempotency lives in the calling code rather than in a constraint, then it holds only for the
  callers that remembered, and a second writer — a plugin, a daemon, a retry — breaks it silently.
- **Provenance.** Can you say where a row came from? A wrong answer that cannot be attributed to
  the mechanism that produced it cannot be fixed; it can only be argued about.

For Sync these are not hygiene, they are the product. Sync's claim is the *binding* — which call
site depends on which vendor operation — and a binding is a derived assertion with a confidence
that varies by how it was derived. Sync sells "we found a real dependency and here is the evidence,"
so a finding whose evidence is unlabelled is not a weaker finding, it is not a finding. Sync also
runs the same pipeline repeatedly over a slowly-changing world; every stage re-runs, every stage
must converge. And Sync intends to be open-core with third-party vendor adapters, which means the
store will one day have writers whose code Sync does not review. Every invariant that lives in a
caller rather than in the schema is an invariant that survives only as long as Sync writes all the
callers.

---

## 2. The design space

### 2a. Idempotency as a schema property

**`codebase-memory-mcp` is the strongest example in the set, and it is complete.** (VERIFIED.) The
whole schema is one DDL string in `internal/../src/store/store.c:228-330`. Every one of its eight
tables declares a key: `projects` has `name TEXT PRIMARY KEY` (line 231), `file_hashes` has
`PRIMARY KEY (project, rel_path)` (241), `nodes` has `UNIQUE(project, qualified_name)` (254),
`edges` has `UNIQUE(source_id, target_id, type, local_name_gen)` (273), `lsp_surface` has
`PRIMARY KEY (project, rel_path)` (299), `index_coverage` has
`PRIMARY KEY (project, rel_path, kind)` (311), and `index_coverage_meta` is keyed on `project`
(316). Every write names that key in an explicit conflict clause: `store.c:1478` (projects),
`1659` (nodes), `2023` (edges), `2339` (file_hashes), `2827` (coverage meta), `3462`
(lsp_surface), `7850` (summaries). I found no write in that file that assumes an empty table.

Its edge key is the most interesting thing in this dimension. An `IMPORTS` edge carries one
imported symbol's local name, so two named imports from the same module are distinct edges — but
the local name lives inside a JSON blob. Rather than lifting it to a column or hashing it in the
caller, the schema declares a *generated* column and puts that in the constraint
(`store.c:270-273`):

```sql
local_name_gen TEXT GENERATED ALWAYS AS (CASE WHEN type='IMPORTS'
  THEN coalesce(json_extract(properties,'$.local_name'),'') ELSE '' END),
UNIQUE(source_id, target_id, type, local_name_gen)
```

The comment above it (`store.c:256-262`) states the reason for `coalesce(...,'')` explicitly:
"NOT NULL: NULLs never conflict in a UNIQUE index, which would break their dedup entirely." That is
the same rule Sync writes on `observed_call.operation_id` (`schema.sql:345-347`) — two projects
arriving independently at the same trap means the trap is real.

**`codegraph` reached the same place, but by paying for it first.** (VERIFIED.) Its `edges` table
originally had only an `AUTOINCREMENT` surrogate id, and `insertEdge` used `INSERT OR IGNORE` —
which, with nothing unique to conflict on, is a plain `INSERT`. Two extraction passes emitting the
same edge produced byte-identical duplicate rows that inflated every count downstream. The schema
comment naming the defect is `src/db/schema.sql:165-172`; the fix is a `UNIQUE` index at 173-174,
folding nullable coordinates so coordinate-less edges dedup too:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_identity
  ON edges(source, target, kind, IFNULL(line, -1), IFNULL(col, -1));
```

This is `efcc19d` in another language. Sync's own rule file (`.claude/rules/graph-grain.md`) cites
that commit as "this rule being learned the expensive way." Two independent graph products learned
the identical lesson, and neither learned it by reasoning.

### 2b. Idempotency as a property of the calling code

**`code-review-graph` is the counter-example, and the contrast is sharp because it is the closest
sibling to `codegraph` in the set.** (VERIFIED.) Its schema is a Python string constant at
`code_review_graph/graph.py:74-121`. The `nodes` table declares
`qualified_name TEXT NOT NULL UNIQUE` (line 79) and `upsert_node` correctly names it in
`ON CONFLICT(qualified_name) DO UPDATE` (238-250). The `edges` table (94-105) declares **no unique
constraint at all** — a bare `id INTEGER PRIMARY KEY AUTOINCREMENT` and nothing else. A repository-
wide grep found `UNIQUE` exactly once in the whole package, on that one node column.

So `upsert_edge` (`graph.py:265-296`) implements convergence by hand: a `SELECT` on
`(kind, source_qualified, target_qualified, file_path, line)`, then an `UPDATE` if a row came back
and an `INSERT` if it did not. Migration v8 (`migrations.py:219-225`) exists solely to make that
`SELECT` fast — "Add composite index on edges for upsert_edge performance." It adds a plain index,
not a unique one. The project noticed the read cost of doing dedup in application code and paid it,
without noticing that one extra keyword would have moved the guarantee into the storage engine for
free.

The cost is two round trips per edge and a race window. The connection is opened with
`check_same_thread=False` and `journal_mode=WAL` (`graph.py:192-196`), the package ships a polling
daemon (`daemon.py:623`) and a `ThreadPoolExecutor`/`ProcessPoolExecutor` indexer
(`incremental.py:70-71`). I traced the `upsert_edge` callers and they all appear to run on the main
thread after the pool has returned, so the in-process race is probably not live today
(INFERENCE) — but nothing in the schema prevents it, and two *processes* (the daemon indexing while
a CLI run indexes) would both see no row and both insert (INFERENCE; WAL permits one writer at a
time but not one *reader-then-writer* sequence at a time).

**`codegraph`'s `unresolved_refs` is the same shape and admits it.** (VERIFIED.)
`insertUnresolvedRef` at `src/db/queries.ts:1957-1963` is a bare `INSERT INTO` with no conflict
clause, into a table (`schema.sql:79-92`) whose only key is an autoincrement id. Convergence comes
from `deleteUnresolvedByNode` and `ON DELETE CASCADE` from `nodes` instead — delete-then-insert
rather than upsert. That is a legitimate strategy, and the schema comment (70-78) documents the row
lifecycle carefully, but it means the table's correctness depends on every writer remembering to
delete first.

### 2c. Provenance: a column, a default, or nothing

Three of the four persisting repositories have a provenance concept. They differ in how honest the
representation is, and the differences are instructive.

**`codegraph` gets it closest to right, with one gap.** (VERIFIED.) `edges.provenance` is a real
column (`schema.sql:53`, added in migration v2 at `migrations.ts:42`), indexed (`schema.sql:187`),
and the vocabulary is closed in code: `src/extraction/kernel/layout.ts:112` declares
`PROVENANCES = [undefined, 'tree-sitter', 'scip', 'heuristic']`. That is a confidence ladder in
exactly Sync's sense — a parser result, an index-server result, and a guess. It is *used*: the
column is a query parameter (`queries.ts:1716-1728`, `getOutgoingEdges(sourceId, kinds?,
provenance?)` appends `AND provenance = ?`), and the MCP layer gates on it
(`src/mcp/tools.ts:1855`, `2002`, `2052` all branch on `provenance !== 'heuristic'`). The gap is
the write: the column is `TEXT DEFAULT NULL`, index 0 of `PROVENANCES` is `undefined`, and every
insert passes `edge.provenance ?? null` (`queries.ts:521`, `1661`, `1691`). Nothing refuses an
unattributed edge. An edge with no provenance is honest — it does not claim a rung it does not have
— but it is also indistinguishable from an edge written by a synthesizer that forgot.

**`code-review-graph` has the same idea and the default makes it worse than nothing.** (VERIFIED.)
`edges.confidence_tier TEXT DEFAULT 'EXTRACTED'` (`graph.py:103`, added by migration v9 at
`migrations.py:234-237`). The vocabulary is two values: `EXTRACTED` for a parser result, `INFERRED`
for a resolver's guess (`scoped_resolver.py:480`, `event_resolver.py:107`). The default is
`EXTRACTED` — the *higher-confidence* value. A row written by a caller that forgot to set the tier
claims to have been directly extracted. Worse, the read path fabricates it: `graph.py:2188` reads

```python
confidence_tier = row["confidence_tier"] if "confidence_tier" in row.keys() else "EXTRACTED"
```

so a row from a database predating migration v9 — a row whose provenance is genuinely unknown —
is returned to every caller asserting the strongest tier. This is the precise failure Sync's
`unattributed` sentinel exists to prevent, implemented backwards.

**`open-code-review` has no schema, but it does carry lineage.** (VERIFIED.) It persists a JSONL
event log per session (`internal/session/persist.go:20-38`), and every record carries `parentUuid`
threading it to its predecessor (`lastUUID`, line 37). Two fields are genuine provenance: a session
records `resumedFrom` (line 36) and a review item that reused a previous run's result records
`sourceSessionID` (`persist.go:177`, `186`). So a reviewer's comment can be traced to the session
that actually produced it rather than the session that reported it. In a schemaless log this is
purely convention — nothing prevents omitting either field — but the *modelling instinct* is right
and is the same one Sync formalises.

**`codebase-memory-mcp` has provenance, and keeps it where it cannot be used.** (VERIFIED. An
earlier draft of this note said the repository had none; that was wrong, and the correction is more
useful than the original claim.) There is no provenance *column*, but every `CALLS` edge carries the
resolver's verdict inside the free-form `properties` JSON blob. `src/pipeline/pass_calls.c:358-364`
builds it literally:

```c
snprintf(props, sizeof(props),
         "{\"callee\":\"%s\",\"confidence\":%.2f,\"strategy\":\"%s\",\"candidates\":%d}",
         esc_callee, res->confidence, res->strategy ? res->strategy : "unknown",
         res->candidate_count);
```

The vocabulary is a real confidence ladder — the MCP tool description at `src/mcp/mcp.c:515-518`
enumerates it as `lsp | language_rule | heuristic | unresolved` and tells the caller what it is for:
"Use it to judge whether an edge is trustworthy, not to find edges." That last clause is the whole
finding. Because the strategy lives in a JSON blob rather than a column, it is available for
*display* and unavailable for *selection*: it cannot be constrained, cannot be grouped without a
`json_extract` over every row, and cannot be indexed cheaply. The tool exposes it behind an opt-in
`include_evidence` flag that is off by default, so the trust signal is something a caller must know
to ask for.

The repository has already conceded the point once, for a different field. `properties.url_path` was
promoted out of the blob into a generated column and indexed
(`src/store/store.c:271` and `create_user_indexes` at 380) precisely so it could be queried. The
escape hatch exists and is proven; provenance simply has not been through it. This is the strongest
available evidence for Sync's own rule that lineage is "a column, not a join" — a repository that
started with the blob, hit the wall, and built the exact promotion mechanism Sync's rule skips
straight to.

### 2d. Grain, declared or not

Sync's rule is that a `-- Grain:` comment precedes the columns. Two references practise the same
discipline without naming it, and their coverage is partial in a revealing way.

**`codegraph`'s telemetry schema is the best single file in this dimension, and it is not the one
you would expect.** (VERIFIED.) `telemetry-worker/migrations/0001_init.sql` (Cloudflare D1) opens
by declaring the file itself a contract — "This file is public on purpose... If a column is not
here, it is not kept" — then gives every one of its five tables a grain sentence: "One row per
sanitized event accepted by POST /v1/events" (`events`), "Daily unique machines"
(`daily_machines`), "Machine × day activity matrix" (`machine_days`), "First day a machine was ever
seen" (`machine_first_seen`). It goes further than Sync does in one respect: it states the
*arithmetic hazard* each grain creates, in the imperative. On `daily_machines`:

> NOTE: these are per-day distinct counts and CANNOT be summed across a range — a range-wide
> distinct count comes from `machine_days`.

and on the volume column in `daily_event_counts`, that for `usage_rollup` events one row is a
pre-aggregated counter, so `count` is a `SUM` of a prop rather than a row count — restated in
`src/rollup.ts:74-80` where the SQL lives: "counting rows there would silently report 'machines
that used the tool' and undercount by an order of magnitude." That sentence is structurally
identical to Sync's "a query that counts findings by counting rows is wrong, and wrong quietly."

Its rollup writes are all keyed upserts (`rollup.ts:82` `ON CONFLICT (day, event, dim, value) DO
UPDATE`, `123-137` for the other two tables), and the ingest path picks the merge per column:
`machine_days.prod` merges with `max()` and `machine_first_seen.first_day` merges with `min()`
(`src/index.ts:200-205`), with the comment explaining that a late-arriving offline buffer "can move
a machine's first day earlier but never later." That is the same argument Sync writes for
`first_seen = LEAST(...)` / `last_seen = GREATEST(...)` in `record_observed_shape` and
`record_observed_call`.

The same repository's *primary* schema — `src/db/schema.sql`, the code graph itself — declares no
grain for any of `nodes`, `edges`, `files`, or `project_metadata`. `unresolved_refs` gets a
lifecycle note (70-78) and `name_segment_vocab` gets a rich rationale (136-148), but neither says
what one row is. (VERIFIED.) So within one repository, the schema written for a dashboard nobody's
correctness depends on is documented to a higher standard than the schema the product runs on. That
is worth noticing rather than mocking: the telemetry file was written once, deliberately, with
money attached; the graph schema accreted.

**`codebase-memory-mcp` declares grain for its three metadata tables and none of its graph tables.**
(VERIFIED.) `lsp_surface` gets "One row per file: its serialized cross-file LSP surface..."
(`store.c:283-288`), `index_coverage` gets "One row per file the indexer could not fully cover"
(298-303), `index_coverage_meta` gets "One row per completed coverage persistence attempt"
(311-313) — which is a per-*attempt* grain of exactly the kind Sync's `migration_outcome` has, and
the comment even draws the consequence: "a missing row unambiguously means coverage metadata is
unavailable." `projects`, `file_hashes`, `nodes` and `edges` get nothing. The pattern across both
repositories is that grain gets written where the row is a *record of an event or an attempt*, and
gets skipped where the row feels like an object. That is backwards: object tables are exactly where
a re-index silently changes what a count means.

**`code-review-graph` declares grain nowhere.** (VERIFIED — I read the whole of `_SCHEMA_SQL` at
`graph.py:74-121` and all nine migrations.) Column-level comments name a vocabulary
(`kind TEXT NOT NULL, -- File, Class, Function, Type, Test`) but no table says what one row is.

### 2e. Migrations

Three strategies are represented, and Sync uses a fourth.

**Versioned, ordered, transactional, with a version table.** `codegraph`
(`src/db/migrations.ts`): a `schema_versions` table (`schema.sql:5-9`), `CURRENT_SCHEMA_VERSION = 8`
(line 12), an array of `{version, description, up}` (29-153), and `runMigrations` executing each
pending migration inside its own transaction with the version recorded in the same transaction
(182-199). `code-review-graph` (`code_review_graph/migrations.py`) is the same design in Python: a
`MIGRATIONS: dict[int, Callable]` registry (245-254), `run_migrations` committing and version-
stamping per migration and rolling back on failure (259-284). Both handle SQLite's lack of
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` by probing `PRAGMA table_info` first — `codegraph` at
`migrations.ts:139-146`, `code-review-graph` in `_has_column` at `migrations.py:48-54`, which also
allow-lists table names against a frozenset to keep the f-string interpolation safe.

What makes `codegraph`'s version of this worth copying is that migration v6 (`migrations.ts:78-102`)
proves the framework can express a **data repair**, not just DDL:

```sql
DELETE FROM edges WHERE id NOT IN (
  SELECT MIN(id) FROM edges
  GROUP BY source, target, kind, IFNULL(line, -1), IFNULL(col, -1)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_identity ON edges(...);
```

with a comment noting the `GROUP BY` must match the index expression exactly or the index creation
fails on a pair the `DELETE` left behind, and that the whole migration is idempotent because the
`DELETE` becomes a no-op once the table is unique. And it is *tested*, by ageing a database:
`__tests__/db-perf.test.ts:324-360` builds a current database, drops the identity index, deletes
the recorded version rows at or above 6, inserts a duplicate to prove the pre-fix state admits it,
runs `runMigrations(raw, 5)`, then asserts the duplicate collapsed, the distinct edge survived, the
index exists, and a subsequent re-insert is a no-op.

**No framework; detect incompatibility and refuse to open.** `codebase-memory-mcp` has no version
table and no migration list. `init_schema` issues `CREATE TABLE IF NOT EXISTS` and then runs a
compatibility probe (`store.c:332-347`): it prepares `SELECT local_name_gen FROM edges LIMIT 0` and,
if that fails, logs `store.schema result=incompatible missing=edges.local_name_gen` and returns an
error, failing the open. The stated reason is that SQLite cannot `ALTER` a table-level `UNIQUE`
constraint in place, so a pre-widening database can neither prepare the current upsert nor hold two
named imports — and callers already treat an unopenable database as a signal to delete and rebuild.
(REPORTED — the comment states the caller behaviour; I did not trace the rebuild path.) This is a
defensible answer for a derived cache: the data is reproducible, so a schema change is a rebuild
rather than a migration, and the probe converts a silent wrong answer into a loud refusal.

**None.** `Understand-Anything` has no migration mechanism; it handles its one historical change —
renaming the data directory from `.understand-anything/` to `.ua/` — by preferring the legacy
directory forever if it exists (`packages/core/src/persistence/index.ts:19-21`, "no migration
needed"). That works for whole-file replacement and would not survive a schema.

### 2f. Whole-file replacement instead of a store

**`Understand-Anything`** (VERIFIED, `packages/core/src/persistence/index.ts`) writes four JSON
files under `.ua/`: `knowledge-graph.json`, `meta.json`, `fingerprints.json`, `config.json`. Each
save is `writeFileSync(path, JSON.stringify(x, null, 2))` over the whole document (84-98, 122-125,
133-136, 150-153). Idempotency is total and free — writing the same graph twice produces the same
bytes — but there is no merge, no per-row conflict resolution, and no grain, because there are no
rows. Two properties are worth carrying forward regardless of store:

- **Sanitisation at the persistence boundary, not at the caller.** `sanitiseFilePaths` (53-82) runs
  inside `saveGraph`, converting absolute paths to project-relative and reducing out-of-tree paths
  to a bare basename, with the comment (87-90) recording that this was a *fix*: without it,
  `/Users/alice/company/src/auth.ts` was written verbatim and later served by the dashboard. Same
  instinct as Sync's "never store what must not be stored", placed at the same layer.
- **Validation on read.** `loadGraph` runs `validateGraph` and throws on failure (109-117).

The cost is two-fold and both halves are visible in the file. The write is not atomic — no temp
file and rename — so a crash or a full disk mid-write truncates the graph. And the read path
swallows exactly that: `loadFingerprints` returns `null` on any parse failure (141-145) and
`loadConfig` silently returns defaults (158-162). A corrupted fingerprint store therefore presents
as "nothing has been analysed yet," which re-analyses everything rather than reporting damage.

**`PageIndex`** (VERIFIED, `pageindex/client.py`) is the same design with one addition: a
`_meta.json` index over per-document JSON files, plus `_rebuild_meta` (170-179) which reconstructs
that index by scanning the directory whenever the index is missing or corrupt, and `_read_json`
(148-155) which prints `Warning: corrupt <name>` and returns `None`. So the *derived* index is
treated as disposable and the per-document files are the source of truth. That is the right
layering, and it is a cheap idea: a rebuildable index needs no migration and no consistency
guarantee.

**`claude-cookbooks`** contains one file with DDL,
`claude_agent_sdk/site_reliability_agent/infra_setup.py:221-249` — a two-table Postgres demo
(`users`, `orders`) seeded with `ON CONFLICT (email) DO NOTHING` so the tutorial can be re-run.
Idempotent seeding is the only design decision in it. Nothing to learn beyond that.

**`superpowers` and `skills` persist nothing.** (VERIFIED — `superpowers/hooks/` contains only
`hooks.json`, `hooks-cursor.json`, `run-hook.cmd` and a `session-start` directory, with no file
writes; `skills/skills/` is markdown.) Both are content libraries distributed as files, and the
absence is correct for what they are.

### 2g. Identity, and what is deliberately kept out of it

One reference has thought harder about *what belongs in a key* than about where the key is enforced,
and it is the one with no schema at all.

**`open-code-review` keeps two identities per item and names the job of each.** (VERIFIED.)
`CoverageItem` (`internal/session/manifest.go:178-185`) carries both an `ItemID` and a
`Fingerprint`. `ItemID` is minted by one canonical function (196-207) from
`(operation, mode, normalizePath(oldPath), normalizePath(newPath))`, SHA-256 over a NUL-joined key,
with `normalizePath` (213-223) unifying separators and cleaning `.`/`..` so cosmetically different
spellings of one path collapse. The doc comment above it states the contract:

> It is content-independent... so the same logical file keeps a stable item_id across a resume chain
> even when its diff content (and therefore its fingerprint) changes. The raw diff content lives
> only in `CoverageItem.Fingerprint`, which is used for checkpoint matching. Every call site —
> `RegisterSelected` and each `Mark*` — MUST key on the same `ItemID(...)` so a mismatched key never
> silently no-ops a transition.

So the content-dependent identity is not forbidden, it is *demoted*: it exists as a second field for
the one job that needs it (matching a resume checkpoint), while every state transition keys on the
content-independent one. The failure it is written against — "a mismatched key never silently
no-ops a transition" — is the same class as the one Sync's `finding` key was fixed for.

Sync reaches the same conclusion and expresses it as a prohibition. `insert_finding`
(`store.py:370-372`) carries: "Neither the rationale nor anything derived from it may join this key:
efficiency rationales carry live call counts, so an id computed from one would change between runs
and accumulate a row per scan rather than converging." (VERIFIED.) Both projects identified that
content in a key destroys convergence. `open-code-review` then kept the content hash and gave it a
job; Sync discarded it. The consequence is in §3.7.

Two smaller things in the same file are worth recording. The failure vocabularies are *closed and
validated*: `FailureClass` has eight members with a `valid()` method (`manifest.go:52-72`),
`RunFailureClass` has seven and a separate `valid()` (86-107), and the two are deliberately different
enumerations — a run never fails with `provider` or `panic` because those are always attributable to
one item, and the run enum adds `internal` for scheduler failures. `itemFailureForRunClass` (110-129)
is the explicit, commented mapping between them, including the two run classes that have no item
equivalent and therefore sweep their pending items to `unknown` while the run-level record keeps the
precise cause. And `TerminalState` (159-166) is four values computed *only* from the coverage sets
plus `run_failure`, with the comment naming it "the authoritative replacement for the
warning-derived `completed_with_errors` status" — a terminal status that is derived from the work
rather than from how loud the run was.

---

## 3. What Sync should adopt

### 3.1 Declare the natural key in the schema for the three tables that only hash it in Python

**Proof: `codebase-memory-mcp/src/store/store.c:243-275`** — every table's identity is a table-level
`UNIQUE`/`PRIMARY KEY`, and every write names it.

Four of Sync's seven tables do this: `migration_outcome` (`schema.sql:234`), `observed_shape` (307),
`observed_call` (370), `observed_error_window` (446). The other three — `call_site`,
`vendor_change`, `finding` — declare only `id TEXT PRIMARY KEY`, and their natural key exists
nowhere but inside `_stable_id` in `store.py:20-21`, called at `240`, `316-319` and `373-375`. The
components are not even stored in one case: `vendor_change`'s identity includes
`change.raw.get("text", "")`, which lives only inside the `raw` JSONB and is never a column.
(VERIFIED.)

The consequence today is small, because Sync writes all three callers. The consequence at the
open-core boundary is not: a third-party adapter that writes through `GraphStore` gets the right
identity, but a third-party adapter that writes SQL — or a future ingest worker in another language,
or a bulk loader — can insert a duplicate that nothing rejects. `codebase-memory-mcp`'s generated-
column trick is the direct answer for `vendor_change`: add
`raw_text_gen TEXT GENERATED ALWAYS AS (raw->>'text') STORED` and
`UNIQUE (vendor_id, from_version, to_version, kind, path_ptr, operation_id, raw_text_gen)`, and the
identity becomes the database's rather than the caller's. `call_site` and `finding` need no
generated column — every component of both keys is already a column.

Land it in `src/sync/graph/schema.sql`, with the caveat in 3.3 below.

### 3.2 A version table and ordered migrations, before the hosted control plane needs one

**Proof: `codegraph/src/db/migrations.ts` (framework) plus
`codegraph/__tests__/db-perf.test.ts:324-360` (the aged-database test that proves a data-repair
migration works).**

`GraphStore.apply_schema` (`store.py:147-193`) converges a database forward by re-issuing every
declared column as `ADD COLUMN IF NOT EXISTS`, derived from the `CREATE TABLE` bodies so nobody has
to maintain a parallel ALTER list. That derivation is genuinely better than either reference's
hand-written migration bodies, and its docstring is admirably honest about the boundary: it "cannot
rename a column, change a type, add or drop a constraint, or backfill a value, and it does not
restore a table-level `UNIQUE` that a dropped column took with it," and it nominates itself for
replacement — "When the first rename or backfill arrives, this is the thing to replace rather than
the thing to extend." (VERIFIED.)

That moment is now, and 3.1 is what brings it: adding a `UNIQUE` constraint to a populated table is
exactly the operation `apply_schema` cannot express. Sync also already has the harder half of the
test infrastructure — `tests/test_schema_convergence.py` has an `aged_dsn` fixture (line 40) and an
`_age(dsn, *drops)` helper (59) that strips columns to simulate an old database. `codegraph`'s v6
test is the same fixture applied to a constraint instead of a column.

Note the trap `codegraph` set for itself and Sync avoided: `codegraph/src/db/schema.sql:12-13`
contains a data `INSERT` into `schema_versions`, which makes the file non-re-executable, which
forces `src/db/index.ts:373-377` to recover FTS triggers by running a **regular expression over the
schema file** to extract just the trigger DDL. The comment at 366-369 states the reason outright.
Keep Sync's `schema.sql` pure DDL and keep the version row a runtime write.

### 3.3 A compatibility probe that refuses the open, for the constraints `apply_schema` cannot restore

**Proof: `codebase-memory-mcp/src/store/store.c:332-347`.**

Even after 3.2, there will be a window where a developer's database predates a constraint. Sync's
current behaviour in that window is the worst available: the constraint is absent, every write still
succeeds, and duplicates accumulate — the `codegraph` #1034 failure exactly. A probe after
`apply_schema` that queries `pg_indexes` for each declared table-level `UNIQUE` and raises naming
the missing one converts a silent divergence into a startup refusal. `codebase-memory-mcp`'s probe
is four lines and logs the missing object by name.

This has a second use Sync needs more than `codebase-memory-mcp` does. `schema.sql` already records
(lines 86-115) that `vendor_change.severity` is deliberately *not* a `CHECK` constraint, because a
`CHECK` riding on a column definition never reaches a database that already has the column — so it
would be "absent and believed present," which the comment correctly calls worse than absent. A probe
is the general answer to that whole class: it does not add the constraint, it makes its absence
loud.

Land it as a method on `GraphStore` called from `apply_schema`, in `src/sync/graph/store.py`.

### 3.4 Snapshot and re-attach conclusions across a re-index, instead of dropping them

**Proof: `codegraph/src/extraction/index.ts:2280-2301` (the snapshot) and `2448-2479`
(`reattachCrossFileEdges`), with the supporting query at `src/db/queries.ts:1835-1856`.**

This is the most directly transferable piece of engineering in the whole survey, because it is a
solved version of a problem Sync's code explicitly declines to solve.

`codegraph` hit it as issue #899. Node ids are `sha256(filePath:kind:name:line)` — position is in
the identity, exactly as Sync's `_stable_id(repo_id, path, symbol, line, col)` puts it in. So a
docstring-only edit above a symbol changes every node id in that file. Re-indexing the file deletes
its nodes (`queries.ts:637-647`, `DELETE FROM nodes WHERE file_path = ?`) and `ON DELETE CASCADE`
(`schema.sql:54-55`) takes every edge with them — including edges whose *source* is in an unchanged
file, which nothing will re-emit. The comment at `extraction/index.ts:2280-2294` names the
consequence: "re-indexing a callee file severs `calls`/`references` edges from callers that import
it."

The repair snapshots incoming cross-file edges before the delete, along with each target's
`(kind, name)`, then re-resolves them against the newly-inserted nodes by `(kind, name)` rather than
by id (`2459-2467`). Three details make it safe rather than a guess:

- Matching is on identity **minus position**, which is stable across the line shifts that caused the
  problem in the first place.
- A target that finds no match is not guessed at: the edge is converted back into an *unresolved
  reference* (`2468-2470`, `resurrectRefFromDroppedEdge`), so the graph records that something used
  to point here and no longer resolves, rather than silently forgetting.
- `provenance` is carried through the re-attach verbatim (`2467`). Lineage travels across the
  repair, which is Sync's own rule applied where it is easiest to drop.

Sync's `replace_call_sites` (`store.py:267-313`) currently ends with: "What this does not do is
match an old row to a new one and move the finding across. A call at line 13 where there used to be
one at line 12 may be the same call shifted or a different call written where the old one was
deleted, and nothing at this layer can tell those apart." That objection is real but it is answered
by not matching on position at all. Sync has the same components: `(repo_id, path, symbol)` is
`call_site` identity minus `(line, col)`. Where that key is unique within a file, the match is as
safe as `codegraph`'s. Where it is not — the same SDK method called twice in one file, which is
precisely what `efcc19d` was about — Sync should decline, and declining is *detectable* rather than
guessed: count the candidates, and re-attach only where there is exactly one.

This lands in `GraphStore.replace_call_sites`, and would convert a retracted call site's open
findings onto the new row rather than filtering them out of `open_findings` forever.

### 3.5 The rollup shape, when `observed_call` needs one

**Proof: `codegraph/telemetry-worker/migrations/0001_init.sql` plus
`telemetry-worker/src/rollup.ts:118-140`.**

Sync's `observed_call` grain comment (`schema.sql:320-326`) already reaches the right conclusion —
keep trace-level resolution now, aggregate later, "a rollup is derivable from these rows at any
time; these rows are not recoverable from a rollup." What it does not yet have is the shape of the
aggregate. `codegraph`'s telemetry backend is that shape, built and running:

- Raw events are purged on a retention window; rollups are kept forever because they are tiny.
- One table — `machine_days`, a `(machine_id, day)` matrix, `WITHOUT ROWID` — is **never** purged,
  because it is the only thing that can answer a range-wide distinct count. The daily rollup is
  rebuilt *from that table* rather than from the purged raw events (`rollup.ts:118-127`), so a
  rollup for a day whose raw rows are gone is still recomputable.
- New breakdowns are rows in a generic `(day, event, dim, value)` table (`daily_dim_counts`), so
  "adding a breakdown is a line in `ROLLUP_STATEMENTS`, never a migration."
- The retention window is chosen in the DDL comment with arithmetic attached — measured row size,
  D1's per-index write billing, 90 days ≈ 6.7 GB against a 10 GB cap, 180 days exceeds it — and the
  levers to pull if it gets tight are listed in order.

That last item answers a question Sync's `call_site` grain comment leaves open (`schema.sql:19-22`):
"nothing prunes it. That is deliberate — a retention rule is a decision about how long a conclusion
stays explainable... A hosted control plane will have to make it." `codegraph` demonstrates that the
decision belongs in the schema file with its cost model beside it, so that whoever revisits it
inherits the arithmetic rather than redoing it.

### 3.6 Push the rung into the query

**Proof: `codegraph/src/db/queries.ts:1716-1728`.**

Sync stores `binding_rung` on three tables and surfaces it to the dashboard
(`src/sync/dashboard/queries.py:103`) and MCP (`src/sync/mcp/tools.py:135`, `249`, `283`, `397`) —
but every filter on it happens in Python after materialising Pydantic models. `open_findings`
(`store.py:495-517`) has no rung parameter. (VERIFIED.) `codegraph` makes provenance an optional
`WHERE` clause. Cheap, and it is what turns "we record the rung" into "you can ask for only the
findings you trust."

### 3.7 Keep the content fingerprint that the identity rule throws away

**Proof: `open-code-review/internal/session/manifest.go:178-207` — `ItemID` (content-independent,
keys every transition) and `Fingerprint` (content-dependent, keys checkpoint matching) as two fields
on one struct.**

Sync's `finding` identity is `_stable_id(detector, call_site_id, vendor_change_id, claim)`
(`store.py:373-375`), and `store.py:370-372` correctly forbids the rationale from entering it,
because efficiency rationales carry live call counts and a key computed from one would write a fresh
row per scan. The prohibition is right. What it costs is that `finding` carries no record of the
rationale's content at all beyond the current text, so one question is unanswerable: *did this
finding's evidence change?* A DETECT run that upserts an existing finding with a materially different
rationale — the call count doubled, the drift got worse — is indistinguishable from a run that
re-derived the identical claim, because `ON CONFLICT (id) DO NOTHING` (`store.py:381`) does not even
write the new rationale. (VERIFIED.)

`open-code-review`'s answer is to keep both and give the content hash a narrow job. The Sync analogue
is a `rationale_hash` column on `finding`, written on every DETECT pass, deliberately outside the
identity for exactly the reason `binding_rung` is outside it (`store.py:386-392`). It costs one
column and turns `DO NOTHING` into `DO UPDATE SET rationale = EXCLUDED.rationale, rationale_hash =
EXCLUDED.rationale_hash` where the hash differs, which makes "this finding's evidence moved" both
detectable and cheap to query. Land it in `schema.sql`'s `finding` table and `insert_finding`.

### 3.8 Give `abandon_reason` a closed vocabulary

**Proof: `open-code-review/internal/session/manifest.go:52-129` — two distinct closed enumerations,
each with a `valid()` method, plus an explicit commented mapping between them.**

`CLAUDE.md` and `.claude/rules/graph-grain.md` both say abandoned runs are data and the reason stays
queryable, and `schema.sql:222` has the column. But the value written is
`state.get("diagnostics") or "unknown"` (`src/sync/remediate/nodes.py:643`) — free-form diagnostic
prose from whichever stage failed. (VERIFIED.) So `GROUP BY abandon_reason` over
`migration_outcome` returns approximately one group per distinct error message, and the query the
column exists to serve — which change kinds are not mechanically safe — cannot be written against it.
The column is queryable in the sense that it is a column, and not in the sense that anyone can learn
from it.

`terminal_status` is milder but has the same shape: three string literals written inline at
`nodes.py:217`, `571` and `653` with no shared alias, unlike `Severity`, which `schema.sql:79-82`
names once and `tests/test_severity_vocabulary.py` asserts the identity of across three columns.
(VERIFIED.)

What `open-code-review` proves is that the useful version of this is *two* vocabularies, not one: a
per-item class and a per-run class that are deliberately different sets, with a named function
mapping run cause onto item cause and a comment explaining the two run causes that have no item
equivalent. Sync has the same two levels — a `migration_outcome` row is one attempt, and a scan is a
run over many. The adoption is a `sync.core.AbandonReason` alias in the same shape as `Severity`,
with the free-form diagnostic kept in a separate column rather than in this one.

---

## 4. What Sync already does better, and where a reference would cost it

**Grain coverage is complete here and partial everywhere else.** All seven of Sync's tables carry a
`-- Grain:` comment stating what one row is and, in five cases, the specific query that would be
wrong without it. The best reference achieves this for its telemetry schema and for three of eight
metadata tables; the closest sibling product achieves it for zero. Adopting anything from
`code-review-graph`'s or `codegraph`'s *graph* schema documentation would be a step backwards.

**Refusing an unattributed row has no equivalent in the set.** `GraphStore.insert_finding`
(`store.py:335-395`) raises on `binding_rung == UNATTRIBUTED`, naming the detector, with the check
at the write rather than on the model so that `sync.core` stays a publishable SDK. No reference
refuses anything. `codegraph` defaults to NULL, which is at least honest. `code-review-graph`
defaults to `EXTRACTED` and *fabricates* `EXTRACTED` on read for legacy rows (`graph.py:2188`) —
adopting that pattern would mean every pre-column Sync finding claiming to rest on a static binding.
The cost of that mistake in Sync's setting is precisely measurable: `sync.benchmark.binding` scores
precision per rung, so a fabricated rung is a measurement about a binder that never ran.

**Per-column merge semantics, argued.** `record_observed_shape` (`store.py:589-642`) chooses a
different merge for each column and writes the reason for each: `nullable_seen` is `OR` because
evidence does not expire; `spec_enum_values` is a sorted union because traffic exercises one member
at a time; the window widens at both ends because sources do not arrive in order; and `sample_count`
adds for traffic sources but takes a `GREATEST` for synthetic ones, because a replayed synthetic
body is the ingest running again rather than the shape being seen again. Only `codegraph`'s
telemetry ingest does anything comparable, and only for two columns (`max` on `prod`, `min` on
`first_day`). `codebase-memory-mcp` merges every edge write with one uniform `json_patch`
(`store.c:2023-2027`), which is a deep last-write-wins and cannot express "this counter adds and
that one holds." `code-review-graph`'s rollups are uniformly `SET x = excluded.x`.

**Retract instead of delete.** Sync's `call_site.retracted_at` (`schema.sql:46-55`) exists because
`finding.call_site_id REFERENCES call_site (id) ON DELETE CASCADE` — deleting a stale call site
deletes what a run concluded about it, "measured on the first attempt at this: the ghost row went
and the finding went with it, one row to zero" (`store.py:281-286`). Both graph references take the
delete: `codegraph` at `queries.ts:637-647` and `code-review-graph` at `graph.py:298-303`
(`remove_file_data`). For a pure code graph that is fine — the graph is fully re-derivable and
nothing hangs off a node. For Sync it would destroy the corpus. Do not adopt delete-by-file, and
note that `codegraph` itself had to build the #899 snapshot machinery (§3.4) to survive its own
choice, which is evidence for Sync's position rather than against it.

**Pure-DDL `schema.sql` that can be re-executed.** Covered in §3.2. `codegraph` paid for the
alternative with a regex.

**Where `codebase-memory-mcp`'s approach would cost Sync something real.** Putting the natural key
in the schema is right (§3.1), but that repository shows the bill when a second writer exists: it
ships a raw SQLite file writer that constructs the database byte-by-byte for speed
(`internal/cbm/sqlite_writer.c:2192-2256`), which duplicates every `CREATE TABLE` as a C string
literal and hand-builds the `sqlite_autoindex_*` B-trees, with a comment at 2215-2220 warning that
the definitions "must stay semantically" identical across three places. Sync has exactly one writer
today and should keep it that way; a second one is where a table-level constraint stops being free.

Also from that repository, a cautionary note worth keeping: it tried a partial expression index over
`json_extract(properties,'$.is_entry_point')` and **reverted** it, because `json_extract` in an
index `WHERE` clause aborts `CREATE INDEX` — and therefore the whole database open — on any row
whose JSON is malformed (`store.c:380-387`). Sync's `vendor_change.raw` and `observed_call.spans`
are both JSONB with the same exposure if anyone indexes into them.

**Where whole-file JSON would cost Sync.** `Understand-Anything`'s and `PageIndex`'s design is
simpler than anything Sync has, and it buys idempotency for free. It also loses every per-row merge
Sync depends on — `sample_count`, the span map, the widening windows — and both write non-atomically
and then swallow the resulting corruption (`persistence/index.ts:141-145`, `client.py:148-155`). For
Sync that would mean an interrupted OBSERVE ingest presenting as "no baseline yet."

---

## 5. Open questions only the owner can settle

1. **Does §3.4 land, and with what tie-break?** Re-attaching findings across a re-index is the
   highest-value item here and the only one that changes what a customer sees. `codegraph` matches
   on identity-minus-position; Sync's analogue is `(repo_id, path, symbol)`. The unresolved case is
   two calls to the same SDK method in one file — `efcc19d`'s case. Declining when the candidate
   count is not exactly one is safe and detectable, but it means the common Stripe-heavy file gets
   no re-attachment at all. Is a partial repair worth the code, or does the honest answer stay
   "re-raise the finding against the new row"?

2. **When does `apply_schema` get replaced, and does §3.1 force it early?** Its docstring argues
   convincingly that a migration framework bought now is carried for a year before it is needed.
   But declaring the three missing natural keys is an `ADD CONSTRAINT` on a populated table, which
   `apply_schema` cannot do. Either the constraints wait for M4, or the framework arrives ahead of
   the need. The `vendor_change` generated column has the same shape.

3. **Should the grain rule become a test?** Nothing enforces it — a grep for `Grain` across
   `tests/` and `src/sync/core/models.py` returns nothing, and `_statements()` in `store.py:31-41`
   strips comments before anything sees them, so no existing check could catch a missing one by
   accident. (VERIFIED.) None of the references test it either. A test asserting every
   `CREATE TABLE` in `schema.sql` is preceded by a `-- Grain:` line is about fifteen lines and would
   make the rule survive an agent that has not read `.claude/rules/graph-grain.md`. Against that: it
   tests for the presence of prose, not its correctness, and a rule that can be satisfied by typing
   the magic word may be worse than one that requires having read the argument.

4. **Is `unattributed` allowed to persist?** It is refused on the `finding` write, but
   `Finding.binding_rung` still *defaults* to it (`models.py:149`) so a third-party detector can
   construct one, and the column default keeps it reachable for history. `code-review-graph` shows
   the failure mode of a wrong default vividly. Is the current split — model permissive, write
   strict — the permanent answer, or does it tighten once the third-party detector surface is real?

5. **Does the retention decision get written down now?** `call_site` grows one row per position a
   call has ever occupied and nothing prunes it; `observed_call` and `observed_error_window` cannot
   be backfilled. `codegraph`'s telemetry schema shows a retention window chosen against measured
   row sizes and a storage cap, with the levers listed. Sync's arithmetic will differ, but the
   question — how long does a conclusion stay explainable — is answerable before the first hosted
   tenant, and much harder after.

6. **Is the Type 2 rule aspirational, and should it say so?** `.claude/rules/graph-grain.md` carries
   a rule with a heading of its own — "Vendor operations are Type 2, not Type 1... Never update a
   vendor-derived row in place — write a new row with validity bounds" — and there is nothing in the
   schema for it to govern. `src/` contains no `vendor_operation` table, no `valid_from`, and no
   `valid_to`; `schema.sql` declares seven tables and none of them is an operation dimension.
   (VERIFIED — grep over `src/` for all three terms returns nothing.) The nearest thing is
   `vendor_change`, which records a *transition* between two spec versions rather than an
   operation's state at one, and whose write is an in-place update:
   `ON CONFLICT (id) DO UPDATE SET raw = EXCLUDED.raw, detected_at = now()` (`store.py:325`).
   That update is bounded — `raw->>'text'` is inside the hashed identity, so a change with different
   text is a different row — but every other field of `raw` is overwritten by whatever the last
   ingest saw, which is precisely "update a vendor-derived row in place." Either the rule is a
   commitment about a table M2 or M3 will add, in which case the rule should name it; or the ADG
   answers "what did this operation look like before the change" by replaying `vendor_change` rows
   rather than by holding versioned operation rows, in which case the rule is describing a design
   Sync did not take and should be rewritten. A rule with no referent is a rule an agent will
   eventually satisfy by inventing a table.

7. **Does `finding` want to know its evidence moved?** §3.7's `rationale_hash` is cheap, but it
   implies a policy decision the schema cannot make: when a finding's rationale changes materially,
   is that the same finding with new evidence, or a new finding? Today `ON CONFLICT DO NOTHING`
   answers "the same, and the new evidence is discarded." That is defensible for convergence and
   indefensible for a customer reading a rationale that describes traffic from three weeks ago.
