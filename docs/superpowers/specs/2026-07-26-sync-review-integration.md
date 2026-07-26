# Sync — Review Integration and Borrowed Mechanisms

**Date:** 2026-07-26
**Status:** Decided. Mechanisms adopted now; integration lands after the MCP server exists.
**Scope:** What Sync takes from Alibaba's Open Code Review, and how Sync reaches code reviewers without becoming one.

## Context

Sync's pull requests are read by engineers who review many of them a day. The design has treated that reviewer
as an assumption. This document replaces the assumption with a studied one, using the only large-scale AI
code-review system whose source is public.

**Open Code Review** (`alibaba/open-code-review`, Apache-2.0, Go) was Alibaba Group's internal AI review
assistant for two years before it was open-sourced — by its own account serving tens of thousands of
developers and identifying millions of defects. Everything below marked *verified* was read from the cloned
repository at `HEAD` on 2026-07-26, not from documentation about it.

Its published benchmark is built from 50 open-source repositories, 200 real pull requests, 10 languages, and
1,505 ground-truth issues cross-validated by more than 80 senior engineers. Against a general-purpose agent on
the same model it reports higher precision and F1, faster reviews, and roughly **one ninth the tokens** — with
deliberately *lower recall*, described as "a deliberate trade-off favoring precision over noise."

That sentence is the most useful thing in the project. A system reviewed by people at volume chose to miss real
defects rather than spend reviewer attention. Sync's pull requests compete for the same attention.

## What Sync adopts

Five mechanisms, all verified in source.

### 1. Positions are computed, never generated

*Verified: `internal/diff/resolver.go`, `internal/diff/relocation.go`.*

The model never emits a line number. It emits a finding together with an `existing_code` snippet.
`ResolveLineNumbers` then locates that snippet by matching it against the file's diff hunks, falling back to
scanning the full new-file content. When matching fails, `ReLocateComment` asks the model for a *more precise
snippet* — not for a line number — and retries resolution.

OCR names position drift as one of three characteristic failures of general-purpose agents doing review.
This mechanism converts it from a model problem into a string-matching problem.

**Sync adopts this wherever a location is reported.** The `locate` node and `sync_explain_call_site` both
resolve positions by snippet match rather than trusting a model-reported line. `call_site.content_hash`
already exists for incremental indexing and gives the matching substrate. A patch that edits the wrong line
because a model miscounted is a defect class Sync can delete outright rather than mitigate.

### 2. Bundle related work into one unit with isolated context

*Verified: described in `README.md`; `internal/scan/batch.go` implements batching.*

Related files are grouped into a single review unit — their example bundles `message_en.properties` with
`message_zh.properties` — and each bundle runs as a sub-agent with its own context. Divide and conquer keeps
quality stable on large changesets and parallelises naturally.

**Sync's bundling key is the vendor change, not the file.** Every call site affected by one removed field
shares a changelog entry and a specification diff. Remediating them as one unit sends that shared context once
instead of once per finding, which is the same economy the latency architecture already claims for computing a
vendor diff once across customers.

### 3. Small rule sets, matched deterministically

*Verified: `internal/config/rules/system_rules.json`, `rule_docs/*.md` (25 files).*

Rules are matched to files by glob, not by asking a model which rules apply:

```json
"**/*.{ts,js,tsx,jsx}": "ts_js_tsx_jsx.md",
"**/*.java": "java.md",
"**/pom.xml": "pom_xml.md"
```

And the rule documents are small. `default.md` is five headings — Correctness, Security, Performance,
Maintainability, Test Coverage — and roughly fifteen questions in total. The stated purpose is "eliminating
information noise at the source."

**Sync matches rules on `change_kind`.** A `response-property-removed` gets a different, short instruction set
than a `request-property-added`. Deterministic selection, small payload, no general-purpose prompt trying to
cover every case.

### 4. A deliberately small toolset

*Verified: `internal/tool/definitions.go`.*

Six tools total: `task_done`, `code_comment`, `file_read`, `file_find`, `file_read_diff`, `code_search`. Two of
those are "emit a finding" and "I am finished," so the reasoning surface is four. OCR reports distilling this
from production tool-call traces — call frequency, per-tool repetition rates, and the effect of each new tool
on the whole call chain.

Sync's graph surface arrived at four tools independently. That agreement is treated as confirmation, and the
frozen-schema rule in `2026-07-25-sync-graph-surface-design.md` stands.

### 5. Precision over recall, as a stated position

Sync already declines to open a pull request it cannot verify. This extends the same discipline to what a
pull request *says*: a finding Sync is not confident in is not worth a reviewer's attention, and the cost of
one confidently wrong claim is that the reviewer skims the next ten.

## The integration: Sync supplies reviewers, and does not become one

Every AI reviewer reads the repository and none can see outside it. CodeRabbit, Greptile, OCR, and coding
agents all share the same blind spot: they cannot know that the API a diff calls is changing next month,
because that requires vendor-change data joined to call sites. Sync has exactly that and nothing else does.

So Sync ships as a tool reviewers call, through an extension point OCR already built.

### Why this shape rather than a review tool

- **Each new reviewer becomes a distribution channel rather than a competitor.** One stable interface answers
  the same missing question for all of them.
