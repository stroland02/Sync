<div align="center">

# Sync

### Self-maintaining API integrations

**Sync watches the third-party APIs your code calls. When one breaks, drifts, or starts costing you money, it opens a pull request that fixes your code — already verified green by your own CI.**

[![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-1C3C3C)](https://github.com/langchain-ai/langgraph)
[![Postgres 16](https://img.shields.io/badge/store-Postgres%2016-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)](#status)

</div>

<div align="center">

<img src="docs/console-mock/demo.gif" width="92%" alt="A tour of the Sync operator console: the fleet, a call-site drawer, the command palette, detector attribution, codebase, API service, signals, the binding surface, a finding, the solution workflow, a pull request and the adapter settings" />

**The operator console — every screen in one pass.** Fleet → drawer → palette → detectors →
codebase → vendor → signals → binding surface → finding → workflow → pull request → settings.

*This is the design mock, not shipped code.* [What is built today](docs/why-sync.md#the-operator-console) ·
[the mock](docs/console-mock/) · [the plan that builds it](docs/superpowers/plans/2026-08-08-console-mock-to-build.md)

</div>

```
vendor ships a breaking change  →  Sync finds every call site that depends on it
                                →  patches them
                                →  runs your CI
                                →  opens a PR carrying the evidence
```

---

## Run it

**Three ways in. Two of them work today, and the third is written down because it is where this
is going.** Every one of them ends at the same console on
**http://127.0.0.1:4173**, signed in with the password the log prints — `sync-local-demo` unless you
exported `SYNC_CONSOLE_PASSWORD` first.

### 1. One command

```bash
npx @superloglabs/sync
```

**This does not work yet, and the reason is one line in our own manifest.** `@superloglabs/sync`
is not published — the registry answers 404, and `package.json` carries `"private": true`, so
`npm publish` refuses. That is a decision nobody has taken rather than a step nobody has got to.
**Use [2. From a checkout](#2-from-a-checkout--one-prerequisite-and-it-is-docker) instead; it is
the same work and it runs today.**

The program itself is real and is what publishing would ship: `bin/sync-up.mjs` checks the one
prerequisite and hands over to `docker compose`. It deliberately reimplements none of the real
steps — npm delivers a Node program, and a wrapper claiming to install Python and a database
would fail in front of the person being shown it.

### 2. From a checkout — one prerequisite, and it is Docker

Nothing here needs Python, `uv`, Node, `gh` or a Postgres on your machine. The image carries all of
them.

```bash
git clone https://github.com/stroland02/sync.git
cd sync
docker compose -f docker-compose.demo.yml up --build
```

### 3. From source, for working on Sync itself

Python 3.12, `uv`, Node 22.22+, and Postgres on 5433. **[docs/developing.md](docs/developing.md)**
carries the prerequisites, the install, and the quality gates.

### Run it — one prerequisite, and it is Docker

Nothing below this heading needs Python, `uv`, Node, `gh` or a Postgres on your machine. The image
carries all of them.

```bash
git clone https://github.com/stroland02/sync.git
cd sync
docker compose -f docker-compose.demo.yml up --build
```

Then open **http://127.0.0.1:4173** and sign in with the password the log prints — `sync-local-demo`
unless you exported `SYNC_CONSOLE_PASSWORD` before starting.

**Measured on a developer machine: 282 seconds the first time and 22 seconds after that.** The first
run builds four toolchains — the console's dependencies, a production build of it, Node for the
runtime image, and the Python tree — and every run after reuses all of it.

**If you are about to show this to somebody, build it beforehand:**

```bash
docker compose -f docker-compose.demo.yml build
```

That is the same work moved earlier, and it turns a five-minute wait into a twenty-two second one.
Nothing about the result differs.

That brings up Postgres, applies the schema, starts the API, waits until the API actually answers,
and only then serves the console. The order is deliberate: **half a stack is worse than no stack**,
because a console pointed at an API that never came up presents as a console bug and sends you
debugging the wrong thing.

Nothing is exposed except the console, and it is bound to `127.0.0.1` rather than every interface.
The API is reached only through the console's own `/api` proxy, which is where the credential gate
sits.

**Two things this does not do yet, stated here rather than discovered.**

- **The console comes up empty.** It renders correctly and has no data in it, because nothing yet
  indexes a repository you point it at — the CLI has no indexing subcommand, and indexing needs a
  vendor specification staged that a fresh container does not have. `B188` in
  `docs/superpowers/BACKLOG.md` carries the three ways out and what each one costs. Until that
  lands, this shows you that the product runs, not what it finds in your code.
- **The one-command form exists and is `npx @superloglabs/sync`.** `bin/sync-up.mjs` checks the
  single prerequisite and hands over to exactly the `docker compose` invocation above — it
  deliberately reimplements none of it, because npm delivers a Node program and a wrapper claiming
  to install Python and a database would fail in front of the person being shown it. **The
  published path has now been measured and it does not exist**: the registry answers 404 and
  `package.json` marks the package private, so `npm publish` refuses. Publishing it is a decision
  and a credential, not a task.

To stop it, and to remove its database with it:

```bash
docker compose -f docker-compose.demo.yml down -v
```

This is deliberately a separate file from `docker-compose.yml`, which serves only the development
Postgres on port 5433 that the section below uses.

### The journey, and why it runs in this order

Most tools in this space need instrumentation before they can show you anything: install an SDK,
get a key, wire an exporter, wait for an event. **Sync does not, and that is the strongest thing
about it.** The API dependency graph's first rung is `static` — call sites read straight out of
your code — so there is something true to show before you have configured anything.

1. **Index your repository.** Your call sites, your vendors, your findings. Every binding marked
   `static`, and the console saying plainly that `static` is what it is. No key, no SDK, no signup.
   *(Blocked today — see the note above and `B188`.)*
2. **Attach telemetry, if you want to, and watch bindings move from `static` to `observed`.** The
   screen shows the upgrade, so you can see exactly what instrumenting bought you. It is an
   argument for instrumenting rather than a precondition for being allowed in. In practice this is
   `sync ingest` over a payload you exported — Sync has no listener and does not ask you to point
   an exporter at a URL.
3. **Let it open a pull request, once you trust it.** Last, not first — after you have seen its
   reasoning on your own code.

**Value before configuration**, and it is not a trick: the provenance rung means the console can
say exactly how much that free first answer is worth.

## Status

## Status: pre-alpha, and specific about it

M0's definition of done was one thing: a real breaking change producing a CI-green pull request
against a real repository, unattended.

**That has happened once.** One `sync run` against a fork of `stripe/stripe-connect-furever-demo`
produced [pull request #1](https://github.com/stroland02/stripe-connect-furever-demo/pull/1) — two
deletions in one file, removing a withdrawn request argument at both call sites that passed it,
typecheck green on the branch, no human between detection and pull request.

Three qualifications, because they change what the result means:

- **The acceptance run has not re-executed since the pipeline changed underneath it.** It is
  `@pytest.mark.e2e` and deselected by default. Since it last ran, the pipeline gained the tier
  cascade, a push guard, branch deletion on abandonment, the dependency-edit guard and more —
  every one of them on the acceptance path.
- **The vendor change was constructed**: a property removed from a real pinned specification
  rather than one Stripe withdrew, because no window of Stripe's history examined here contains a
  top-level breaking change this application would notice.
- **Three of the five quality axes have never had a sample.** Merge rate, routing accuracy and
  cost per merged patch need pull requests that have not been opened yet. They report `null`
  rather than zero, deliberately.

What *is* measured is measured properly — see [Quality gates](docs/developing.md#quality-gates).

---

## Read further

The argument, the mechanism and the architecture live under `docs/` so this page can get you
running. Nothing was shortened in the move.

- **[Why Sync exists](docs/why-sync.md)** — the problem nobody owns, what actually makes this
  different, and the honesty discipline the console is built on. **Start here if you want to know
  why a graph of your own code is the product rather than a feature.**
- **[How it works](docs/how-it-works.md)** — provenance rungs, the remediation state machine, the
  tier cascade, durable execution, containing the agent, and the two invariants.
- **[Architecture and stack](docs/architecture.md)** — the shape of the system and the engineering
  constraints behind it.
- **[Working on Sync itself](docs/developing.md)** — from-source setup, the quality gates, and how
  the work is done.
- **[Beta readiness](docs/superpowers/plans/2026-08-18-beta-readiness.md)** — what stands between
  here and a stranger running this, measured rather than asserted.

## License

Apache-2.0. See [LICENSE](LICENSE).
