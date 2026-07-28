# Sync — The Migration Corpus

**Date:** 2026-07-25
**Status:** Built, empty. The table is `src/sync/graph/schema.sql:54`, the model is
`MigrationOutcome` in `src/sync/core/models.py`, and the remediation graph writes through
`src/sync/remediate/corpus.py` — including the abandoned attempts, which are the negative class.
The merge webhook receiver is built — `record_merge_outcome` in `src/sync/forge/webhook.py`
verifies GitHub's signature, then calls `GraphStore.set_merge_outcome` — and `pr_merged` still
stays null, because it matches a delivery to a row by `pr_number` and nothing writes that column
when the pull request opens. No real pipeline run has produced a row yet.
**Scope:** What Sync records about every remediation attempt, where each field is captured, and why the record
is safe to aggregate across customers.

## Why this exists at M0

Every other asset in Sync can be built later. This one cannot. A remediation run that completes without writing
its outcome is a labeled example destroyed at the moment it was produced, and there is no path that recovers it
— the vendor specification pair, the call-site shape, the patch attempt, the typecheck diagnostics, and the CI
verdict exist together for a few minutes and never again.

The cost of recording it during M0 is one table and a handful of writes inside nodes that already exist. The
cost of adding it at M4 is every run between now and then.

**What the corpus is for.** Not fine-tuning. Its value is *routing*: the tier cascade in the latency
architecture guesses which change kinds are mechanical enough for a deterministic codemod or a `low`-effort
model call. The corpus turns that guess into a measured prior. A change kind observed to be repaired by a
codemod and to pass CI thirty times in a row does not need a model call at all, and every such class removed
from the model path is a permanent cost and latency win that a competitor without the corpus cannot copy.

Its second use is evidence about Sync itself. Autonomous pull requests merge at roughly a third overall but at
three-quarters or better when the change is maintenance-shaped (see `2026-07-25-sync-competitive-position.md`).
Sync's entire claim is that its output sits in the upper band. Without `pr_merged`, that remains a borrowed
statistic.

## What is recorded

One row per remediation *attempt*, not per finding. A finding that fails static verification twice and succeeds
on the third try produces three rows, and the two failures are the more informative ones.

```sql
CREATE TABLE migration_outcome (
    id                            bigserial PRIMARY KEY,
    finding_id                    uuid NOT NULL,
    attempt_index                 int  NOT NULL,          -- 0-based, within the finding

    -- the vendor change. Public data. No privacy constraint applies to this block.
    vendor_id                     text NOT NULL,          -- 'stripe'
    from_version                  text NOT NULL,
    to_version                    text NOT NULL,
    change_kind                   text NOT NULL,          -- oasdiff classification id, verbatim
    change_severity               text NOT NULL,
    operation_id                  text,                   -- 'POST /v1/charges'; null when unmapped
    path_ptr                      text,                   -- JSON pointer to the field that moved

    -- the call site, as SHAPE only. See "What is deliberately not recorded".
    language                      text NOT NULL,          -- 'typescript'
    sdk_version                   text,
    symbol_shape                  text NOT NULL,          -- 'client.<resource>.<verb>(object)'
    arg_arity                     int  NOT NULL,
    arg_key_hashes                text[] NOT NULL,        -- salted; never the literal keys
    response_fields_touched_count int  NOT NULL,
    call_site_depth               int,                    -- nesting depth of the enclosing scope
    is_wrapped                    bool NOT NULL,          -- reached through a helper, not the SDK directly

    -- what was attempted
    strategy                      text NOT NULL,          -- 'codemod' | 'agent'
    tier                          int  NOT NULL,          -- 0 deterministic | 1 low effort | 2 xhigh
    edit_script                   jsonb,                  -- abstract edit operations, never a textual diff
    input_tokens                  int,
    output_tokens                 int,
    cache_read_input_tokens       int,
    wall_ms                       int  NOT NULL,

    -- what happened
    static_verify_passed          bool,
    static_verify_error_class     text,                   -- normalized tsc error code, e.g. 'TS2339'
    ci_result                     text,                   -- 'green'|'red'|'timeout'|'not_reached'
    ci_wall_ms                    int,
    terminal_status               text NOT NULL,          -- 'pr_opened'|'retrying'|'abandoned'
    abandon_reason                text,

    -- outcome, arriving days later by webhook (M1)
    pr_number                     int,
    pr_merged                     bool,
    pr_merged_at                  timestamptz,
    pr_closed_unmerged            bool,
    human_edits_before_merge      int,                    -- commits on the branch not authored by Sync

    created_at                    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON migration_outcome (vendor_id, change_kind, strategy, tier);
CREATE INDEX ON migration_outcome (finding_id, attempt_index);
```

Four columns above are specified and not built. `src/sync/graph/schema.sql:54` carries neither
`call_site_depth` nor `is_wrapped` from the call-site block, neither `ci_wall_ms` nor
`pr_closed_unmerged` from the outcome block; `finding_id` is `text` there rather than `uuid`, and
`terminal_status` is nullable. The second index is absorbed by the natural key
`UNIQUE (finding_id, attempt_index)`, which leads with the same columns. None of the four is
load-bearing for an axis `src/sync/benchmark/axes.py` computes today, which is why they were
skipped rather than missed — but a query written from this block will not run against the table.

`change_kind` is the routing key. Every question the corpus is meant to answer — *is this class of change safely
mechanical, which tier should it start at, does it merge* — is a group-by on `(vendor_id, change_kind,
symbol_shape)`.

## Where each field is captured

The remediation graph already checkpoints at every node, so each write lands in a node that exists.

