# Contributing to Sync

The interface is the product. Sync cannot write adapters for every API a codebase calls, which is
why `sync.core` imports nothing from any sibling package and why the plugin protocols are the part
we care most about getting right. If you write an adapter and the protocol fights you, that is a
bug in the protocol and we want to hear about it.

## The highest-value contribution: a vendor adapter

An adapter is a self-contained implementation of one protocol. It depends on `sync.core` alone, so
it does not inherit Postgres, LangGraph, or anything else in this repository's dependency tree.

That is a packaging fact rather than an aspiration. `sync.core` is built as its own distribution,
`sync-core`, and pydantic is the only thing it depends on — an environment holding it has six
packages in it against the eighty-one a checkout of this repository installs. Nothing is published
yet, so build the wheel from a checkout:

```bash
uv build --package sync-core   # dist/sync_core-*.whl
```

`tests/test_core_distribution.py` is what keeps that true: it builds the wheel, installs it into an
empty environment and runs the conformance kit there.

```python
class VendorAdapter(Protocol):
    vendor_id: str
    def fetch_changes(self, since: Version) -> Iterable[VendorChange]: ...
    def operation_for_symbol(self, symbol: str) -> OperationRef | None: ...
```

`operation_for_symbol` is the hinge. It maps an SDK call site — `stripe.charges.create` — onto an
OpenAPI operation — `POST /v1/charges`. Without it, a spec diff and the source code that calls that
API live in unconnected universes.

**Run the conformance kit before you trust it.** `sync.core.conformance` checks the guarantees a
`runtime_checkable` Protocol cannot: the standard library verifies only that method *names* exist,
so an adapter can satisfy `isinstance` completely and be wrong in every way that matters. The kit
covers all five protocols, and every rule in it has been proved able to fail.

Read `src/sync/signals/twilio/` before `src/sync/signals/stripe/`. Stripe's specification is
unusually clean; Twilio is the one that proved the protocol generalises, and its adapter is more
representative of what you will hit.

### Three things an adapter must not do

**Never guess a mapping.** An unresolvable symbol yields no finding, so nobody ever learns the
convention was wrong. `GeneratedSpecAdapter.operation_for_symbol` refuses to invent one by design,
and its docstring is worth reading on why. Return `None` and be visibly unresolved.

**Never put vendor knowledge in core.** A URL convention, an `operationId` scheme, an SDK naming
rule — all of it belongs to your adapter. The moment `sync.core` knows a vendor's name, the plugin
story is dead.

**Prefer a missing binding to a wrong one.** A missed finding costs one incident. A false finding
costs the reviewer's willingness to read the next one, and that does not recover at the rate it is
spent.

## Working agreement

These are not style preferences. Each exists because something went wrong without it.

**Test first, and watch it fail for the reason you expect.** A test that has never failed has never
been shown to test anything. When a test asserts on a subprocess, an exit code or an external tool,
prove it detects a real violation before trusting it — the import-boundary test's original form
exited 0 without parsing its own argument.

**Declare a table's grain in `schema.sql` before adding a column.** One `migration_outcome` row is
one *attempt*, not one finding. A query that counts findings by counting rows is wrong, and wrong
quietly.

**Every stage is idempotent.** Re-running INDEX, SIGNAL or DETECT on the same input converges on
the same rows. Every table gets a natural key and an explicit conflict clause.

**Every binding carries the rung it came from** — `static`, `resolved` or `observed` — and so does
every artifact derived from it. A false positive that cannot be attributed to a rung cannot be
fixed.

**Abandoned runs are data.** `abandon_reason` stays queryable. Abandoned attempts are where routing
learns which change kinds are not mechanically safe.

**Always pass `encoding="utf-8"` explicitly** to `read_text`, `write_text`, `open`, and
`subprocess.run(..., text=True)`. On Windows these default to the locale codepage. Every fixture in
this repository is ASCII, so no test will ever catch a missing one — it fails first against real
vendor data or a real customer repository. `scripts/lint_encoding.py` is the gate, and it exists
because this shipped more than once.

**Comment to state a constraint the code cannot show.** Never to narrate what the next line does,
and never to explain why a change is correct — that is talking to a reviewer, and it becomes noise
the moment the pull request merges.

## Getting set up

```bash
uv sync                       # dependencies; uv only, never pip or poetry
docker compose up -d          # Postgres 16 on port 5433, not 5432
uv run pytest                 # run it once before committing
```

Python is 3.12 and the interpreter is `python`, never `python3`.

Do not set `SYNC_DSN`. `tests/conftest.py` provisions a database per process; pointing that
variable at one that does not exist produces roughly thirty-five failures unrelated to your change.

## Before you open a pull request

Four gates, all of which CI runs:

```bash
uv run pytest
uv run lint-imports
uv run python scripts/lint_encoding.py src scripts tests
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt
```

If your change touches the binder, the corpus gate also applies:

```bash
uv run python scripts/gate_corpus.py --score <a score you produced>
```

Its floors are the figures the corpus recorded, not round numbers anyone liked. **Restating a floor
because the corpus grew is correct. Lowering one because a number got worse is the thing the gate
exists to prevent.**

## Commits

[Conventional Commits](https://www.conventionalcommits.org/) — `feat:`, `fix:`, `test:`, `docs:`,
`chore:`. Write the body in prose explaining *why*, not what; the diff already says what.

Git warns `LF will be replaced by CRLF` on Windows. That is expected. Do not add a `.gitattributes`
to silence it.

## Reporting a defect

The most useful report is a reproduction. Second most useful is a measurement. An assertion that
something seems wrong is welcome but will be measured before it is acted on — several confident
claims in this repository's history turned out to be reading a hardcoded literal.

For anything with a security dimension, see [SECURITY.md](SECURITY.md) rather than opening an
issue.
