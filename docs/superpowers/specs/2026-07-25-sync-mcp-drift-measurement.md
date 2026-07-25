# Sync — MCP Drift Measurement

**Date:** 2026-07-25
**Status:** Evidence. Resolves the M1 go/no-go test named in the strategy plan.
**Question:** Does MCP tool-schema drift occur often enough to justify moving the MCP adapter ahead of runtime
telemetry in the milestone order?

## Why this was measured before it was built

The strategy work reordered M1 to the MCP adapter on the assumption that MCP tool schemas drift far more than
Stripe's post-`acacia` cadence of two breaking releases per year. That was an assumption, and the milestone
order rested on it. The plan's verification section proposed watching ten public MCP servers for three weeks.

Git history makes the forward-looking test unnecessary: a year of drift has already happened and is recorded in
release tags. This measures it retroactively instead of waiting.

## Method

For each release tag in the twelve months to 2026-07-23, check out the tree, extract every tool's parameter set
and which parameters are required, and diff consecutive releases. A change counts as **breaking** when it
invalidates an existing caller: a tool removed, a parameter removed, a new required parameter, or an optional
parameter tightened to required.

Two repositories, two extractors:

- **`modelcontextprotocol/servers`** — the reference servers. Python, extracted with the `ast` module by
  resolving `Tool(name=…, inputSchema=Model.model_json_schema())` to the Pydantic model's fields.
- **`github/github-mcp-server`** — a vendor-operated production server. Go, extracted with a brace-matching
  scanner that reads both declaration styles, because the project migrated from the fluent
  `mcp.NewTool("x", mcp.WithString("y", mcp.Required()))` form to the official SDK's `mcp.Tool{…}` struct
  literal partway through the window.

## Result

| | Reference servers | GitHub's server |
|---|---|---|
| Releases in window | 18 | 59 (excluding release candidates) |
| Tool-schema changes | 3 | 560 raw, 355 after artifact filtering |
| **Breaking changes** | **1** | **135** |
| Release transitions containing one | 1 of 17 | 18 of 37 |
| Tools added | 0 | 85 |

Stripe, for comparison, ships breaking changes in two semiannual releases per year.

**The reference servers are nearly static.** One breaking change in twelve months: `git_init` was removed in
`2025.9.25`. Two optional parameters were added to `git_log`. That is all.

**The vendor-operated server is not.** GitHub's MCP server shipped a breaking change in roughly half its
releases, retired 38 tools, added 54 newly-required parameters, and added 85 tools over the same window. Verified
by hand as a representative instance: `get_commit` carried an `include_diff` parameter in `v1.1.2` and does not
in `v1.2.0`.

## What this does and does not establish

**Establishes:** for MCP servers operated by a vendor against a moving product, schema drift exceeds Stripe's
cadence by more than an order of magnitude, and breaking drift is routine rather than exceptional. The M1
reordering holds.

**Corrects the assumption that motivated it:** "MCP tool schemas drift constantly" is false as a blanket claim.
Drift tracks whether a real product sits behind the server. Reference and demo servers are static; the servers
worth watching are the ones a vendor ships alongside a changing API. Sync's MCP adapter should target
vendor-operated servers, and any coverage claim counted in "number of MCP servers watched" would be
mostly noise.

**Does not establish:** anything about the ecosystem as a whole. Two repositories were measured, one of them a
single vendor. A survey would need a dozen vendor-operated servers, and the honest confidence here is "one
strong instance and one negative control," not "a rate."

## The artifact problem, and what it implies for the adapter

The raw Go measurement reported 346 breaking events; 135 survived filtering. The discarded 211 were extraction
failures, in three classes:

1. **Mass parameter wipes.** When a tool's parameters move behind a feature-flag-gated or programmatically
   constructed schema — `get_file_contents` in `v1.6.0` — a static reader sees every parameter disappear at
   once. Filtered by discarding any tool losing four or more parameters in one release.
2. **Helper refactors.** `page` and `per_page` moved into a shared `WithPagination()` helper in `v0.7.0`,
   which takes no parameter-name string and so is invisible to a scanner looking for one.
3. **Flaky tool disappearance.** Tools that vanish in one release and return in a later one were never removed;
   the extractor lost them.

**This is the strongest argument in the document for how the MCP adapter should be built.** Every one of these
failures comes from reading tool definitions out of source. An MCP server answers `tools/list` with its actual
schema — no parsing, no language-specific extractor, no refactor artifacts, and no distinction between the two
declaration styles that cost most of the effort here. The adapter should snapshot the served schema and diff
snapshots, exactly as the design document proposes, and should never attempt to recover schemas from a
repository.

It also means this measurement cannot be repeated cheaply as a monitor. Going forward, snapshot `tools/list`
from running servers; use source extraction only for backfilling history that no snapshot exists for.

## Consequences for the plan

- The M1 reordering stands, with its target narrowed: **vendor-operated MCP servers**, not the MCP ecosystem.
- `VendorAdapter.fetch_changes` for MCP is a snapshot differ over `tools/list` output. The change taxonomy used
  here — `tool_removed`, `param_removed`, `param_added_required`, `param_tightened`, and their non-breaking
  counterparts — is a working first draft of the `VendorChange.kind` vocabulary for MCP, and it was arrived at
  by classifying real changes rather than by design.
- The snapshot store needs one row per `(server, observed_at)` holding the full `tools/list` response, because
  a diff is only as good as the oldest snapshot retained. This is cheap and should start as soon as the adapter
  exists.

## Reproducing

Scripts are in the session scratchpad, not committed: `extract.py` (Python/ast), `go_extract.py` (Go/scanner),
`drift.py` and `drift_go.py` (checkout, diff, classify). They are measurement instruments, not product code, and
they carry the extraction limitations described above. If the numbers here are ever load-bearing for something
external, re-derive them from live `tools/list` snapshots instead.
