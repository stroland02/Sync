-- Grain: one row per position a call site has ever been indexed at, per repository. The rows
-- with `retracted_at IS NULL` are the ones the repository has at the revision last indexed, and
-- that set -- never the whole table -- is what a detector, a count or a rank is about. A query
-- here that omits the predicate reads positions the code no longer occupies.
--
-- Identity is (repo_id, path, symbol, line, col) and position is in it deliberately -- the same
-- SDK method called twice in one file is two call sites and would otherwise collapse into one
-- row. The consequence is that a call which merely shifted down the file is a *new* row, so a
-- re-index that only inserts leaves the old position asserted forever, with whatever findings
-- were raised against it. `GraphStore.replace_call_sites` is what closes that, and why an upsert
-- alone is not convergence for this table.
--
-- It retracts rather than deletes, and the foreign key is the whole reason:
-- `finding.call_site_id REFERENCES call_site (id) ON DELETE CASCADE`, so deleting a stale row
-- deletes what a run concluded about it. A ghost row is something a reader can notice and a
-- finding that vanished is not, and abandoned runs are data. So a call site that a pass stopped
-- finding keeps its row, keeps its findings, and stops being current.
--
-- The cost is that this table only grows: one row per position a call has ever occupied, and
-- nothing prunes it. That is deliberate -- a retention rule is a decision about how long a
-- conclusion stays explainable, and it is not made by whoever needed the disk. A hosted control
-- plane will have to make it.
--
-- Every query that answers about one customer must say so. `call_sites_for_operation` filters on
-- `repo_id` only when asked, and a detector that forgets finds every repository's rows.
CREATE TABLE IF NOT EXISTS call_site (
    id                   TEXT PRIMARY KEY,
    repo_id              TEXT NOT NULL,
    path                 TEXT NOT NULL,
    line                 INTEGER NOT NULL,
    col                  INTEGER NOT NULL,
    vendor_id            TEXT NOT NULL,
    operation_id         TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    args_keys            TEXT[] NOT NULL DEFAULT '{}',
    response_fields_read TEXT[] NOT NULL DEFAULT '{}',
    sdk_version          TEXT NOT NULL,
    content_hash         TEXT NOT NULL,
    -- How many loops enclose the call, counting array callbacks that iterate. Zero means the
    -- call is made once per unit of work; one means a collection becoming one vendor call
    -- each; two means quadratic. Static evidence: a loop that never executes still counts,
    -- which is why this is not interchangeable with a count from `observed_call`. A query
    -- that treats a non-zero depth as proof of volume is wrong -- it is proof of shape.
    loop_depth           INTEGER NOT NULL DEFAULT 0,
    indexed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- When a pass over this repository stopped finding the call at this position. NULL means the
    -- revision last indexed has it. Nullable and with no default because that is the only shape
    -- `apply_schema` can add to a table that already has rows, and every row it would be added
    -- to is a call site the last pass did find.
    --
    -- The first absence rather than the latest: `replace_call_sites` only stamps rows that are
    -- still current, so a row already retracted keeps the timestamp it got. "When did the graph
    -- stop seeing this call" is answerable; "which was the most recent pass that did not see it"
    -- is not, and is a question about the scan schedule rather than about the code.
    retracted_at         TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS call_site_operation_idx ON call_site (vendor_id, operation_id);

-- Grain: one row per change one vendor made between one pair of spec versions. Identity is
-- (vendor_id, from_version, to_version, kind, path_ptr, operation_id, raw->>'text'), which is the
-- tuple `GraphStore.upsert_vendor_change` hashes into `id`. The text is in it because two
-- arguments removed from one operation differ in nothing else.
--
-- This is the one source in the pipeline that does not converge, and `CLAUDE.md` names the
-- exemption rather than leaving it to be discovered: `oasdiff breaking` returns a different answer
-- on successive runs over identical bytes on both pinned versions, so these rows are at-least-once
-- and a count of them is not a measurement. `raw` keeps the vendor's own record beside our
-- interpretation of it, which is why `b29795a` could be applied to history instead of re-fetching
-- every spec pair.
CREATE TABLE IF NOT EXISTS vendor_change (
    id           TEXT PRIMARY KEY,
    vendor_id    TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    path_ptr     TEXT NOT NULL,
    -- 'breaking'|'warning'|'deprecation'|'addition'|'info' -- `sync.core.Severity`, and the same
    -- vocabulary `finding.severity` and `migration_outcome.change_severity` hold. All three are
    -- typed by that one alias; `tests/test_severity_vocabulary.py` asserts the identity rather
    -- than restating the members here a fourth time.
    --
    -- Named in a comment and not declared as a CHECK, which means Postgres will store a severity
    -- no build of this code can read back. That is a property of this schema rather than an
    -- oversight, and three measurements decide it:
    --
    -- A CHECK riding on a column definition never reaches a database that already has the
    -- column. `apply_schema` converges an existing database by re-issuing each definition as
    -- `ADD COLUMN IF NOT EXISTS`, and Postgres skips the whole item -- any constraint on it
    -- included -- when the column is there. The constraint would land on every database created
    -- after the edit, where every write already goes through a validated model, and on none of
    -- the ones that predate it, which is the only place a hand-written row can be. Absent and
    -- believed present is worse than absent.
    --
    -- Reaching those databases means a table-level `ALTER TABLE ... ADD CONSTRAINT`, which costs
    -- the two rules this file is held to. A bare ADD CONSTRAINT is not idempotent -- 42710 on the
    -- second apply -- and it is refused outright by a table already holding a violating row,
    -- 23514, so it would have to be DROP-then-ADD with NOT VALID: tolerating history the way
    -- `finding.binding_rung`'s `unattributed` default does.
    --
    -- What settles it is the coupling. `Severity`'s own comment records that widening it moved no
    -- contract precisely because nothing enumerates it -- the MCP tool schemas type severity as a
    -- bare string and this file stores TEXT. Ten columns here have a closed vocabulary behind
    -- them, four already name it in a comment exactly as this does, and not one is constrained in
    -- DDL. A CHECK on severity alone would make this file a second declaration of a vocabulary
    -- `sync.core` owns, and would close one of the four shapes that reach the same silence:
    -- `source` outside its own literal, a `raw` that is not an object, and any field a later model
    -- requires that the row does not carry all arrive at it too.
    --
    -- The failure that costs something is on the read and it is not in this package: every read in
    -- `GraphStore` raises on such a row, and `sync.mcp.tools._change_for` is where the raise
    -- becomes an empty answer indistinguishable from a change that had no diff.
    -- `docs/superpowers/reports/2026-07-30-a-row-the-model-refuses.md` carries the write routes
    -- and the argument for repairing it there.
    severity     TEXT NOT NULL,
    source       TEXT NOT NULL,
    raw          JSONB NOT NULL DEFAULT '{}'::jsonb,
    detected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Grain: one row per CLAIM, per detector, per call site -- identified by
-- (detector, call_site_id, vendor_change_id, claim). One detector saying two things about one
-- call site is two rows, and `claim` is what says which. Counting a detector's findings by
-- counting call sites undercounts wherever a detector makes more than one claim about one.
--
-- The grain was never written down, and three detectors violated it without anyone noticing:
-- `observed-drift`, `status-rate` and `efficiency` all emitted several findings per call site
-- with no discriminator, so the insert below kept whichever arrived first and discarded the
-- rest in silence. That is what `claim` exists for.
--
-- `claim` names the KIND of claim and never its wording. A discriminator carrying a live count
-- -- "called 40 times" -- would make DETECT write a fresh row on every run instead of
-- converging, which is the same silent failure with the opposite sign.
CREATE TABLE IF NOT EXISTS finding (
    id                TEXT PRIMARY KEY,
    detector          TEXT NOT NULL,
    claim             TEXT NOT NULL,
    call_site_id      TEXT NOT NULL REFERENCES call_site (id) ON DELETE CASCADE,
    vendor_change_id  TEXT REFERENCES vendor_change (id) ON DELETE SET NULL,
    -- `sync.core.Severity`, the same five members `vendor_change.severity` names, and TEXT for the
    -- reason argued there. A detector chooses this rather than copying it: four of the five pick a
    -- constant, and `vendor_change` passes the vendor's own grading through.
    severity          TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open',
    -- Which binding this claim rests on, so a false positive can be attributed to the binder
    -- that produced it. A column and not a join, which is what `graph-grain.md` requires of any
    -- row whose content depends on a binding.
    --
    -- The default serves rows written before this column existed and nothing else. A bare NOT
    -- NULL cannot be added to a populated table and a backfilled rung would be invented, which
    -- is the failure this column exists to prevent. So history answers `unattributed`: a value
    -- no binder emits and which `BindingRung` deliberately excludes.
    --
    -- `Finding.binding_rung` defaults to it too. Requiring the field would fail a forgetful
    -- detector at construction, which is stronger; it also invalidated every `Finding` fixture
    -- in the suite -- 32 files, 153 failures -- and repairing those would have written a rung
    -- into fixtures that do not reason about one. `unattributed` on a row written after this
    -- shipped is still a bug; it is one no type catches, and the five detector tests are what
    -- stand in for that.
    binding_rung      TEXT NOT NULL DEFAULT 'unattributed',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS finding_status_idx ON finding (status);

-- Grain: one row per repair ATTEMPT, per run kind, not per finding. A finding retried three
-- times writes three rows and attempt_index says which. Counting findings by counting rows is
-- wrong.
--
-- A run has identity too: `is_rehearsal` is `true` for a zero-remote `sync rehearse` run against
-- a fixture repository and `false` for a real pipeline run, and it is in the natural key rather
-- than a filter bolted onto every reader. Before it existed the key was `(finding_id,
-- attempt_index)` alone, so a rehearsal and a production run that happened to process the same
-- finding at the same attempt index against one shared database collided -- and since
-- `sync rehearse --dsn` defaults to the exact DSN `sync run` does, that is not a hypothetical.
-- `ON CONFLICT DO NOTHING` kept whichever wrote first and silently dropped the other; when the
-- other was the production row, the pull request it opened never reached `merge_rate` or
-- `counts.pull_requests_opened` (B79). `GraphStore.migration_outcomes` and every reader built on
-- it filter `is_rehearsal` back out, because a rehearsal row belongs in this table -- it still
-- costs a repair attempt worth recording -- and nowhere a corpus-wide rate is computed.
--
-- Nothing here identifies a customer: the symbol is a shape, argument keys are salted digests,
-- and neither the diff nor the file path is stored. That is what makes the table safe to
-- aggregate across customers, which is the only thing that makes it worth keeping.
--
-- It cannot be backfilled. Every attempt processed before this table existed is lost.
CREATE TABLE IF NOT EXISTS migration_outcome (
    id                            BIGSERIAL PRIMARY KEY,
    finding_id                    TEXT NOT NULL,
    attempt_index                 INTEGER NOT NULL,

    vendor_id                     TEXT NOT NULL,
    from_version                  TEXT NOT NULL,
    to_version                    TEXT NOT NULL,
    change_kind                   TEXT NOT NULL,
    -- `sync.core.Severity` again, copied from the change this attempt was made against rather than
    -- graded here, and TEXT for the reason argued on `vendor_change.severity`. Not widened for the
    -- corpus: an attempt against a change of a severity the model cannot name is not a wider
    -- grading, it is an unreadable row, and this table is the one that cannot be backfilled.
    change_severity               TEXT NOT NULL,
    operation_id                  TEXT,
    path_ptr                      TEXT,

    language                      TEXT NOT NULL,
    sdk_version                   TEXT,
    symbol_shape                  TEXT NOT NULL,
    arg_arity                     INTEGER NOT NULL,
    arg_key_hashes                TEXT[] NOT NULL DEFAULT '{}',
    response_fields_touched_count INTEGER NOT NULL,

    strategy                      TEXT NOT NULL,
    tier                          INTEGER NOT NULL,
    -- Which decision-table row assigned `tier`, at this table's grain of one row per attempt.
    -- A retried attempt that routed differently from its predecessor carries its own value
    -- rather than collapsing into one, which is what makes "tier 0 was wrong for this change
    -- kind" a query instead of an archaeology project.
    --
    -- 'unrouted' means the table had no jurisdiction over the finding, which is a fact about
    -- the finding. NULL is reserved for a row this column was never written for: the three
    -- attempts that predate it, which cannot be backfilled because the table they routed on
    -- has changed since.
    routing_row                   TEXT,
    edit_script                   JSONB,
    input_tokens                  INTEGER,
    output_tokens                 INTEGER,
    cache_read_input_tokens       INTEGER,
    wall_ms                       INTEGER NOT NULL,

    static_verify_passed          BOOLEAN,
    static_verify_error_class     TEXT,
    ci_result                     TEXT,
    terminal_status               TEXT,
    abandon_reason                TEXT,
    -- The coded companion beside the prose above, not instead of it (B128). One of the values
    -- `sync.remediate.state.AbandonReasonCode` declares, written by `make_abandon` at the same
    -- point it writes `abandon_reason`. Does not change this table's grain: it is one more
    -- attribute of the row the natural key below already identifies, not a new dimension a row
    -- varies over, so the unique constraint and `ON CONFLICT` clause are unchanged. NULL on a
    -- row from before this column existed and on every row that is not an abandonment.
    abandon_reason_code           TEXT,

    pr_number                     INTEGER,
    pr_merged                     BOOLEAN,
    pr_merged_at                  TIMESTAMPTZ,
    human_edits_before_merge      INTEGER,

    -- See the table's grain comment. `NOT NULL DEFAULT false` is what lets this land on a
    -- database that already has rows: every one of them predates `sync rehearse` and so was a
    -- production run, which is the only value history can honestly be given.
    is_rehearsal                  BOOLEAN NOT NULL DEFAULT false,

    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The natural key. A restarted run re-recording an attempt must converge rather than
    -- inflate the corpus, and an inflated corpus silently overstates every rate computed
    -- from it. `is_rehearsal` joined it in B79, so a rehearsal and a production run at the same
    -- finding and attempt index no longer collide -- widening this constraint is not something
    -- `GraphStore.apply_schema` can carry to a database that already has the old one; see its
    -- docstring's "What this does not express."
    UNIQUE (finding_id, attempt_index, is_rehearsal)
);

CREATE INDEX IF NOT EXISTS migration_outcome_kind_idx
    ON migration_outcome (vendor_id, change_kind, strategy, tier);

-- Grain: one row per (vendor_id, operation_id, field_path, json_type, source) tuple. A shape
-- observed again increments sample_count on its row rather than adding one, which is why that
-- column exists at all: a table that appended would make every presence rate a function of how
-- often the ingest ran rather than of what the vendor sent.
--
-- **sample_count means one thing per source class and merges accordingly**, and it is the
-- sentence above that forces the split rather than an exception to it. For a traffic source the
-- write is a response somebody received, so a second write is a second sample and the counter
-- adds. For a synthetic source -- `sync.graph.sources.SYNTHETIC_SOURCES`, the rows Sync
-- constructed from a published specification -- a second write is the ingest running again over
-- the same constructed body, so the counter holds: it is the largest single claim made about the
-- row rather than the sum of the claims. One row still means one shape; for a synthetic source
-- it also means one sample, at any repetition count.
--
-- The replay tier is what forces it. A failed replay re-enters `patch` and MAX_STATIC_ATTEMPTS
-- is 3, so one finding offers the same synthesized body three times, and ten findings over one
-- operation would carry it past the sample floor the drift detector reads. A run key on the row
-- does not fix that -- it changes which row the addition lands in, and the retry writes the same
-- key twice. Convergence under re-execution is a property of the merge.
--
-- Only the counter is held. Every other column merges identically for both classes, so a
-- synthetic row still records that the shape was seen, that the field can be null, which
-- published members were exercised, and over what window.
--
-- Values are never stored, only shape -- paths, types, nullability, counts. The single
-- exception is an enum member the vendor's published specification names, because a vendor enum
-- is public data. A string the specification does not name is a customer's data and is
-- discarded before it reaches this table. That is a threat-model commitment, and it is tested
-- rather than commented.
--
-- It cannot be backfilled. Every response seen before this table existed is a baseline sample
-- permanently lost, which is why the schema is fixed now and the detector that reads it is not
-- built until M2.
CREATE TABLE IF NOT EXISTS observed_shape (
    id               BIGSERIAL PRIMARY KEY,
    vendor_id        TEXT NOT NULL,
    operation_id     TEXT NOT NULL,
    -- A JSON Pointer into the response body, '/data/status'. Not a URL path: vendor_change.path_ptr
    -- addresses the operation, this addresses a field inside its response, and a join written as
    -- though they were the same form matches nothing.
    field_path       TEXT NOT NULL,
    -- 'string'|'number'|'boolean'|'object'|'array'|'null'
    json_type        TEXT NOT NULL,
    -- Evidence, not a current reading: one null response proves the field can be null and a
    -- thousand non-null ones afterwards do not unprove it.
    nullable_seen    BOOLEAN NOT NULL DEFAULT FALSE,
    -- Only members the published specification names, and only those actually observed.
    spec_enum_values TEXT[] NOT NULL DEFAULT '{}',
    -- 'error-payload'|'replay'|'interceptor'. The mechanism that produced the row, not a vendor:
    -- Sentry and Datadog both write 'error-payload'. Only some of these are responses a vendor
    -- actually sent -- 'replay' rows are a specification restated through the customer's code --
    -- and `GraphStore.observed_shapes` answers with traffic alone unless asked for everything.
    -- `sync.graph.sources` holds which is which and must be extended with this list.
    source           TEXT NOT NULL,
    -- Samples, not writes. What that counts depends on the source class -- see the grain note.
    sample_count     INTEGER NOT NULL DEFAULT 1,
    first_seen       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The natural key. json_type is in it because a field that used to arrive as a string and
    -- now arrives as a number is the unpublished change this table exists to catch, and merging
    -- those two into one row would erase it. source is in it because the sources have different
    -- fidelity -- error-payload shapes are biased toward failures -- and merging them would let
    -- a biased sample masquerade as a baseline.
    --
    -- No separate read index: this constraint's btree leads with (vendor_id, operation_id),
    -- which is how the baseline is read.
    UNIQUE (vendor_id, operation_id, field_path, json_type, source)
);

-- Grain: one row per (repo_id, vendor_id, operation_id, server_address, http_method, trace_id)
-- -- one unit of work's use of one operation against one host. NOT one row per span. Three
-- calls to one operation inside a single request are one row whose call count is three, so a
-- query counting vendor calls by counting rows undercounts precisely where the efficiency
-- detector looks.
--
-- The trace is in the grain and that is the whole decision. Three of the four efficiency
-- findings -- a call inside a loop, a page walked at the default size, the same call repeated
-- with no cache -- are all the same question: how many times did ONE unit of work call this?
-- A time-bucketed rollup answers "how many calls this hour", which cannot distinguish one
-- request making two hundred calls from two hundred requests making one. That distinction is
-- the finding. A rollup is derivable from these rows at any time; these rows are not
-- recoverable from a rollup, and this table cannot be backfilled, so the resolution is kept
-- now and aggregated later rather than the reverse.
--
-- The cost is honest: for traffic where most requests make one vendor call, this compresses
-- barely at all, and a high-volume tenant will want a windowed rollup on top. That is a view to
-- add, not a grain to have chosen.
--
-- `spans` is a JSONB map keyed by span id, and it is what makes ingest idempotent. OTLP
-- delivery is at-least-once and a collector re-sends whatever is still buffered rather than the
-- batch it sent before, so a batch-level dedup misses the overlapping-subset case that actually
-- happens. `||` on a JSONB object is last-write-wins per key, so folding a span already present
-- changes nothing. Every count is derived from this map rather than stored beside it, which is
-- why no counter here can drift: there is no counter.
--
-- Nothing here identifies a customer. The request URL never reaches a column: a correlated call
-- keeps the vendor's own published path template, which is public, and every call keeps a
-- salted digest of the URL whose only purpose is to say whether two calls went to the same
-- place. An uncorrelated call keeps no path at all, which means fixing the correlation later
-- requires re-ingesting rather than reinterpreting these rows.
CREATE TABLE IF NOT EXISTS observed_call (
    id             BIGSERIAL PRIMARY KEY,
    repo_id        TEXT NOT NULL,
    vendor_id      TEXT NOT NULL,
    -- Empty when nothing could correlate the request. Empty rather than NULL because it is in
    -- the natural key, and NULL is not equal to NULL in a unique index -- every uncorrelated
    -- span would insert a fresh row and the table would grow without converging.
    operation_id   TEXT NOT NULL,
    -- 'observed' for a binding this table produced, 'unresolved' when there is no binding. The
    -- rungs a call site can carry are 'static' and 'resolved'; a span is a third kind of
    -- evidence and says so, because a false positive that cannot be attributed to a rung cannot
    -- be fixed.
    binding_rung   TEXT NOT NULL,
    server_address TEXT NOT NULL,
    http_method    TEXT NOT NULL,
    trace_id       TEXT NOT NULL,
    -- The vendor's published template, '/v1/charges/{charge}'. Never the request path: that
    -- carries resource identifiers. Empty for an uncorrelated call, which has no template.
    url_template   TEXT NOT NULL DEFAULT '',
    -- span_id -> {"target": <salted digest>, "status": <int|null>, "resend": <int>}
    spans          JSONB NOT NULL DEFAULT '{}'::jsonb,
    first_seen     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The natural key. server_address is in it because one operation reached through two hosts
    -- is two integrations -- a live key and a sandbox, or a regional endpoint -- and merging
    -- them would average a test workload into a production bill. http_method is in it because
    -- operation_id is empty for uncorrelated calls, and without the method every uncorrelated
    -- request to one host in one trace would collapse into a single row.
    UNIQUE (repo_id, vendor_id, operation_id, server_address, http_method, trace_id)
);

-- The detector reads by repository and operation across traces; the unique constraint's btree
-- leads with (repo_id, vendor_id, operation_id) and serves that. This index serves the other
-- direction -- everything one unit of work did -- which is how a loop finding is evidenced.
CREATE INDEX IF NOT EXISTS observed_call_trace_idx ON observed_call (repo_id, trace_id);

-- Grain: one row per (repo_id, vendor_id, operation_id, source, status_class, window_start,
-- window_end) -- one operation's failures of one class, over one period somebody queried, in one
-- repository. NOT one row per error and NOT one row per Sentry issue. `error_count` is how many
-- errors the window held and `issue_count` is how many distinct groups produced them, so a query
-- counting errors by counting rows is wrong by three orders of magnitude and a query reading
-- `issue_count` as a volume is wrong the other way.
--
-- The window bounds are in the grain because they are a fact about the *query*, not about the
-- errors. A window derived from what happened to fail shrinks to the extent of the failures, so
-- an hour with two errors and an hour with two thousand both read as a busy minute and no two
-- windows are comparable. Only the caller knows the period it asked Sentry for, so the caller
-- supplies it and a mismatch between the two is undetectable here -- an export queried over a
-- different period files its counts under a window they did not happen in.
--
-- **This is a numerator with no denominator, and it must never be read as a rate.** Sentry sees
-- failures and nothing else: it cannot say how many requests were made, so `error_count / N` has
-- no N in this table and never will. `observed_call` is where the denominator lives, at a
-- different grain from a different sample. Joining them is real work and it is deliberately not
-- done here; what these rows support unaided is a comparison of one window against another.
--
-- `status_class` is '4xx', '5xx', '2xx' or '' -- the hundreds bucket of the response the
-- representative event recorded, and empty when it recorded none. It is in the key rather than
-- summed away because a 402 is a declined card and a 503 is the vendor being down, and pooled
-- they are a count that describes neither integration. Empty is a third answer and not a missing
-- one: a `TypeError` reading a field off a successful response is the failure a removed response
-- property causes, and it carries no status at all. The class is read from one event and
-- attributed to the whole group's count -- Sentry groups by fingerprint so that is usually right
-- and it is not guaranteed.
--
-- It cannot be backfilled: an error tracker's retention is finite and a window that has aged out
-- is gone. That is why the resolution is chosen now and aggregated later rather than the reverse.
CREATE TABLE IF NOT EXISTS observed_error_window (
    id            BIGSERIAL PRIMARY KEY,
    repo_id       TEXT NOT NULL,
    vendor_id     TEXT NOT NULL,
    operation_id  TEXT NOT NULL,
    -- Which binding the count rests on, so a wrong attribution can be traced to the binder that
    -- made it. A column and not a join, for the reason `finding.binding_rung` is one.
    --
    -- Non-empty always, and there is no 'unresolved' counterpart to `observed_call`'s. An issue
    -- nothing correlates is not this vendor's, and a Sentry project is the customer's entire
    -- error stream rather than a pre-filtered one, so recording those would make this table a
    -- copy of their error volume filed under no operation.
    binding_rung  TEXT NOT NULL,
    -- 'error-tracker-group' today, and the only writer. The mechanism rather than a vendor, the
    -- way `observed_shape.source` names its values -- Sentry and Datadog both write
    -- 'error-payload' there and both write this. In the key for the reason that column has it:
    -- a count an error tracker's own grouping produced and a count derived from spans have
    -- different sampling stories, and merging them lets one masquerade as the other. That
    -- disagreement is the point -- two independent sources differing about one operation is
    -- information about the correlator, and with one source there is nothing to disagree with.
    -- The same argument refuses a per-product value: two trackers grouping the same failures are
    -- one sampling story, and splitting them would put one window's errors in two rows that any
    -- consumer summing rows would add together.
    source        TEXT NOT NULL,
    status_class  TEXT NOT NULL,
    window_start  TIMESTAMPTZ NOT NULL,
    window_end    TIMESTAMPTZ NOT NULL,
    error_count   INTEGER NOT NULL,
    -- How many distinct Sentry groups the count came from. Not recoverable from `error_count`,
    -- and it separates one broken call path from a vendor refusing everything.
    issue_count   INTEGER NOT NULL,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The natural key. `binding_rung` is deliberately outside it, exactly as it is outside
    -- `finding`'s: the rung describes the binding a count rests on rather than which count it is,
    -- so a correlator that improves must converge on the row it already wrote instead of adding a
    -- second one that double-counts the window.
    UNIQUE (repo_id, vendor_id, operation_id, source, status_class, window_start, window_end)
);

-- Grain: one row per repository. Not per run, and not per revision -- context is what stays
-- true of a checkout while the code changes underneath it, and a row per revision would make
-- the prompt's context a function of when the last index ran rather than of what the
-- repository is.
--
-- `source` names the mechanism that produced the body, as `observed_shape.source` does and for
-- the same reason: a patch traceable to bad context must be traceable to *which* bad context.
-- `seeded-file` is the customer's own committed `.sync/context.md`. `operator` is a human
-- through the console or the CLI. Membership is positive -- a source added and left
-- unclassified is absent from the prompt rather than silently inside it.
--
-- Sync never writes `.sync/context.md` back. A `seeded-file` row is a copy, the file is the
-- original, and every index re-seeds. An operator edit to a seeded row is therefore overwritten
-- on the next index. That precedence is deliberate: when Sync and the customer disagree about
-- what is true of the customer's repository, the customer wins.
--
-- No foreign key to `call_site`. Context may precede an index, and a repository Sync has never
-- indexed is one an operator may still describe.
CREATE TABLE IF NOT EXISTS repo_context (
    repo_id                TEXT PRIMARY KEY,
    body                   TEXT NOT NULL,
    source                 TEXT NOT NULL,
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    telemetry_attached_at  TIMESTAMPTZ
);

-- Grain: one row per repository.
--
-- Automation and merge settings for agent-opened pull requests against this repository.
-- `merge_policy`: 'never' | 'when_checks_pass'. Immediate merge without verification is refused.
-- `merge_method`: 'squash' | 'merge' | 'rebase'.
-- `base_branch`: target base branch (default: 'main').
CREATE TABLE IF NOT EXISTS repo_settings (
    repo_id                 TEXT PRIMARY KEY,
    merge_policy            TEXT NOT NULL DEFAULT 'when_checks_pass',
    merge_method            TEXT NOT NULL DEFAULT 'squash',
    base_branch             TEXT NOT NULL DEFAULT 'main',
    merge_policy_refusals   JSONB NOT NULL DEFAULT '{"immediate": "Refused: violates invariant ''nothing reaches a pull request unverified''"}'::jsonb,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Grain: one row per attempt (not per adapter).
--
-- Identity is (vendor_id, attempted_at, COALESCE(from_version, ''), COALESCE(to_version, ''))
-- or id. The distinction this exists to make is *never-asked* apart from *nothing-new*, and
-- *clean-decline* apart from *fetch-failure*. `vendor_change` records only results, so an
-- adapter polled hourly that found nothing new for a week is indistinguishable from one
-- whose fetch has been 403ing for a week. Both render as an old `last_change_at`.
--
-- `reason_code` is from the closed seventeen-member vocabulary in `sync.signals.intake_attempt`.
-- Like `abandon_reason_code`, a promise to learn from failures and aggregate statistics across
-- adapters requires a closed vocabulary rather than free text. Free text is retained only in `detail`
-- as diagnostic detail.
CREATE TABLE IF NOT EXISTS intake_attempt (
    id            TEXT PRIMARY KEY,
    vendor_id     TEXT NOT NULL,
    attempted_at  TIMESTAMPTZ NOT NULL,
    outcome       TEXT NOT NULL,
    reason_code   TEXT,
    detail        TEXT,
    changes_count INTEGER NOT NULL DEFAULT 0,
    from_version  TEXT,
    to_version    TEXT,
    source        TEXT,
    duration_ms   DOUBLE PRECISION,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (vendor_id, attempted_at, from_version, to_version)
);

CREATE INDEX IF NOT EXISTS intake_attempt_vendor_idx ON intake_attempt (vendor_id, attempted_at DESC);

-- Grain: one row per DISMISSAL of one finding by one person at one time. Not a property of the
-- finding, and that distinction is the whole decision (owner decision 45, 2026-08-18): a finding
-- dismissed and later un-dismissed has two rows and the current state is the latest one, because
-- a column would overwrite and the console could not then show that somebody changed their mind.
-- Counting dismissed findings by counting rows here is wrong for exactly the reason it is wrong
-- on `migration_outcome`.
--
-- `reason` is NULL on an un-dismissal and one of the closed vocabulary otherwise. The vocabulary
-- is closed for the same reason `abandon_reason_code` is: a promise to learn from dismissals
-- needs a schema that can answer the question, and free text cannot be aggregated. The values are
-- Sync's own reviewers' -- `interface-originality.md` takes a vocabulary's shape and never its
-- values.
--
-- `false_positive` is the only honest source of detector accuracy, so it must stay separable
-- rather than pooled with the other three. That is why the reason is a column here and not a
-- boolean beside a note.
--
-- Dismissal is not deletion: the finding row is untouched and stays listed, filtered out by
-- default. A read surface can only offer that filter because the finding is still there.
CREATE TABLE IF NOT EXISTS finding_dismissal (
    id           BIGSERIAL PRIMARY KEY,
    -- Deliberately NOT a foreign key to `finding`, and no other durable table has one either.
    -- `finding` is re-derived: a scan truncates it and writes it again. A FK here both blocks
    -- that truncate outright (`cannot truncate a table referenced in a foreign key constraint`)
    -- and, with the cascade, would delete every dismissal a human recorded on every index run --
    -- silently undoing the one thing decision 45 exists to preserve. Finding ids are stable
    -- across re-derivation, because `insert_finding` hashes
    -- (detector, call_site_id, vendor_change_id, claim), so the key still names the same finding
    -- after the row is rebuilt. `tests/test_scan_preserves_durable_rows.py` is what caught it.
    finding_id   TEXT NOT NULL,
    -- NULL means this row un-dismissed the finding. A reason is required to dismiss and
    -- meaningless to restore, and `record_dismissal` enforces the pairing.
    reason       TEXT,
    -- Who, as recorded by whatever authenticates the write. Not nullable: a dismissal nobody can
    -- be attributed to is not reviewable, and the point of keeping history is that a reader can
    -- ask who decided.
    actor        TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS finding_dismissal_latest_idx
    ON finding_dismissal (finding_id, created_at DESC);
