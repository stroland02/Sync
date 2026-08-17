# Sync watches Sync: the console shows our own codebase, and our own repairs are the record

**Owner's instruction, 2026-08-17.** The dev console should show **our own data** — this repository,
its own attached vendors, its own findings — rather than a seeded fixture. Test codebases for other
vendors come later. And the point is bigger than a demo: *"if we can't clean this up and get it
functioning it will never last."* The platform has to prove its workflow by resolving the issues we
hit while building it, and those repairs have to be **recorded in the repo** through the systems we
already built.

This plan says what that means concretely, what it honestly cannot mean, and what to build first.

## Why this is the right instruction and not just a nicer demo

Every number in the console today comes from `scripts/seed_console.py`. That fixture has been useful
and it has also been hiding things — the abandoned-run screen went unrendered for weeks because the
seed pairs an abandoned generation with an opened one, so no URL produced it (`M14-W348`). A fixture
answers the questions its author thought of. **Our own repository asks questions nobody chose.**

There is also a harder argument. Sync's claim is that it watches the third-party APIs a codebase
calls and repairs them when they drift. This repository *is* such a codebase, and it has already
been bitten exactly the way a customer would be — `CLAUDE.md` records that `ClaudeAgentOptions` was
documented with the wrong shape, that seven fields were listed as the verified surface when the
installed package declares forty-five, and that `temperature`, `top_p` and `budget_tokens` return
HTTP 400 on this model. **Those are vendor-surface drifts in our own call sites.** If Sync cannot
catch the class of bug that has already cost this project days, the claim is not yet true.

## What Sync can honestly watch in this repository, and what it cannot

This section exists so the dogfooding does not overclaim, which would be the worst possible outcome
for a product whose position is honesty.

**It can watch these, because they are the thing it is built for:**

| Call site | Vendor surface | Why it qualifies |
|---|---|---|
| `src/sync/runner/claude_sdk.py` | `claude_agent_sdk.ClaudeAgentOptions`, and the model id | A third-party SDK whose option surface has already changed under us, with a documented incident |
| `src/sync/signals/**` adapters | vendor OpenAPI documents and SDK manifests | Already the subject of the SIGNAL stage |
| `src/sync/forge/**` | the GitHub API through `gh` | A versioned third-party surface |

**It cannot watch these, and saying so is the point:**

- **The `NameError` that has blocked the API entrypoint all afternoon is not an API drift.**
  `configured_api_password` is imported inside `app_factory` and called from `main()`; that is a
  Python scoping bug in our own code. Sync detects *vendor* surface change. A dogfooding story that
  claimed this bug as a Sync catch would be inventing a capability, and this plan will not.
  **It is still evidence** — see the recording section, which is about repairs generally, not only
  about Sync-detected ones.
- **Anything with no machine-readable vendor contract.** `CLAUDE.md`'s own rule: a vendor is only a
  target if it publishes a versioned, machine-readable spec.

## The three things to build, in order

### 1. The dev console shows this repository and nothing else

`scripts/seed_console.py` is owned by another session and stays. What changes is which database the
**dev** console points at.

- Index this repository for real: `call_site` rows from `src/sync/**` for the vendor surfaces named
  above, at the `static` rung, through the existing INDEX stage.
- Point the dev API at that graph rather than the seeded one.
- **The seed does not disappear** — it becomes what it always should have been: the fixture the
  *tests* and the *empty-state walk* use, not the thing the owner looks at.

**The honesty consequence, and it is a feature.** Our own graph will be sparse at first: few call
sites, few vendor changes, possibly zero findings. The console already renders that correctly and it
was proven on 2026-08-17 (`M14-W346`) — "No repository has been indexed, so nothing has been
searched" rather than a zero that reads as a clean bill of health. **A sparse honest console is the
demo.** It is what a design partner sees on day one, and we will be looking at the same screen they
do rather than at a fixture nobody else will ever have.

### 2. Every repair is recorded through the systems we already built

This is the half the owner asked to focus on, and almost all of it already exists. The gap is that
we have been recording repairs in `WORKLOG.md` prose and *not* in the machine-readable places built
for exactly this.

What exists and is already the right shape:

- **`migration_outcome`** — one row per repair *attempt*, with `terminal_status`,
  `abandon_reason` and `abandon_reason_code` from a twelve-member closed vocabulary (`B128`). The
  grain is an attempt, not a finding, and `CLAUDE.md` states it.
- **The checkpointer** — the node-by-node record of what a run did, which the workflow screen already
  renders, including the evidence that stopped an abandoned run.
- **`WORKLOG.md`** — one row per work item, already carrying the identifier on every commit.

**What is missing is one link: a repair we made by hand has no row.** Every fix in this repository
today is a commit and a WORKLOG line; none of them is in `migration_outcome`, so the corpus — the
thing that is supposed to teach routing which change kinds are mechanically safe — has only what the
automated loop produced.

**The proposal, deliberately small.** A repair recorded by hand gets a `migration_outcome` row with
its `terminal_status` and, when it failed or was abandoned, a reason code from the same closed
vocabulary. It is marked as human-authored rather than agent-authored, because a corpus that cannot
tell those apart cannot answer the only question it exists to answer — *what can Sync do
unattended*. `is_rehearsal` already sets the precedent for a boolean that keeps two kinds of row from
being confused.

**Do not** invent a parallel ledger. `.claude/rules/graph-grain.md` and the pipeline-discipline spec
already govern this table; a second one would be a fact written twice, which this repository has
spent a week fixing before.

### 3. The loop that proves it

The measure is not "the console is prettier". It is: **an issue we hit while building is repaired
through the pipeline, and the repair is queryable afterwards.**