- **It preserves the position already decided** in `2026-07-25-sync-positioning-and-open-core.md`: the binding
  is the product. Review is another consumer of the binding.
- **The cost of being wrong is asymmetric.** If the integration finds no adoption, two configuration files are
  deleted. A `sync_review_pr(diff)` tool would mean diff-parsing machinery, review-shaped logic, and a
  permanent entry in a schema that is frozen on publish.
- **Using an extension point as designed is the deferential move.** Rebuilding review logic inside Sync would
  duplicate two years of tuning and then depend on it anyway.

### How it attaches

*Verified: `internal/mcp/client.go`, `internal/mcp/provider.go`, `cmd/opencodereview/config_cmd.go`,
`internal/config/rules/system_rules.go`.*

OCR starts each MCP server as a subprocess over stdio (`mcp.CommandTransport{Command: cmd}`) using the official
Go SDK, then registers the server's tools into the same registry that holds `file_read` and `code_search`.
Tools whose names collide with built-ins or with already-registered tools are skipped with a warning; a
`tools` whitelist restricts which are registered at all.

Sync's server is stdio with a `sync-mcp` entry point and `sync_`-prefixed tools, so it attaches with no adapter
and no name collision. Two artifacts install it.

**Server registration** — `~/.opencodereview/config.json`:

```json
{
  "mcp_servers": {
    "sync": {
      "command": "sync-mcp",
      "tools": ["sync_explain_call_site", "sync_whats_at_risk"]
    }
  }
}
```

Only two of the four tools are registered. Their own finding — that each added tool perturbs the whole call
chain — is a reason to give a review agent the minimum that answers its question.

**Rule attachment** — `<repo>/.opencodereview/rule.json`:

```json
{
  "rules": [
    {
      "path": "**/*.{ts,js,tsx,jsx}",
      "rule": ".opencodereview/rules/sync-api-surface.md",
      "merge_system_rule": true
    }
  ]
}
```

`merge_system_rule: true` is load-bearing: it **adds** the fragment to OCR's own rules rather than replacing
them. All 25 language rule sets keep working; Sync's rules sit on top.

Rule precedence is four layers, highest first: a custom file passed via `--rule`, then
`<repo>/.opencodereview/rule.json`, then `~/.opencodereview/rule.json`, then the built-in system rules. Sync
installs at the project layer, inside the customer's repository — no fork of OCR and no upstream pull request.

**The rule fragment** is written in the register OCR's own rules use — imperative and specific, matching lines
like "Using `var` is strictly prohibited":

```markdown
#### Third-Party API Surface
- For any call to a third-party SDK client, call `sync_explain_call_site` with the file and line before
  commenting on it. Do not guess whether the API is current.
- If the response reports `known_changes`, report the change and the affected field. Name the vendor version
  the change lands in.
- If `binding_source` is `static`, say that the mapping is derived rather than observed.
- Do not comment on a third-party call whose `known_changes` is empty. Silence is the correct output.
```

That last line matters as much as the first three. A rule that only ever adds comments is a rule that adds
noise.

## The weakness, and what bounds it

The honest objection to this shape is that OCR's agent must *choose* to call Sync's tools. Reading the source
narrows that considerably but does not eliminate it.

**Rule matching is deterministic.** The glob table decides which rules reach the model; no model decides. A
TypeScript file always receives the TypeScript rules, and with the fragment merged in, always receives Sync's
instruction. What remains probabilistic is only the tool call itself.

**Three things bound the residual risk:** the instruction sits in the document the model is already reading,
in the voice it already follows; the project layer installs it without anyone's cooperation; and the whitelist
keeps the added surface to two tools rather than four.

**It is falsifiable in an afternoon, and must be.** Before this integration is claimed to work, run OCR against
a fixture pull request that touches a Stripe call site with a known change, and count whether the tools are
called. If they are not, the defect is in the rule fragment, not in the architecture — but the claim is not
made until the count is taken.

## What Sync deliberately does not build

Diff parsing, comment positioning infrastructure, rule matching, the review loop, a severity taxonomy, and
language rule sets. These exist, they are good, and they are Apache-2.0.

Sync also does not add a `sync_review_pr(diff)` tool. OCR already holds the diff and the line numbers; what it
lacks is knowledge of what a line depends on, which is the question Sync's existing tools answer.

## Sequencing

| When | What |
|---|---|
| Now, independent of everything | Snippet-based positioning in the `locate` node. No dependency on M0, the MCP server, or OCR. |
| After M0 merges | The eight-task graph-surface plan, unchanged. This document does not alter it. |
| After the MCP server runs | The two configuration artifacts and the rule fragment, then the falsification test above. |
| Later | Rule matching on `change_kind` in the patch node, and bundling findings by vendor change. |

Nothing here changes the four tools, so `2026-07-25-sync-mcp-graph-surface.md` proceeds as written.

## Attribution

Open Code Review is Apache-2.0, copyright 2026 Alibaba. Mechanisms described here are adopted as design
influence; no code is copied. If a rule fragment or plugin is published for OCR users, it belongs upstream in
their plugin ecosystem, with attribution, rather than vendored.
