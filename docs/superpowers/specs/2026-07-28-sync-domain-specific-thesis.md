# Sync as a Domain-Specific Solution

**Date:** 2026-07-28
**Status:** Thesis. One architectural consequence is concrete enough to build and is specified
at the end; the rest is framing that should change what gets prioritized.
**Scope:** What NVIDIA's domain-specific approach actually transfers to a solo software
project, the textbook idea Sync is productizing, and the gap that reading it exposes.

## Provenance

Stated up front because the argument is only as good as its sources.

- **VERIFIED this session:** NVIDIA's founding and near-death facts; Coccinelle's existence,
  purpose, terminology, and paper trail with authors and venues.
- **NOT VERIFIED:** the specific measurements inside the EuroSys 2006 paper — the PDF returned
  404 and the CACM Turing lecture returned 403. Numbers from that paper are deliberately absent
  below rather than approximated.
- **Textbook knowledge, not fetched:** Hennessy & Patterson's domain-specific architecture
  guidelines, from *Computer Architecture: A Quantitative Approach*, 6th edition, Chapter 7.
  Stated because they are stable and well known, flagged because they were not read today.

## The NVIDIA pattern

The facts, and then the part that transfers.

Founded 5 April 1993 by Jensen Huang, Chris Malachowsky, and Curtis Priem, agreed at a Denny's
on Berryessa Road. The bet was that graphics was worth a dedicated processor when the industry's
answer was a general-purpose CPU. Huang's stated reasoning is the interesting part: video games
were "one of the most computationally challenging problems" *and* had "incredibly high sales
volume" — a hard problem attached to a market large enough to fund solving it.

The first product failed. NV1 used quadrilateral primitives; Microsoft's DirectX standardized on
triangles. The domain was right and the interface was wrong. In 1996 the company cut from about
100 employees to 40. When RIVA 128 shipped in August 1997 there was **one month of payroll left**.
It sold roughly a million units in four months.

Then, in the early-to-mid 2000s, over a billion dollars went into CUDA — making the graphics
processor programmable for general computation, years before the workload that justified it
existed.

### What transfers, and what does not

**Does not transfer:** the capital, the fab relationships, the billion-dollar bet. A solo
self-funded project cannot buy a decade of unprofitable investment.

**Transfers, and is free:**

1. **Pick a domain where the general-purpose tool is structurally wrong.** Not slower —
   *structurally wrong*. A CPU rendering triangles is not a slow GPU; it is the wrong shape. A
   general coding agent pointed at "keep my API integrations working" is likewise the wrong
   shape: it re-derives, from scratch, per session, what a precomputed binding would already
   know.

2. **The first interface can be wrong while the domain is right — so make the interface cheap
   to replace.** NV1's quads were a bet on a representation, and the bet lost. Sync has already
   made analogous bets: `path_ptr` as a name, `Severity`'s four values, the tool schemas. The
   lesson is not "guess better," it is to keep the *domain* commitment deep and the *interface*
   commitment shallow. Frozen tool schemas and a `VendorAdapter` protocol are that discipline
   already; the corpus schema is where it matters most and where it is hardest.

3. **Constraint forces the discipline that survives.** One month of payroll meant NVIDIA could
   not afford a silicon respin, so it verified before taping out. Solo and self-funded is the
   same constraint in a different currency: there is no budget for a wrong patch against a
   customer's repository. That is precision-over-recall, default-deny routing, and
   nothing-reaches-a-PR-unverified — already committed, and now with a reason that is
   structural rather than stylistic.

4. **Own the domain's stack, not one component.** NVIDIA's durable advantage is not the die; it
   is CUDA, cuDNN, and the domain SDKs above them. Applied here: Sync's moat is not the detector
   and not the patcher. It is the binding graph, the schema, the change feed, and the migration
   corpus — the layer everything else must go through.

5. **Invest ahead of the domain's arrival.** CUDA preceded deep learning by years. Sync's
   equivalents are cheap rather than expensive, and both are already identified: the
   `migration_outcome` corpus and the `observed_shape` baseline. Neither can be backfilled.
   Writing them before they pay is the entire move.

## The textbook idea Sync is productizing

The user's premise — that the idea usually already exists and the work is getting it to a
product — is correct here, and specifically so.

**Sync's problem has a name in the literature: *collateral evolution*.** From INRIA's Coccinelle
project, verified today: collateral evolutions are "necessary updates to client code when
library APIs change... renaming functions, adding context-dependent arguments, or restructuring
data."

That is Sync's entire problem statement, published in 2006.

The research line:

| Paper | Authors | Venue |
|---|---|---|
| Understanding Collateral Evolution in Linux Device Drivers | Padioleau, Lawall, Muller | EuroSys 2006 |
| Documenting and Automating Collateral Evolutions in Linux Device Drivers | Padioleau, Lawall, Muller, Hansen | EuroSys 2008 |
| Semantic Patches for Documenting and Automating Collateral Evolutions | Padioleau, Hansen, Lawall, Muller | PLOS 2006 |
| How Often Do Experts Make Mistakes? | Palix, Lawall, Thomas, Muller | ACP4IS 2010 |

