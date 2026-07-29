# Attaching Sync to Open Code Review

Every AI reviewer reads the repository and none can see outside it. They cannot know that the API
a diff calls is changing next month, because that requires vendor-change data joined to call
sites. Sync has that and exposes it over MCP, so a reviewer can ask rather than guess.

Open Code Review starts each MCP server as a subprocess over stdio and registers its tools
alongside its own. Sync's server is stdio, its entry point is `sync-mcp`, and its tools are
`sync_`-prefixed, so it attaches with no adapter and no name collision. Three files install it,
and they are the whole integration — Sync builds no diff parsing, no comment positioning, no rule
matching and no review loop, because Open Code Review already has them and they are Apache-2.0.

## Status: installed but unverified

**The falsification count has not been taken.** The design that this implements requires it
before the integration is claimed to work:

> Before this integration is claimed to work, run OCR against a fixture pull request that touches
> a Stripe call site with a known change, and count whether the tools are called. If they are not,
> the defect is in the rule fragment, not in the architecture — but the claim is not made until
> the count is taken.

That run has not happened. Open Code Review is a third-party binary and this repository's tests
may not call one, so what is proven here is everything up to the boundary and nothing across it:

| Proven, by test | Not proven |
|---|---|
| `sync-mcp` starts and answers `initialize` over stdio | That OCR's agent calls the tools when reviewing a real diff |
| stdout carries JSON-RPC frames and nothing else | That the rule fragment is worded persuasively enough to be followed |
| The whitelisted names are tools the server advertises | That the findings a reviewer produces from them are useful |
| The advertised schemas match the frozen golden file | |
| The rule fragment carries the silence instruction | |

The honest objection to this shape is that the agent must *choose* to call the tools. Rule
matching is deterministic — a TypeScript file always receives the TypeScript rules, and with the
fragment merged in, always receives Sync's instruction — so what stays probabilistic is the tool
call itself. Until somebody counts, that residual risk is unmeasured rather than small. If the
count comes back zero, the defect is in the fragment's wording and this file should say what
changed and what the second count was.

## Installing

**1. Register the server** — merge `config.json` into `~/.opencodereview/config.json`:

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

`sync-mcp` must be on the `PATH` of whatever starts Open Code Review, and `SYNC_DSN` must be set
in its environment — the server reads the graph and exits 2 with a message on stderr if it is
not pointed at one.

Two of the four tools are registered, deliberately. Open Code Review's own finding is that each
added tool perturbs the whole call chain, which is a reason to give a review agent the minimum
that answers its question. `sync_whats_changed` and `sync_propose_patch` stay unregistered:
the first answers a question review does not ask, and the second proposes an edit, which is not
a reviewer's job.

**2. Attach the rule** — copy `rule.json` to `<repo>/.opencodereview/rule.json` and
`rules/sync-api-surface.md` to `<repo>/.opencodereview/rules/sync-api-surface.md`.

`merge_system_rule: true` is load-bearing: it **adds** the fragment to Open Code Review's own
rules rather than replacing them, so all 25 language rule sets keep working and Sync's rules sit
on top. Rule precedence is four layers, highest first: a file passed via `--rule`, then
`<repo>/.opencodereview/rule.json`, then `~/.opencodereview/rule.json`, then the built-in system
rules. This installs at the project layer, inside the customer's repository — no fork and no
upstream pull request.

**3. Take the count.** See above. It is the step that turns this from a plausible integration
into one that works.

## What the fragment says, and why its last line matters

The fragment is written in the register Open Code Review's own rules use — imperative and
specific. Its final instruction is the one to protect when somebody shortens it:

> Do not comment on a third-party call whose `known_changes` is empty. Silence is the correct
> output.

A rule that only ever adds comments is a rule that adds noise, and the cost of one confidently
irrelevant comment is that the reviewer skims the next ten. Open Code Review's published
benchmark makes the same trade in the other direction — deliberately lower recall, "a deliberate
trade-off favoring precision over noise" — and this fragment has to hold to it or it degrades the
tool it is attached to.

## Attribution

Open Code Review is Apache-2.0, copyright 2026 Alibaba. No code is copied here; the two JSON
files are configuration in the shapes it documents, and the rule fragment is Sync's own text. If
a fragment or plugin is ever published for its users, it belongs upstream in their plugin
ecosystem, with attribution, rather than vendored.
