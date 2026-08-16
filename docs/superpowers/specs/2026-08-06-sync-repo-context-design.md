# Sync — Per-Repository Context

**Date:** 2026-08-06
**Status:** Approved design, not yet built.
**Branch:** written independently on both `repo-context` (based on `178ff7b`, the console
line's tip) and `superlog-reference` (based on `origin/main`). Both landed on `main` at the same
merge on 2026-08-16, which is why this document has one text rather than two — `main` now carries
`sync.dashboard.graph_views` and the whole console line, so nothing in this design is blocked.
**Scope:** How a durable statement about a customer's repository reaches the patch agent, who
may write one, and what the MCP server says about it.

## Context

Every remediation run starts cold. `build_patch_prompt` assembles the vendor change, the call
site and the required edit, and nothing else — so an agent rediscovers the same facts about a
repository on every finding: which package manager the lockfile names, which directories are
generated, which conventions the codebase keeps. The facts are stable and the rediscovery is not
free.

`CLAUDE.md` sets the toll: **every agent must shorten the critical path or improve a result.**
This design pays it twice. Facts supplied are facts not derived, and the section sits in the
prompt's stable prefix, so a retry re-reads it from cache rather than paying for it again.

Two constraints shaped every decision below.

**The MCP tool surface is frozen.** `sync.mcp.tools` publishes four tools, `GraphReader` pins
the signatures of `all_vendor_changes` and `open_findings`, and
`tests/golden/tool_schemas.json` fails the build on a removal or a rename. When the console
needed repository-scoped vendor findings it gained `graph_views.vendor_findings` rather than a
narrower `whats_at_risk`. A question the graph can answer that the frozen surface cannot reach
is a new reader, never a fifth tool. This design adds no tool.

**Sync never writes to the customer's repository.** The boundary that `propose_patch` stops at
is the same one here. Nothing in this design puts a byte in a customer's checkout.

## Decisions

| Decision | Choice | Consequence |
|---|---|---|
| Where context lives | `repo_context` in the graph store | One read path; no writes to the customer's tree |
| Who may author it | An operator, or the customer's own committed file | The agent reads; it does not yet write |
| Precedence | A committed `.sync/context.md` wins | The customer keeps authority whenever they want it |
| Attribution | A `source` column, not a rung | Context is not a binding and must not borrow the ladder |
| Reaching an agent | A resource and an `instructions` field | Both are MCP primitives that are not tools |
| Oversize input | Refused, never truncated | Prose cut mid-sentence reads as complete and is not |

## Modules

Four, each with one purpose.

| Module | Owns | Depends on |
|---|---|---|
| `sync.core.models.RepoContext` | The type | Nothing |
| `sync.graph.store` (two new methods) | Persistence and reads | Postgres |
| `sync.context` (new package) | The seed file and the prompt section | `sync.core` alone |
| `sync.dashboard.graph_views.repo_context` | The console's view | `GraphStore` |

`RepoContext` carries the table's four columns and nothing else: `repo_id`, `body`, `source`,
`updated_at`.

`sync.context` knows a file format and a prompt section. It knows nothing about Postgres and
imports no sibling that does — the same shape as `sync.telemetry`, which knows OTLP and HTTP and
no vendor. It returns data and persists nothing; every write goes through `GraphStore`, and the
caller holds both. The import-linter contract in `pyproject.toml` must gain `sync.context` under
`forbidden_modules`, or `sync.core` could import it and the contract would pass.

## The table

```sql
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
CREATE TABLE IF NOT EXISTS repo_context (
    repo_id     TEXT PRIMARY KEY,
    body        TEXT NOT NULL,
    source      TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

The natural key is `repo_id` and the conflict clause is `ON CONFLICT (repo_id) DO UPDATE`.
The table converges on re-run and claims no exemption from
`2026-07-27-sync-pipeline-discipline.md`.

No foreign key to `call_site`. Context may precede an index, and a repository Sync has never
indexed is a repository an operator may still describe.

### Why `source` and not a rung

`CLAUDE.md` requires every binding to carry the rung it came from — `static`, `resolved` or
`observed` — and refuses an unattributed finding. A fourth rung was considered and rejected. A
rung describes how a binding between code and a vendor operation was established. Context
establishes no binding, and borrowing the ladder would put prose on a scale built for evidence.

`source` is the weaker and correct instrument. It attributes without claiming.

## Reaching the agent

`GraphStore` gains `repo_context(repo_id) -> RepoContext | None` and
`upsert_repo_context(context) -> None`. `GraphReader` is a structural Protocol over
`all_vendor_changes` and `open_findings`; a class satisfies it by having those methods, not by
having only those. Nothing frozen moves.

`build_patch_prompt` gains a trailing parameter with a default:

```python
def build_patch_prompt(finding, change, site, diagnostics="", repo_context="") -> str:
```

The section renders between `Why this matters` and `_SCOPE_RULES`. The repository is described
before the edit is constrained, so the rules keep the last and strongest position.

**An empty context renders no section.** Not an empty heading — nothing. With no row the prompt
is byte-identical to today's, so every existing assertion on `build_patch_prompt` holds without
an edit and the diff is provably additive.

Section order stays load-bearing. Everything above the diagnostics block is stable across
retries of one finding, and context is stable across all of them, so the cacheable prefix grows
rather than moving.

## Writing

`POST /api/repos/{repo_id}/context`, carrying `{"body": "..."}`, writing `source='operator'`.

This is the first write route on `sync.api.app`; every route there today is a GET. The module's
claim that the transport holds no logic survives it. The handler checks that `body` is a
non-empty string within the cap and calls one method; the surface does the rest.

The CLI gains `sync context set --repo-id X --body -` and `sync context show --repo-id X`,
matching how `ingest` and `shapes` already take `--repo-id` and read `-` as stdin.

## Seeding

`sync.context.read_seed(local_path) -> str | None` returns the contents of
`<local_path>/.sync/context.md`, or `None` when the file is absent, empty, unreadable, or over
the cap. It touches no database. INDEX calls it and, on a string, calls
`GraphStore.upsert_repo_context` with `source='seeded-file'`. Splitting the read from the write
is what keeps `sync.context` free of Postgres.

The file is read with `encoding="utf-8"` passed explicitly, which `CLAUDE.md` requires and which
no ASCII fixture in this repository would catch the absence of.

Shallow clones carry the file; `--depth 50` does not exclude it. A `--repo` local checkout
carries it too. Nothing writes it back.

## Failure

| Case | Behaviour |
|---|---|
| No row | No prompt section. Not an error. |
| Seed file empty or whitespace | No row written. Absence and emptiness stay one state. |
| Seed file unreadable, or not UTF-8 | Logged, run continues, no context. |
| Body over the cap | Refused. 400 at the route; a log naming the path and the limit at the seed. |
| `repo_id` unknown to the graph | Allowed. |
| Concurrent writes | Last wins, through the conflict clause. |

Two of these are the design rather than defensive detail.

**An unreadable seed file must never abandon a run.** Context improves a run; it is not a
precondition for one. A malformed optional file that abandoned remediation would make adopting
this feature strictly riskier than ignoring it.

**Oversize input is refused and never truncated.** The cap is 8000 characters, counted on the
decoded string rather than on bytes, so a body of accented prose is not silently shorter than an
ASCII one. Prose cut mid-sentence and handed to an agent that edits code is worse than no prose
at all, because it reads as a complete statement and is not one.

## MCP

Two changes, and neither is a tool.

**`instructions` on the `initialize` result.** The MCP specification defines the field on
`InitializeResult` in revision `2025-06-18`, which is what `PROTOCOL_VERSION` already pins. It
sits beside `capabilities` and `serverInfo`, and the golden tool-schema file never sees it. The
text states what the graph answers and that a repository may carry context; it names no tool
that does not exist.

**`sync://context/{repo_id}` as a resource template.** `sync.mcp.resources` already serves
`sync://feed/{vendor}` through `resource_templates_as_data()`. Resources are a protocol
primitive separate from tools, and they do not pass through `sync.mcp.registry`, which is what
the frozen-four rule governs. An agent gains read access to repository context through the
primitive that already exists for this shape of thing, and no schema grows.

## Verification

Two claims are checkable rather than argued, and both concern landing without disturbing anyone.

**`tests/golden/tool_schemas.json` is never regenerated.** The test passes with the file
untouched. A design that required regenerating it would be the wrong design, because that file
is the tripwire on the frozen four.

**`build_patch_prompt` with no context is byte-equal to today's output.** Asserted against the
current text, not against a rewritten fixture.

| Area | Test |
|---|---|
| Import boundary | `sync.context` added to `forbidden_modules`; the contract still passes |
| Schema | An aged database gains `repo_context`, asserted by a write, in `test_schema_convergence.py` |
| Prompt | Section present and correctly positioned when context exists |
| Seed | Present, absent, empty, oversize, and non-UTF-8 bytes |
| Precedence | Re-indexing overwrites an operator edit to a `seeded-file` row |
| MCP | `initialize` carries `instructions`; the templates list carries `sync://context/{repo_id}`; `tools/list` is unchanged |
| API | POST 200, POST empty 400, POST oversize 400, GET |

The non-UTF-8 case uses real non-ASCII bytes. Every fixture in this repository is ASCII, so an
ASCII fixture would assert nothing about the encoding argument it is there to protect.

Database tests inherit the per-worker database from `conftest`. Nothing here makes a network or
a model call, so nothing here carries the `e2e` marker.

## What this does not do

**No agent writes context.** `source` ships with `seeded-file` and `operator` and no third
value. An agent recording what it learned across runs is a separate piece — memory, not context
— and building its write path here would be scope creep. `sync.graph.sources` establishes the
pattern for adding a mechanism later: one enumeration entry, one classification, and a test that
fails loudly when the second is forgotten.

**No console screen is specified.** The console must render `source` wherever it renders a
body, because the precedence rule surprises anyone who meets it as bare prose. Which screen, and
what it looks like, belongs to the M7 console line and to
`.claude/rules/interface-originality.md`, not here.

**The import-linter contract is not completed.** `forbidden_modules` enumerates nine packages
and omits `sync.mcp`, `sync.api`, `sync.dashboard` and `sync.benchmark`, so `sync.core` could
import `sync.mcp` today and the contract would pass. This design adds `sync.context` because it
must. Closing the rest is one line and the same mechanism, and it belongs to a diff that argues
one thing.