And it shipped. **Coccinelle** is a program matching and transformation engine providing
**SmPL**, the Semantic Patch Language. Its semantic patches live in the Linux kernel's own
`scripts/` directory. This is not a proposal in a paper; it is twenty years old and in
production in the largest C codebase in the world.

### What they solved, and the half they left

Coccinelle made collateral evolution **executable**. A semantic patch is declarative, applies
across thousands of files, and is deterministic.

It did not make collateral evolution **discoverable**. Someone has to notice the API changed,
understand what it means, and write the patch. In the Linux kernel that someone exists, because
the API author and the client authors are in one repository with one mailing list.

**For a company consuming a third-party API, nobody occupies that role.** The vendor ships the
change and does not know who calls what. The consumer discovers it from an exception. There is
no shared repository, no shared review, and no one whose job is to write the semantic patch.

That gap is the product:

> Coccinelle solved the transformation half of collateral evolution and assumed a human who
> knows what changed. Sync's binding graph is the discovery half, and a model can now write the
> patch the human never had time to write.

The last clause is what changed since 2008 and why this is buildable now rather than then.

## The domain-specific architecture guidelines, transposed

Hennessy & Patterson devote a chapter to domain-specific architectures and give five design
guidelines. Four describe what Sync already does — arrived at independently, which is a good
sign — and the fifth is a gap.

| # | H&P guideline | Sync's equivalent | Status |
|---|---|---|---|
| 1 | Dedicated memories, to minimize data movement | The ADG is the dedicated memory. A binding is computed once and queried many times, never re-derived per session. `FeedCache` is the same principle for vendor artifacts. | **Done** |
| 2 | Spend the resources saved by dropping general-purpose features | Sync deliberately does not understand the codebase. It indexes call sites that bind to vendor operations and ignores everything else, spending what it saves on binding confidence — the `static` → `resolved` → `observed` ladder. | **Done** |
| 3 | Use the easiest parallelism that fits the domain | Findings are independent, so parallelism is per-finding and embarrassingly so. `locate → patch → verify` is explicitly *not* parallelized: it is a data dependency, and the latency spec says so. | **Done** |
| 4 | Reduce data size and type to the simplest the domain needs | Shapes, never values. Abstract edit scripts, not textual diffs. Salted hashes, not keys. Arrived at for privacy and threat-model reasons; it is also guideline 4 exactly. | **Done** |
| 5 | **Use a domain-specific language** | **Sync has none.** Tier-0 codemods would be ad-hoc Python; the agent edits files directly. | **Gap** |

Guideline 5 is the finding.

## The consequence: a migration language

Coccinelle's central artifact is not the engine, it is **SmPL** — the language that makes a
transformation a reviewable, reusable, checkable object rather than a diff.

Sync currently has no such object. The agent edits files, `tsc` checks the result, and what
ships is a diff. That has four costs, and they compound:

- **Review does not amortize.** A reviewer reads a diff per repository. A semantic patch is read
  once and trusted everywhere it applies.
- **Nothing is reusable.** The same Stripe change, at a thousand customers, is a thousand
  independent agent runs producing a thousand diffs. One patch would serve all of them.
- **The corpus stores the wrong thing.** `migration_outcome.edit_script` is specified as
  "abstract edit ops, not a textual diff," which is the right instinct without a language to
  express it in. A migration language *is* that column's type.
- **The feed ships only half the value.** `2026-07-25-sync-positioning-and-open-core.md` argues
  the un-scrapeable asset is "each change carrying a verified migration recipe." A recipe needs
  a notation. Without one the feed publishes what changed and stays silent on what to do.

### Do not invent the language — the prior-art check changed this recommendation

An earlier draft of this document proposed designing a migration DSL. Running the prior-art
check first, rather than listing it as future work, killed that proposal. It is recorded here
rather than quietly deleted, because "design a new language" is exactly the kind of idea that
survives on plausibility when nobody checks.

**`ast-grep` already is the notation.** Verified today:

- **Declarative YAML rules** with `pattern`, `rule`, `fix`, `transformation`, and `rewriter` —
  matching *and* rewriting, not search alone.
- **TypeScript is supported**, which is Sync's M0 language, alongside Python, Go, Rust, Java
  and others.
- **`ast-grep-py` 0.45.0 on PyPI, MIT licensed**, Python 3.8+, wheels for Windows, macOS and
  Linux, actively released since November 2023. Sync is Python; this is an import, not an
  integration.
- **Built on tree-sitter — which Sync already depends on** (`tree-sitter`,
  `tree-sitter-typescript` are in `pyproject.toml` for the INDEX stage). The parsing substrate
  is shared rather than duplicated.

