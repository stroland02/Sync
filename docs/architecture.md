# Architecture and stack

Moved out of `README.md` verbatim.

## Architecture

```
                        ┌─────────────────────────────────────────┐
   depends on nothing   │              sync.core                  │
                        │  Finding · CallSite · VendorChange      │
                        │  Patch · the plugin protocols           │
                        └─────────────────────────────────────────┘
                             ▲         ▲         ▲         ▲
              ┌──────────────┘         │         │         └──────────────┐
        ┌───────────┐            ┌──────────┐  ┌──────────┐         ┌───────────┐
        │ sync.index│            │sync.graph│  │sync.forge│         │sync.signals│
        │ TS · Py   │            │ Postgres │  │ git · gh │         │ vendor     │
        │ adapters  │            │   ADG    │  │          │         │ adapters   │
        └───────────┘            └──────────┘  └──────────┘         └───────────┘
                                      ▲              ▲
                        ┌─────────────┴───┐   ┌──────┴────────┐
                        │  sync.detect    │   │ sync.remediate│
                        │  detectors      │──►│ LangGraph     │
                        └─────────────────┘   └───────────────┘
                                      │              │
                              ┌───────┴──────────────┴────────┐
                              │ sync.dashboard · sync.api     │
                              │   the operator console        │
                              └───────────────────────────────┘
```

| Package | Responsibility | Depends on |
|---|---|---|
| `sync.core` | Contracts only — `Finding`, `CallSite`, `VendorChange`, `Patch`, and the plugin protocols | **nothing** |
| `sync.graph` | ADG persistence and queries over Postgres | `core` |
| `sync.index` | `LanguageAdapter` protocol; TypeScript and Python adapters | `core` |
| `sync.signals` | `VendorAdapter` protocol; Stripe, Twilio, MCP and generated-SDK adapters | `core` |
| `sync.detect` | `Detector` protocol and the detectors | `core`, `graph` |
| `sync.remediate` | LangGraph graphs turning a `Finding` into a merge-ready pull request | `core`, `graph`, `forge` |
| `sync.forge` | Git and GitHub App operations | `core` |
| `sync.dashboard`, `sync.api` | Read-only aggregates and the console's HTTP surface | `core`, `graph` |
| `sync.benchmark` | Scores the pipeline's own output quality | `core`, `graph` |

**[`ARCHITECTURE.md`](ARCHITECTURE.md) is the engineering document** — the remediation state
machine node by node, the tier cascade, how the agent is contained, and every term this
repository uses.

### The engineering constraints that shape it

These are enforced rather than encouraged, because each one failed silently at least once first:

| Constraint | Why it is a rule |
|---|---|
| **Every stage is idempotent** | Re-running INDEX, SIGNAL or DETECT on the same input converges on the same rows. Every table has a natural key and an explicit conflict clause |
| **A table's grain is declared before a column is added** | One `migration_outcome` row is one *attempt*, not one finding. A query that counts findings by counting rows is wrong, and wrong quietly |
| **Every binding carries its rung** | A column, not a join. The write refuses an unattributed finding |
| **Abandoned runs are data** | `abandon_reason` stays queryable — abandoned attempts are where routing learns which change kinds are not mechanically safe |
| **Any state key written by parallel branches declares a reducer** | Without one, concurrent writes are dropped: no error, no warning, missing results |
| **Every agent must shorten the critical path or improve a result** | An agent that does neither is latency and cost with extra steps |

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.12 | |
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) with a Postgres checkpointer | A CI run takes 3–30 minutes; a worker restart mid-wait must not lose it |
| Parsing | [tree-sitter](https://tree-sitter.github.io/) — TypeScript and Python | Real grammars, not regex over source |
| Codemods | [ast-grep](https://ast-grep.github.io/) | Deterministic edits wherever a transform is known |
| Spec diffing | [oasdiff](https://github.com/Tufin/oasdiff), pinned to 1.26.1 | Its rule identifiers *are* the change-kind domain; unpinning would silently change what the pipeline can see |
| Agent | [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-python) | The fallback patch path |
| Storage | Postgres 16 | |
| Contracts | Pydantic | |
| Vendor surfaces | [MCP](https://modelcontextprotocol.io/) | An MCP server's tool schemas drift like any other contract |
| Console | React 19, Vite, Tailwind v4, vitest | Read-only; no route mutates the graph |

---
