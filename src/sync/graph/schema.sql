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