MIT is compatible with the open-core split, and a rule is a YAML document — reviewable by a
human, storable in a column, and shippable in the feed without inventing a serialization.

The honest limitation, stated because it bounds the idea: **ast-grep matches AST structure;
Coccinelle's SmPL matches control flow**, which is why SmPL can express "this call is not
already guarded on that path" and an AST pattern cannot. For API-shaped migrations —
rename an operation, rename a property, add a required argument, drop a read of a removed
field — structural matching is very likely sufficient, and "very likely" is a claim the corpus
should settle rather than this document.

**OpenRewrite is the Java world's answer to the same problem** — recipes, a catalogue, and
Moderne commercializing it — and it is the wrong stack here. Its recipes are Java, its focus is
Java, and its TypeScript story is not stated in its own overview. Noted so it is not
rediscovered as an option every six months.

### The shape of the proposal

**The model's job becomes emitting an `ast-grep` rule, not editing code.** That inverts the
current pipeline in the direction every other commitment already points:

- **Determinism moves to where it belongs.** Application of a patch is mechanical and testable.
  The model does the part needing judgement — reading a change and expressing the migration —
  and nothing else. This is the deterministic-engineering-times-agent split already adopted from
  Open Code Review, applied one level deeper.
- **The routing matrix gets a target.** `sync.route` currently names tiers with nothing behind
  tier 0, because a codemod has no notation. A migration language is what tier 0 *emits*, and
  tier 1 becomes "a templated patch with holes the model fills."
- **Verification gains a cheap layer.** A patch can be checked for well-formedness and for
  applying cleanly before `tsc` ever runs — earlier and cheaper than the current first gate.
- **The corpus becomes a corpus of migrations rather than of diffs**, which is the difference
  between data that generalizes across customers and data that does not.

**Scope discipline, because this is where the idea still gets dangerous even without inventing
a language.** The work is not a grammar; it is a small library of rule *templates* keyed to the
oasdiff rule kinds `sync.route` already classifies — rename an operation, rename a property, add
a required argument, drop a read of a removed field. Nine rows of routing suggest a comparable
number of templates. Tier 0 fills a template deterministically; tier 1 has the model fill the
holes; tier 2 keeps editing files directly.

The honest risk: a notation that cannot express a migration is worse than none, because the
fallback path has to exist anyway. So this is **additive**, and it earns its scope by
measurement. The share of real migrations expressible as an `ast-grep` rule is a number the
corpus produces, and it decides how far this goes — including whether the control-flow gap
above ever bites.

## What this changes about priorities

Nothing already committed is wrong. Two things move.

**Up:** the migration language, from unmentioned to the design work that unblocks tier 0, gives
`edit_script` a type, and gives the feed its recipe. It was the highest-leverage unbuilt idea in
the project, and it is cheap to prototype because the domain is small.

It is now built and is what tier 0 runs on. `src/sync/route/templates.py` emits the `ast-grep`
rules and owns the deletion and rename spans; `src/sync/remediate/literal_swap.py`,
`property_omit.py` and `parameters.py` are the deterministic strategies over it, composed by
`TieredRemediator` in `src/sync/cli.py:69`. What has not followed is the rest of the claim. `edit_script` is declared on
`MigrationOutcome` and no writer populates it, so the column this notation was meant to give a
type is uniformly null; and the feed's published fields (`FEED_FIELDS` in
`src/sync/signals/feed/publisher.py`) carry no migration recipe alongside the change.

**Confirmed, with a better reason:** writing `migration_outcome` and `observed_shape` before
they pay. That was justified by "cannot be backfilled." The stronger version is guideline 5 plus
CUDA: the substrate is built before the workload arrives, or it is not built at all.

**Reframed:** "we are a binding service" is right and undersells it. The binding is the
discovery half of a problem the literature named in 2006 and half-solved in 2008. Sync is the
other half, for the case the kernel never had — where the API author and the client author have
never met.

## Evidence still needed

Named so the thesis stays falsifiable.

1. **The measurements inside EuroSys 2006** — how many files a single collateral evolution
   touched, how long it took to propagate, and the error rate in manual updates. The PDF was not
   reachable today. This is the closest thing to a quantitative case for Sync existing, and it is
   currently uncited.
2. **Whether structural matching is enough.** `ast-grep` matches AST shape; SmPL matches control
   flow. The claim that API-shaped migrations do not need control-flow awareness is untested.
   The first template that cannot be written is the answer.
3. **The expressible share.** What fraction of real migrations a small template set covers.
   Below some threshold the notation is not worth its maintenance, and that threshold should be
   stated before building, not after.
4. ~~Whether anyone has already done this~~ — **checked, and it changed the recommendation.**
   `ast-grep` supplies the notation, so the proposal is adoption rather than invention. Running
   this check before writing the proposal, rather than after, is the process lesson: the last
   unchecked novelty claim in this project produced a moat estimate that had to be withdrawn.
