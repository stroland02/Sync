# Reference read: SAST, code quality and SCA, against what Sync can honestly show (2026-08-18)

The owner asked for comprehensive codebase metrics on the dashboards — API topology, complexity,
health and reliability, composition and dependencies — and for the open-source scanning tools
behind them. Surveyed with licenses, and judged by one test this repository already applies
everywhere: **a metric Sync cannot compute from what it has read is a metric it must not draw.**

| Tool | What it answers | License | Verdict |
|---|---|---|---|
| `lizard` | cyclomatic complexity, multi-language | MIT | **CANDIDATE, not yet** — the honest source for per-function complexity. A dependency, and the index already parses these files with tree-sitter, so the same numbers are reachable without one |
| `radon` | cyclomatic complexity, maintainability index, Python | MIT | Same verdict, Python-only |
| `ruff` (C901) / `eslint` (complexity) | complexity as a lint rule | MIT | **SKIP** — a customer's own lint config is theirs; reading its output would make Sync's number depend on their thresholds |
| `bandit` / `semgrep` | SAST findings | Apache-2.0 / LGPL-2.1 | **SKIP for now, and it is a scope decision rather than a tooling one.** Sync's product claim is about *API* correctness — a general SAST result on screen would be a second product wearing this one's chrome |
| `osv-scanner`, `pip-audit`, `trivy`, `grype` | known vulnerabilities in declared dependencies | Apache-2.0 | **THE STRONGEST FIT, and it needs a decision.** Sync already parses every manifest; OSV's free API would turn that list into "which of your dependencies has a published advisory". It reaches a network, which is why it is recorded here rather than built quietly |
| `syft` | SBOM generation | Apache-2.0 | Follows from the above; nothing needs it until an SBOM is asked for |
| OpenSSF `scorecard` | repository security posture | Apache-2.0 | **SKIP** — it scores a repository against practices, which is a composite health figure by another name |

## What was built instead, and why it is not a compromise

**`GraphStore.api_topology` — every figure a `GROUP BY` over call sites the index already
wrote.** Measured on this repository the day it landed: 165 call sites, 45 operations, 109
files, three vendors; `PostCharges` reached from 96 of them; one file calling two integrations;
three calls inside loops, one of them quadratic.

That last one is the point worth making about "complexity". **Sync holds a complexity signal
nobody else on this list has: `loop_depth`, per call site, at the API boundary** — zero is one
call per unit of work, one is a page of results becoming a call each, two is quadratic. It is
static evidence and the payload says so. A cyclomatic number would describe the function; this
describes the *cost of the call*, which is the thing this product is about.

**What is deliberately absent from the Overview:** a maintainability index, a security grade, a
health score. Each is a composite, and `CLAUDE.md` refuses composites three times over — a
number averaging "we could not check" with "we checked and it passed" is the failure this
console exists to replace.

**The open decision, stated rather than assumed:** dependency vulnerability data (OSV) is the
one item here that would add real value and needs an owner ruling, because it means Sync makes
a network call about the customer's dependency list. Recorded as `B196`.
