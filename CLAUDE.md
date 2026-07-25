# Sync — working conventions

Read this before writing code. It is the shared context every agent working in this repository gets; briefs and plans layer on top of it, never against it.

## What this project is

Sync watches the third-party APIs a codebase calls and opens verified pull requests when one of them breaks, drifts, or wastes money. Design: `docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md`.

The load-bearing idea is the **API Dependency Graph**: static call sites joined against vendor changes and runtime telemetry. Detectors query it, and all of them emit one `Finding` type into one remediation pipeline. If you are adding something that does not read from or write to that graph, question whether it belongs.

## Latency is a design constraint, not a later optimisation

`docs/superpowers/specs/2026-07-25-sync-latency-architecture.md` is binding on pipeline design. Read it before changing the shape of any pipeline, adding an agent, or introducing a stage.

The rule it exists to enforce: **every agent must shorten the critical path or improve a result. An agent that does neither is latency and cost with extra steps.**

Three things from it that are easy to get wrong:

- Sync's critical path is dominated by the customer's CI run, which nothing we build makes faster. Parallelism addresses about a fifth of the wall clock. The larger wins are precomputation and staged delivery.
- Any state key written by parallel branches **must** declare a reducer. Without one, concurrent writes are dropped silently — no error, no warning, missing results.
- `locate → patch → verify` is a data dependency, not an accident. Parallelising it produces a race, not speed.

## Non-negotiables

**`sync.core` imports nothing from any sibling package.** Not `sync.graph`, not `sync.signals`, not anything. A third party writing a vendor adapter depends on `sync.core` alone; a single sibling import drags Postgres into their dependency tree. `tests/test_import_boundary.py` enforces this and it is not advisory.

**Nothing reaches a pull request unverified.** Every patch passes `tsc` and then the customer's own CI. We never execute customer code ourselves and never hold their secrets. If you find yourself adding a path that skips the gate, you have found a bug in your approach, not a shortcut.

**Vendor-specific knowledge lives in adapters, never in core.** Stripe's URL conventions, its `operationId` scheme, its SDK naming — all of it belongs to `sync.signals.stripe`. The moment core knows a vendor's name, the plugin story is dead.

## Toolchain

| | |
|---|---|
| Python | 3.12. The interpreter is `python`. **Never `python3`** — that is a Microsoft Store shim on this machine and it will not run. |
| Packages | `uv` only (`uv add`, `uv run`). Poetry is not installed; do not introduce it. |
| Database | Postgres 16 in Docker on **port 5433**, not 5432. `docker compose up -d`. |
| TypeScript | via `npx`; the repo does not vendor a compiler. |
| GitHub | the `gh` CLI, already authenticated. |
| Shell | command snippets are POSIX, written for Git Bash. PowerShell 5.1 here has no `&&` — chain with `; if ($?) { }`. |

Git warns `LF will be replaced by CRLF` on every commit. That is expected. Do not add a `.gitattributes` or rewrite line endings to silence it.

**Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, **and `subprocess.run(..., text=True)`**. On Windows all of these default to the locale codepage — cp1252 here — so any non-ASCII byte corrupts or raises, and only on this platform. Every fixture in this repository is ASCII, which means **no test will ever catch it**; it fails first against real vendor data or a real customer repository. When handling bytes that are not text, use `read_bytes`/`write_bytes` and do not decode at all.

`subprocess` is the easy one to forget, and it fails worse than the others. A decode error there is raised on the reader thread and never propagates: the call returns with `stdout` set to `None`, and the next line that concatenates it raises `TypeError` somewhere unrelated. Task 6 shipped exactly this — one accented identifier anywhere in a typechecked project crashed the verification gate instead of failing it. Task 4 hit the plain `read_text` form twice.

## How we work

**Test first, always.** Write the failing test, run it, watch it fail for the reason you expect, then implement. A test that has never failed has never been shown to test anything.

**A test that cannot fail is worse than no test** — it manufactures confidence. When a test asserts on a subprocess, an exit code, or an external tool, prove it detects a real violation before trusting it. This has already bitten us once: the import-boundary test's original form exited 0 without parsing its own argument.

**No test calls a vendor API or a model API.** Fixtures are committed. Local toolchain access — the Postgres container, `npx` fetching a compiler — is fine. The one end-to-end test is marked `@pytest.mark.e2e` and deselected by default.

Run the focused test while iterating; run the full suite once before committing.

## Model configuration

Always `claude-opus-5`, always adaptive thinking, always `xhigh` effort. **The two surfaces spell that differently, and they are not interchangeable.**

Messages API — nested, and takes a token ceiling:

```python
model="claude-opus-5"
thinking={"type": "adaptive"}
output_config={"effort": "xhigh"}
max_tokens=64000
```

Claude Agent SDK (`ClaudeAgentOptions`) — flat, and has **no** `output_config` and **no** `max_tokens`:

```python
ClaudeAgentOptions(
    cwd=...,
    model="claude-opus-5",
    thinking={"type": "adaptive"},
    effort="xhigh",
    allowed_tools=[...],
    disallowed_tools=["WebSearch", "WebFetch"],
)
```

Verified against the installed package: `ClaudeAgentOptions` exposes `cwd`, `model`, `thinking`, `effort`, `allowed_tools`, `disallowed_tools`, and `permission_mode`. Passing the Messages-API shape to it does not work, and this document previously said otherwise.

Restricting a tool means listing it in `disallowed_tools`. Merely leaving it out of `allowed_tools` is not a block — with no `can_use_tool` callback registered, an out-of-list call has no resolution path in headless mode, which inside an unattended pipeline is a hang rather than a refusal.

`temperature`, `top_p`, and `budget_tokens` return HTTP 400 on this model on either surface. Steer with prompting instead. Thinking is on by default, and on the Messages API `max_tokens` caps thinking plus output together, which is why that ceiling is generous.

## Code style

Write code that reads like the code already here. Match its naming, comment density, and idiom.

Comment to state a constraint the code cannot show — never to narrate what the next line does, where something came from, or why a change is correct. That last one is talking to a reviewer, and it becomes noise the moment the pull request merges.

Prefer small, focused modules over large ones. A file that has grown past one clear responsibility is a signal, not a style preference.

Do not add error handling, fallbacks, or validation for conditions that cannot occur. Validate at system boundaries — user input, vendor responses, subprocess output — and trust internal code.

## Commits

Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`). Write the body in normal prose explaining why, not what — the diff already says what.
