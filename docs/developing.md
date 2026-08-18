# Working on Sync itself

From-source setup, the quality gates, and how the work is done. Moved out of `README.md`
verbatim; the quick-start paths that do not need a checkout stay on the landing page.

### Working on Sync itself

Everything from here down is the from-source path, which is a different job with different
prerequisites.

### What you need before the first command

- **Python 3.12** and [uv](https://docs.astral.sh/uv/). The interpreter is `python`.
- **Docker**, for the Postgres 16 that holds the graph. It is published on port 5433.
- **Node 22.22 or later**, for `npm` in `web/` and for `tsc` through `npx`. The floor is
  react-router's own, and CI pins that version.
- **The [`gh` CLI](https://cli.github.com/), authenticated before the *first run* rather than
  before the first pull request.** Sync downloads a vendor's OpenAPI specification with
  `gh api` (`src/sync/signals/stripe/adapter.py:57`) and `scripts/bootstrap_tools.sh` fetches
  the pinned oasdiff release the same way, so an unauthenticated `gh` stops a run at its first
  step and stops the checkout before that.
- **The [`claude` CLI](https://claude.com/claude-code), authenticated.** The last tier of the
  cascade is the Claude Agent SDK (`src/sync/remediate/agent_patch.py:56`), which runs that
  binary as a subprocess. A finding a codemod resolves never reaches it; anything else abandons
  without it.

### Install the checkout

```bash
git clone https://github.com/stroland02/sync.git
cd sync

uv sync                                       # install dependencies
docker compose up -d                          # Postgres 16, on port 5433
bash scripts/bootstrap_tools.sh               # the pinned oasdiff; once per checkout
uv run python scripts/fetch_corpus_repositories.py   # the frozen corpus; once per checkout

uv run pytest                      # ~3400 tests, four to eleven minutes
```

`bootstrap_tools.sh` picks the release asset for your own platform and prints the version
`.oasdiff-version` pins. It refuses rather than guesses on a platform oasdiff publishes no build
for, and it never overwrites a build a checkout already holds.

`fetch_corpus_repositories.py` materialises five repositories pinned by commit into gitignored
`.cache/corpus/`. Both steps are `once per checkout` rather than once per machine: the artifacts
are gitignored, so a second worktree of this repository needs them again. Skip either and the
suite fails on the missing artifact rather than on anything you changed — about fifty tests, each
naming the script that supplies what it wanted.

### Detect and remediate vendor changes in a repository

```bash
uv run sync run \
  --vendor stripe \
  --from-version v2320 --to-version v2330 \
  --repo https://github.com/your-org/your-repo
```

**`--repo` takes a git remote URL, not a checkout on disk.** Sync clones it itself, and it
addresses the same repository through `gh api` to read CI and open the pull request — a
filesystem path carries no owner and name for that call. A path is refused while the arguments
are read, before anything is downloaded, and the refusal names the URL forms to pass instead.

### Run the operator console

```bash
uv run python scripts/seed_console.py             # the schema, plus a fixture to look at
SYNC_API_RELOAD=true uv run python -m sync.api    # :8787
cd web && npm install && npm run dev              # :5173
```

Seed before starting the API. Every console route is a read and none of them creates a table,
so against an empty database the API refuses to start and names the command that applies the
schema. Both processes read `SYNC_GRAPH_DSN`; unset, it resolves to the same `docker compose`
database `--dsn` defaults to on every subcommand below.

Other entry points:

| Command | What it does |
|---|---|
| `sync run` | Detect and remediate vendor changes in a repository |
| `sync intake` | Assess a repository's declared dependencies, ranked by call sites found |
| `sync ingest` | Ingest OTLP client spans and correlate them to call sites |
| `sync shapes` | Record observed response shapes for contract-drift detection |
| `sync benchmark` | Score the pipeline against the frozen corpus |
| `sync merge-outcome` | Record a merge outcome from a signed GitHub webhook |
| `sync publish-feed` | Publish a signed public change feed |

---

## Quality gates

Sync's product claim is quantitative, so it is measured rather than asserted. A frozen corpus of
17 labelled pairs across 5 repositories — pinned by commit SHA and validated by tree digest —
scores the binder on every run, and CI fails on a regression:

```
  binding precision     1.0000    floor 1.0000    n=26
  binding recall        1.0000    floor 1.0000    n=26
  falsifiable negatives      7    floor      7
  pairs scored              17    floor     17
```

The last two floors guard the gate rather than the binder. If falsifiable negatives returns to
zero, precision has no candidates to fail on and its floor gates nothing while staying green. If
pairs scored shrinks, both denominators shrink with it and both rates stay at 1.0000 over a corpus
covering less than it did.

**Both frozen inputs are pinned.** The repositories by commit and tree digest; the symbol map by a
digest over its *content*, so a reserialisation does not read as a change while a repointed symbol
does.

Everything else is **recorded, not gated**. No threshold in this repository was invented — a gate
at a made-up number either fires constantly and gets disabled, or never fires and provides false
assurance.

### How the work is done

- **Test first, in both languages.** Write the failing test, run it, watch it fail *for the reason
  you expect*, then implement. A test that has never failed has never been shown to test anything.
- **A test that cannot fail is worse than no test.** The import-boundary test's original form
  exited 0 without parsing its own argument. When a test asserts on a subprocess or an external
  tool, it is broken deliberately and watched go red before it is trusted.
- **Anything about rendered pixels is measured in Chrome**, through `getComputedStyle`, before and
  after — never asserted from a snapshot, which in a console under active design fails on every
  correct change and gets deleted by whoever it blocks.
- **A workaround ships with a backlog entry naming what retires it, or it does not ship.**

---

## Contributing

The most valuable contribution is **a vendor adapter**, and it is deliberately the easiest thing to
write. `sync.core` imports nothing, so an adapter is a self-contained implementation of one
protocol with no infrastructure in its dependency tree.

```python
class VendorAdapter(Protocol):
    vendor_id: str
    def fetch_changes(self, since: Version) -> Iterable[VendorChange]: ...
    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...
```

`operation_for_symbol` is the hinge of the whole system: it maps an SDK call site such as
`stripe.charges.create` onto an OpenAPI operation such as `POST /v1/charges`. Without it, spec
diffs and source code live in unconnected universes.

Before trusting an adapter you have written, run the conformance kit in `sync.core.conformance`.
It checks the guarantees a `runtime_checkable` Protocol cannot — the standard library verifies only
that method *names* exist, so an adapter can satisfy `isinstance` completely and still be wrong in
every way that matters.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the working agreement, and
[`docs/superpowers/specs/`](docs/superpowers/specs/) for the reasoning behind every decision — each
specification states what it measured rather than what it assumed.

---

## Documentation

| Document | What it settles |
|---|---|
| [Design](docs/superpowers/specs/2026-07-25-sync-self-maintaining-apis-design.md) | The whole system, its milestones and its risk register |
| [Latency architecture](docs/superpowers/specs/2026-07-25-sync-latency-architecture.md) | Why every agent must shorten the critical path or improve a result |
| [Pipeline discipline](docs/superpowers/specs/2026-07-27-sync-pipeline-discipline.md) | Grain, idempotence, and why every binding carries the rung it came from |
| [Benchmark gates](docs/superpowers/specs/2026-07-27-sync-benchmark-gates.md) | What is gated, what is recorded, and why no threshold is invented |
| [Verification regime](docs/superpowers/specs/2026-07-29-sync-verification-regime.md) | How much of the measurement actually runs today |
| [Adaptive vendor substrate](docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md) | How coverage scales by artifact tier rather than by vendor |
| [Threat model](docs/superpowers/specs/2026-07-25-sync-threat-model.md) | What a malicious vendor feed can and cannot do |
| **[Architecture](ARCHITECTURE.md)** | **How the system works: the state machine, the tier cascade, provenance rungs, durable execution, and the three mechanisms that contain the agent** |
| [Console architecture](docs/superpowers/plans/2026-08-05-sync-console-architecture.md) | The nine levels, and the twenty-four sentences that carry the honesty discipline |
| [Backlog](docs/superpowers/BACKLOG.md) · [Work log](docs/superpowers/WORKLOG.md) | Every milestone's real state, and every work item with the commit that landed it |

---
