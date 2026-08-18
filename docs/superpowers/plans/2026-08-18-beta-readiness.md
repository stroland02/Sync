# Beta readiness: what stands between here and a stranger running this

**Owner direction, 2026-08-18:** *"scope out what needs to get done to get beta up and running — I
want to start full testing this out as if I am a new user, from scratch."*

**Scoped against the tree rather than against the plan.** Every claim below was checked by reading
the repository, and where the README and the tree disagree, that is recorded as a finding rather
than smoothed over.

## The three owner decisions this scope rests on

Asked as multiple choice on 2026-08-18 so none of it is a guess:

1. **B188 — bake a pinned vendor spec into the image *and* ship `--repo` indexing.** The largest of
   the four routes and the only one where a new user sees the full loop on first run: call sites
   read out of their own code, bound to a real vendor operation.
2. **All three install paths must work** — `npx`, `git clone` + `docker compose`, and from source.
   Eventually all three; none is being dropped.
3. **The README splits into two pages** — a short one that runs it and links out, with the
   argument, the architecture and the honesty discipline moved under `docs/`.

## The blocker, stated plainly

**A stranger's container cannot index anything.** `/api/repositories` returns `{"repo_ids":[]}`, so
the console renders correctly and holds nothing. The ship plan already names this as the biggest UI
risk: *a screen with real data and plain styling survives the question; a beautifully composed empty
state does not.*

Three facts make it a decision rather than a task, and all three were measured:

- **`sync` has no `index` subcommand.** It has `run`, `ingest`, `shapes`, `merge`, `publish`,
  `intake`, `benchmark`, `reconcile`, `rehearse`, `context`. The composition already exists inside
  `run` (`cli.py:1095-1101`) and has never been exposed on its own.
- **Indexing is per vendor**, so it needs an adapter, which needs that vendor's specification
  staged.
- **`prepare_vendor` reaches the network and shells out to `gh`.** A fresh container has neither
  `gh` nor a credential. `load_vendor` is the offline twin and builds over artifacts something else
  already staged — so it cannot bootstrap either.

## What has to be built, in dependency order

### 1. `sync index --repo <path>` — a CLI entry point that exists
The pieces are written; nothing exposes them. This alone gets call sites into the graph from a
repository the user names, offline, with no vendor involved. **It is the smallest change that turns
an empty console into the user's own code**, and everything below is easier to test once it exists.

### 2. A pinned vendor specification baked at image build
So the vendor half of the loop works on first run without a network or a credential. Two things
this must carry rather than discover:

- **The snapshot ages.** The image states which spec version it holds and when it was pinned, so a
  reader is never guessing whether a finding reflects today's Stripe.
- **The pinned tags become a maintained thing.** That is the cost the owner accepted when choosing
  this route, and it belongs in the backlog with a name rather than as folklore.

### 3. The demo image runs the index on first boot
`docker/entrypoint.sh` already waits for the database, applies the schema, starts the API and waits
for it to answer. Indexing joins that sequence. **The console must not serve before the index has
either finished or failed visibly** — the same argument the entrypoint already makes about half a
stack being worse than no stack.

### 4. `npx` verified end to end
`bin/sync-up.mjs` exists and `package.json` declares the bin. **The README says it "is not built
yet" at line 505, and that is stale.** What has never been checked is the published path: whether
`npx @superloglabs/sync` resolves for somebody who is not in this checkout.

### 5. The README split
A short landing page that runs it, with the argument and architecture under `docs/`. The
honesty discipline moves rather than disappears — it is the product position, and a visitor who
runs the thing without it sees a graph and misses the point.

## What is already true and does not need building

Checked rather than assumed, so nobody spends a unit on it:

- **The demo stack comes up.** Postgres, schema, API, console, in that order, with the API's
  readiness gated before the console serves. Measured at 282 seconds cold and 22 warm.
- **Nothing is exposed but the console**, bound to `127.0.0.1`, with the API reached only through
  the console's `/api` proxy where the credential gate sits.
- **The console is complete enough to test.** Every level renders, the dashboards exist, and the
  indexing canvas now streams live over SSE with its own dropped-stream state.
- **The gates are real.** `pytest`, `lint-imports`, the encoding lint, the design-token guards, the
  conflict-marker guard, the API/type contract test and the register check all run and all bite.

## The risk this scope is really about

The first-run experience is the product's argument in miniature. **A new user who runs one command
and sees their own code bound to a vendor's API has understood Sync in thirty seconds.** A new user
who runs one command and sees an empty console has learned that it starts.

Everything above is in service of the first sentence being true.
