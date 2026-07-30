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

CREATE TABLE IF NOT EXISTS vendor_change (
    id           TEXT PRIMARY KEY,
    vendor_id    TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version   TEXT NOT NULL,
    kind         TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    path_ptr     TEXT NOT NULL,
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

-- Grain: one row per repair ATTEMPT, not per finding. A finding retried three times writes
-- three rows and attempt_index says which. Counting findings by counting rows is wrong.
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

    pr_number                     INTEGER,
    pr_merged                     BOOLEAN,
    pr_merged_at                  TIMESTAMPTZ,
    human_edits_before_merge      INTEGER,

    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- The natural key. A restarted run re-recording an attempt must converge rather than
    -- inflate the corpus, and an inflated corpus silently overstates every rate computed
    -- from it.
    UNIQUE (finding_id, attempt_index)
);

CREATE INDEX IF NOT EXISTS migration_outcome_kind_idx
    ON migration_outcome (vendor_id, change_kind, strategy, tier);

-- Grain: one row per (vendor_id, operation_id, field_path, json_type, source) tuple. A shape
-- observed again increments sample_count on its row rather than adding one, which is why that
-- column exists at all: a table that appended would make every presence rate a function of how
-- often the ingest ran rather than of what the vendor sent.
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
    -- 'error-payload'|'replay'|'interceptor'
    source           TEXT NOT NULL,
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