| Node | Writes |
|---|---|
| `locate` | opens the row: finding, vendor change block, call-site shape block |
| `strategize` | `strategy`, `tier` |
| `patch` | `edit_script`, token counts, `wall_ms` |
| `static_verify` | `static_verify_passed`, `static_verify_error_class` |
| retry edge | closes the row with `terminal_status = 'retrying'`, opens the next `attempt_index` |
| `await_ci` | `ci_result`, `ci_wall_ms` |
| `decide` | `terminal_status`, `abandon_reason` |
| `open_pr` | `pr_number` |
| webhook (M1) | `pr_merged`, `pr_merged_at`, `pr_closed_unmerged`, `human_edits_before_merge` |

**The abandoned rows are the point.** A finding that exhausts its retry bound writes a row with
`terminal_status = 'abandoned'` and its reason. That is the negative half of the label set, it is the half a
naive implementation drops, and a corpus of successes alone cannot answer the only question worth asking of it:
which change kinds should Sync not attempt.

**`pr_merged` cannot be inferred.** It arrives days after the run, from a `pull_request` webhook on the GitHub
App that `sync.forge` already installs. A field that quietly stays null for six months destroys the metric it
exists to provide, which is why the verification section below tests the transition rather than the column.

## What is deliberately not recorded

No customer source text. Not the call site, not the patch as a diff, not the tsc message body, not file paths,
not repository or organization identifiers, not commit SHAs.

The three fields that carry the most risk of leaking source, and their constraints:

**`symbol_shape`** is a normalized skeleton, not the symbol. `stripe.charges.create({amount, currency})` becomes
`client.<resource>.<verb>(object)`. Vendor-side names are public and may be retained through `operation_id`;
customer-side identifiers never appear.

**`arg_key_hashes`** are HMACs under a per-deployment salt, never the literal argument keys. Cross-customer
comparison is therefore possible within a deployment and impossible across salts, which is the correct trade:
the routing signal needs to know *whether two call sites pass the same argument set*, never *what the arguments
are called*.

**`edit_script`** is a sequence of abstract operations against the shape, not a diff:

```json
[{"op": "rename_arg_key", "from_hash": "…", "to_hash": "…"},
 {"op": "replace_method", "from": "<verb:create>", "to": "<verb:createV2>"},
 {"op": "drop_response_field_read", "path_ptr": "/data/status"}]
```

An operation vocabulary rather than free text is what makes the corpus queryable and what keeps source out of
it. It is also the thing a future deterministic codemod is generated *from* — when one `(change_kind,
symbol_shape)` pair has produced the same edit script thirty times with a green CI every time, that script is a
codemod, promoted automatically to tier 0.

**`static_verify_error_class`** is the normalized diagnostic code (`TS2339`), never the message, because the
message contains identifiers from the customer's code.

## Why this is safe to aggregate across customers

The corpus contains public vendor facts, structural shapes with no identifiers, salted hashes, and outcome
booleans. There is no configuration under which a row reconstructs a line of a customer's source, which means
aggregation needs no contractual carve-out about training on customer code and no per-customer opt-in
negotiation. That is a deliberate design choice, made because the alternative — retaining code under an
"aggregated and anonymized" clause — is the clause enterprise security review reliably strikes.

This constraint is worth more than the extra fidelity that dropping it would buy. Sync can say, and demonstrate
in the schema, that it learns from *what happened* and never from *what the code said*.

## Sequencing

**M0.** The table, the writes through `decide`, and the tests below. `pr_merged` and friends stay null; the
columns exist so the webhook has somewhere to land.

**M1.** The `pull_request` webhook handler in `sync.forge`, backfilling merge outcome. Not earlier — there is
one pull request at M0 and its outcome can be read by looking at it.

**M2 onward.** The first query that consumes the corpus: promotion of a repeatedly-verified `(change_kind,
symbol_shape, edit_script)` triple to a tier-0 codemod. Nothing before then needs to read the table, which is
precisely why it is safe to write it now and decide what it means later.

## Package placement

`MigrationOutcome` is a contract, so it is defined in `sync.core` alongside `Finding` and `Patch`, with no
logic and no sibling import. Persistence belongs to `sync.graph`, which already owns Postgres. The writes are
issued from `sync.remediate` nodes. The webhook handler is `sync.forge`, which already holds every GitHub App
concern.

## Verification

Test-first, as everywhere else.

- **The end-to-end run writes exactly one complete row.** The M0 acceptance run asserts a single
  `terminal_status = 'pr_opened'` row exists, and that `ci_result` was populated from the real CI poll rather
  than left at a default. A test that only asserts the row exists would pass against a row of nulls.
- **Failed attempts are recorded.** A graph test that forces two static-verification failures asserts three rows
  with `attempt_index` 0, 1, 2, the first two carrying `static_verify_passed = false` and a populated
  `static_verify_error_class`.
- **Abandonment is recorded.** A test that exhausts the retry bound asserts a row with
  `terminal_status = 'abandoned'` and a non-null `abandon_reason`. This is the row most likely to be lost to an
  early return.
- **The merge webhook transitions the field.** Against a committed `pull_request` webhook payload fixture,
  assert `pr_merged` moves from null to true and `pr_merged_at` is set. Prove the handler rejects a payload for
  an unknown `pr_number` rather than silently writing nothing.
- **No source text leaks.** Given a fixture repository, assert that no text or jsonb column of any
  `migration_outcome` row contains any identifier drawn from that repository's source, and that
  `arg_key_hashes` computed under two different salts do not collide. This test is the schema's contract with
  the privacy argument above; without it the argument is a comment.
