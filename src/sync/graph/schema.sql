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
    indexed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
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

CREATE TABLE IF NOT EXISTS finding (
    id                TEXT PRIMARY KEY,
    detector          TEXT NOT NULL,
    call_site_id      TEXT NOT NULL REFERENCES call_site (id) ON DELETE CASCADE,
    vendor_change_id  TEXT REFERENCES vendor_change (id) ON DELETE SET NULL,
    severity          TEXT NOT NULL,
    rationale         TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'open',
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