The first candidate is already sitting there. `CLAUDE.md` records that the `ClaudeAgentOptions`
surface changed under us and cost real time. If the SIGNAL stage picks up a new `claude_agent_sdk`
release, DETECT raises a finding against `runner/claude_sdk.py`, and REMEDIATE opens a pull request
that this repository's own CI gates — that is the whole product, demonstrated on ourselves, with the
corpus row to prove it happened.

If it abandons instead, that is equally publishable and arguably more useful: `abandon_reason_code`
says why, and the reason a repair is not mechanically safe is exactly what the routing layer is
supposed to learn.

## What this plan refuses

- **No fabricated findings to make the console look busy.** If our graph holds three call sites, the
  console shows three. The empty-state work exists precisely so that reads as honest rather than
  broken.
- **No second ledger**, per above.
- **No claim that Sync caught a bug it did not.** The `NameError` is recorded as a repair, not as a
  detection.
- **No removal of the seed.** Tests and the empty-state walk depend on it, and deleting a fixture to
  make a point would break the guard that proves the console handles absence.

## Sequence, and who owns each piece

1. **Index this repository into a graph the dev console reads.** INDEX and the dev loop —
   coordination needed with whoever owns `scripts/` and `src/sync/index`.
2. **Point the dev console at it**, leaving the seeded database for tests and the empty-state walk.
   Lane B, once (1) exists.
3. **Add the human-authored marker and record repairs into `migration_outcome`.** Schema and writer
   are Lane E's `src/sync/graph`; the vocabulary already exists.
4. **Take one real vendor drift end to end** and publish the corpus row, whichever way it ends.

Steps 1 and 3 are outside Lane B's files. This plan is written so that they can be assigned rather
than assumed, and so nobody builds a parallel version of a system we already have.

---

# How to organise codebases and testing so a reader understands it at a glance

The owner's second instruction: **the main codebase is for systems, and other APIs and vendors are
grouped by test repositories that are easy to understand.** Most of the machinery for this already
exists and is not organised the way that sentence describes, so this section is mostly *naming and
connecting* rather than building.

## What already exists, so nothing here is rebuilt

- **`benchmark/corpus/repositories.yaml`** — five real repositories pinned by commit, with a
  `tree_digest` that refuses a moved tree, materialised by `scripts/fetch_corpus_repositories.py`
  into the gitignored `.cache/corpus/`. Argued in `benchmark/corpus/README.md`.
- **`docs/superpowers/specs/2026-07-27-sync-adapter-targets.md`** — which vendors get adapters, in
  what order, with the discovery mechanism (`.stats.yml` in Stainless-generated SDKs).
- **`scripts/seed_console.py`** — the synthetic fixture, owned by another session.

The gap is not a missing system. It is that these three answer *different* questions and a reader
cannot tell from a directory listing which repository is for which purpose.

## The four tiers, each with one job

| Tier | What it is | The question it answers | Where it lives |
|---|---|---|---|
| **0 — the systems codebase** | this repository | *Does Sync work on the code we actually write?* | `src/`, `web/` |
| **1 — per-vendor probes** | one small repository per vendor surface, deliberately narrow | *Does the adapter and detector for **this one vendor** work?* | `benchmark/corpus/`, grouped by vendor |
| **2 — the scored corpus** | real third-party applications, pinned | *Does it work on code nobody wrote for us?* | `benchmark/corpus/repositories.yaml` |
| **3 — the synthetic fixture** | `seed_console.py` | *Does the console render every state, including the ones real data rarely produces?* | `scripts/` |

**The reason to separate 1 from 2** is that they fail differently and a single list hides it. A
per-vendor probe failing means *our adapter for that vendor is wrong*. A corpus repository failing
means *our engine is wrong on real-world code*. Today both would show up as "the corpus is red", and
whoever picks it up has to read the diff to find out which kind of problem they have.

**The reason to keep 3** is the one already proven: the empty-state and abandoned-run screens were
only reachable from data a real repository does not conveniently produce.

## Making tier 1 legible, which is the actual ask

One directory per vendor, named for the vendor, holding the smallest repository that exercises it:

```
benchmark/corpus/
  repositories.yaml          # tier 2, unchanged
  vendors/
    anthropic/               # our own SDK surface, the one that has already bitten us
    openai/
    stripe/
    cloudflare/
```

Each vendor directory carries a `README.md` of at most a paragraph answering three questions, because
a fixture whose purpose is not written down becomes a fixture nobody dares delete:

1. **Which vendor surface** it exercises, and where the machine-readable spec comes from.
2. **What drift it is pinned to reproduce** — the known change the detector should raise.
3. **What a pass and a failure each mean**, in the terms of tier 1 above.

The ordering of which vendors get a directory is **not a new decision**: `2026-07-27-sync-adapter-targets.md`
already ranks them by bindability, and this structure should follow that ranking rather than
re-litigate it.

## What testing looks like once it is organised this way

- **Tier 0** runs in the ordinary gate. Its findings appear in the dev console, which is the first
  half of this plan.
- **Tier 1** is the fast per-vendor check: small, cheap, and the thing to run when an adapter
  changes. A failure names a vendor.
- **Tier 2** is the scored benchmark, which already exists and already refuses a moved tree.
- **Tier 3** is what the console's own tests and the empty-state walk read.

**One rule that keeps the tiers from collapsing into each other:** a repository belongs to exactly
one tier, and the tier is written in its README. The failure this prevents is the one this project
has already had twice — a fixture used for two purposes, changed for one of them, silently breaking
the other.

## What this section deliberately does not decide

Which vendors get a tier-1 probe first, and how many. That follows the adapter-target ranking and the
milestone, and inventing an order here would be a second authority for a question one document
already answers.
