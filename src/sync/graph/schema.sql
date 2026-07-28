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
