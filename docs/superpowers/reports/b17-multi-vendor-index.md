# B17 — the indexer stops being Stripe's

**Date:** 2026-07-29
**Branch:** `stroland02/m1-forge`
**Files owned:** `src/sync/index/typescript.py`, `src/sync/index/python_lang.py`,
`src/sync/index/sdk_bindings.py` (new), `tests/test_multi_vendor_index.py` (new), five new
fixture repositories.

`docs/superpowers/specs/2026-07-29-sync-adaptive-vendor-substrate.md` names
`_SDK_PACKAGE = "stripe"` as the highest-value defect in the system, and step 1 of its sequence
as "un-hardcode the indexer". This is that step.

## Where the package name comes from now, and why

A language adapter reads an optional `sdk_bindings` attribute off each vendor adapter it holds:
a mapping from language id to the packages that vendor ships for that language. A vendor that
declares nothing gets a binding derived from its `vendor_id`.

Three options were open, and the argument for the third is the reason the other two lose.

**Derived from `vendor_id` alone** is what the brief warns against, and it is wrong the moment
a vendor ships a scoped npm package. `stripe` being simultaneously the vendor id, the npm
package, the PyPI distribution, the import name and the symbol root is the coincidence that hid
this defect for as long as it hid.

**Supplied to the language adapter alongside the vendor adapter** — a second constructor
argument — puts the fact in the caller. `cli.select_language_adapter` would then have to know
which package each vendor ships, which is the vendor knowledge the registry exists to keep out
of the entry point. `sync.signals.registry`'s own docstring records `cli.py` constructing
`StripeAdapter` by name as the bug it was written to fix.

**Read off the vendor adapter** is what shipped. The fact belongs to the vendor, and the vendor
object is already in hand at the only place it is needed. Read with `getattr` rather than added
to the `VendorAdapter` protocol, which this task does not own and could not widen without
failing every existing adapter's `runtime_checkable` test to add a capability none of them was
asked for. `PythonAdapter.unverifiable_reason` already reaches `sync.remediate` this way, so it
is the established shape here rather than a new one.

Four names, not one, and they come apart as soon as the vendor is not Stripe:

| vendor id | package (manifest) | module (source) | symbol root |
|---|---|---|---|
| `stripe` | `stripe` | `stripe` | `stripe` |
| `slack` | `@slack/web-api` | `@slack/web-api` | `slack` |
| `slack` | `slack-sdk` | `slack_sdk` | `slack` |

`module` earns its field on the Python side only: an npm package *is* its module specifier,
while PEP 503 folds `_` to `-` in a requirement and never in an `import` statement. A binding
with one field for both indexes nothing in a repository that depends on `slack_sdk`.

### The fallback is a default, not a claim

No adapter in this repository declares `sdk_bindings`, so every one of them takes the
`vendor_id` derivation. That keeps Stripe working with no vendor-side change — the M0
acceptance path is untouched — and it makes Twilio work for the first time, also with no
vendor-side change, because `twilio` is its package too.

It is safe in the one direction that matters. A wrong derivation **fails to resolve**: the
manifest declares no package by that name, `matches` answers False, and
`cli.select_language_adapter` raises naming what it tried. It cannot resolve *incorrectly*,
because a symbol rooted at the wrong name is in no vendor's map. That is the asymmetry the
design document rests on, applied here rather than restated.

A vendor that *does* declare bindings has spoken completely: a missing language entry yields no
bindings for that language rather than falling back. Falling back there would restore the guess
one level up from where it was removed, and the vendor with a `@scope/name` package is exactly
the vendor for whom the guess is wrong.

### What I need from the registry, and did not take

The end state is that the package is registry data, next to the builder that already routes a
vendor id to an adapter. The exact shape, if `sync.signals` wants to own it:

```python
# on the vendor adapter, or returned beside it from `prepare_vendor` / `load_vendor`
sdk_bindings: Mapping[str, Sequence[SdkBinding]]   # language_id -> the packages it ships
```

`SdkBinding` is `sync.index.sdk_bindings.SdkBinding` — three required strings, `package`,
`module`, `symbol_root`. I did not touch `sync.signals`; the `getattr` composes with either
source, so whichever side ends up holding the data needs no change here.

## One pass, several vendors

**One instance that knows several vendors.** `TypeScriptAdapter` and `PythonAdapter` both take
`vendor_adapters=(...)` in addition to the existing `vendor_adapter=`.

The alternative — one instance per vendor — parses every source file once per vendor. Both
adapters make two full traversals (find clients, then find calls), and parsing dominates
indexing; matching several package names inside one traversal costs a set comparison per import
statement. The latency specification's rule is that cost should track what we cannot make
faster — the customer's source — rather than what we choose, and a catalogue that multiplies
parse count is the second thing.

That claim is pinned rather than asserted: `test_the_tree_is_parsed_the_same_number_of_times_whatever_the_vendor_count`
counts parses through a proxy over the real parser and asserts one vendor and three vendors
produce the same count. Its Python twin does the same.

Attribution had to change with it. `_client_identifiers` returned `set[str]`; it now returns
`dict[str, set[int]]`, mapping an identifier to the bindings it may stand for. A name is
carried against *every* binding that could have bound it, because two vendors' clients can be
spelled `client` in two files and nothing available here distinguishes them. The symbol lookup
decides: each vendor answers for its own root, and a wrong pairing resolves to nothing.

`sdk_version` is per binding for the same reason — a repository declaring two SDKs pins two
versions, and a call site carrying the wrong one describes a dependency the customer does not
have.

## Which SDK shapes this covers, and which it does not

**Covered.** A member chain rooted at a constructed client.

- TypeScript: `import X from 'pkg'` or `import { X } from 'pkg'`, then `const c = new X(...)`,
  then `c.a.b(...)` with at least two segments after the root.
- Python: the same, plus `import pkg` / `import pkg as p`, where the module itself is the client
  — the difference `python_lang.py`'s docstring already recorded, now carried per binding.
- Repository-wide name matching, so a client built in one module resolves at call sites in
  another.

**Not covered, and none of it is closed by parameterising the package name:**

- **A chain broken by a call in its middle.** `client.insights.v1.calls(sid).fetch()` is how
  `twilio-node` addresses a single resource, and `_member_chain` refuses the whole expression,
  so the symbol `twilio.insights.v1.calls.fetch` — which the Twilio symbol map *does* hold — is
  never formed. This is the largest gap and it is Twilio-shaped: the create/list half of
  Twilio's operations index today and the fetch/update/delete half does not.
  `tests/fixtures/ts/twilio` carries one of each, and
  `test_a_call_through_an_instance_resource_is_not_indexed` pins the boundary so it is read
  rather than discovered.
- **Free functions.** `import { createCharge } from 'pkg'; createCharge(...)` has no root
  identifier and no chain.
- **A client obtained from anything but `new`** (TypeScript) or a direct constructor call
  (Python) — a factory, a dependency-injection container, a function return.
- **Renamed re-export.** `import { stripe as billingClient } from './client'` — pre-existing,
  documented, unchanged.
- **A dotted module binding.** `import a.b.c` binds the name `a`, and recording the full path
  as a client root would produce a name no call site writes. No binding today is dotted;
  `_watching` states the gap rather than half-implementing it.
- **Nesting that is not a flat chain.** The spec names `openai.chat.completions.create` as
  differently shaped; a flat chain of that depth does resolve, so what remains untested is
  whether Stainless SDKs are reached at all — I had no fixture and did not guess.

The honest one-line summary: this change stops the *vendor's name* being welded into the
indexer. It does not stop the *SDK's shape* being welded in, and the shape rule is still "member
chain rooted at a constructed client".

## A vendor whose package name differs from its vendor id

Yes, in the ecosystem; no, among vendors this repository registers.

`_BUILDERS` holds `stripe` and `twilio`, and both ship a package named exactly their vendor id,
which is why the assumption survived. The divergence is ordinary elsewhere: Slack ships
`@slack/web-api` on npm and `slack-sdk` on PyPI, GitHub ships `@octokit/rest`, SendGrid ships
`@sendgrid/mail`. Slack is the case the fixtures use, because it diverges on all three axes at
once — package ≠ vendor id, module ≠ package, symbol root ≠ either.

So the honest statement: **the divergence is demonstrated against a fixture vendor, not against
a registered one.** No adapter in this repository exercises it, and the first real one to need
it will be the first to declare `sdk_bindings`.

## Mutations run, one per claim

Each mutation was applied to the shipped source, the suite run, and the source restored.
Every one was caught.

| Mutation | Test that failed |
|---|---|
| `matches` compares against the literal `"stripe"` again | `test_matches_reads_the_declared_package_rather_than_a_constant` |
| symbol built from `binding.package` instead of `binding.symbol_root` | `test_a_vendor_whose_package_is_not_its_vendor_id_is_indexed` |
| `sdk_version=versions[0]` for every vendor (TypeScript) | `test_one_adapter_indexes_two_vendors_in_one_pass` |
| `vendor_id` taken from `_bound[0]` rather than the resolving pair | `test_one_adapter_indexes_two_vendors_in_one_pass` |
| traversal wrapped in a per-vendor loop (TypeScript) | `test_the_tree_is_parsed_the_same_number_of_times_whatever_the_vendor_count` |
| `_member_chain` walks through a call in the middle of a chain | `test_a_call_through_an_instance_resource_is_not_indexed` |
| Python `_watching` compares the import against `binding.package` | `test_the_python_import_name_is_read_rather_than_the_distribution_name` |
| `sdk_version=versions[0]` for every vendor (Python) | `test_one_python_adapter_indexes_two_vendors_in_one_pass` |
| traversal wrapped in a per-vendor loop (Python) | `test_the_python_tree_is_parsed_the_same_number_of_times_whatever_the_vendor_count` |
| a declared-but-empty language entry falls back to the vendor id | `test_a_vendor_declaring_no_binding_for_this_language_contributes_nothing` |
| `_declared` always answers None, so a declared binding is ignored | `test_a_vendor_whose_package_is_not_its_vendor_id_is_indexed` |
| `default_binding` returns empty strings | `test_a_vendor_declaring_nothing_falls_back_to_its_vendor_id` |
| `matches` returns True when no vendor is held | `test_an_adapter_with_no_vendor_matches_nothing` |

Two of these are worth naming rather than tabulating.

The tenth **survived its first version of that test** and is the reason the test now uses Stripe
rather than Slack. Written against Slack, the fallback the mutation restores produces a binding
for the package `slack`, which the Slack fixture does not declare, so the test passed either
way. Rewritten against a Stripe vendor that declares a TypeScript binding only, the fallback
would index `py/simple` *and be right by luck* — which is exactly the failure mode the rule
exists to forbid. A test that cannot fail is worse than no test, and this one could not until it
was moved to the vendor where the wrong answer looks correct.

The sixth was run against its single test rather than the file, because the file runs with `-x`
and an earlier failure would have masked it.

## What the alias coverage now proves that it did not before

`50b391e` added `tests/fixtures/py/aliased` and `tests/test_python_aliases.py`, covering
`import stripe as s`, `from stripe import StripeClient as C`, and a dictionary passed
positionally. At the time those branches had been written and never executed; the tests proved
they worked.

After this change they prove something stronger, because the data structure underneath them
changed shape. `_client_identifiers` returned `set[str]`: an alias only had to *be in the set*,
and the symbol root came from a module constant, so attribution was free and unfalsifiable. It
now returns `dict[str, set[int]]`, and an alias has to be attributed to the binding that bound
it — the symbol root, the vendor id and the SDK version on every resulting call site are all
read through that index.

So the alias tests now assert that **an aliased import carries its vendor with it**, not merely
that an aliased import is recognised. Concretely: `import stripe as s` has to land under the key
`s` pointing at the Stripe binding, and `from stripe import StripeClient as C` has to survive
two hops — the aliased class name into the per-file `imported` map with its owners, then the
assignment `client = C(...)` into the repository-wide map with those owners intact. A defect at
either hop now produces a call site attributed to the wrong vendor or none at all, where before
it could only produce no call site.

They are also, straightforwardly, the regression net that made this refactor safe. Every alias
branch in `_client_identifiers` was rewritten in this task. Without `50b391e` those rewrites
would have been unexecuted code changed into different unexecuted code, and the suite would have
stayed green either way.

The limit worth stating: a single-vendor test cannot distinguish index 0 from index 0. What the
alias tests pin is that the attribution *path* is intact for the fallback binding; the
multi-vendor tests are what pin that two indices stay apart. Neither is sufficient alone.

## Not in the brief, and worth knowing

**The multi-vendor capability is built and not yet reachable from the CLI.** `sync run` takes
one `--vendor`, and `cli.select_language_adapter` passes exactly one adapter through
`vendor_adapter=`. I did not change `cli.py` — it is outside the files this task owns — so
nothing in a real run indexes two vendors at once yet. The wiring is one call site, and it is
the natural first half of the spec's step 2.

**A new module.** `src/sync/index/sdk_bindings.py` holds the binding type and the resolution
rule. Both indexers need it, and duplicating the fallback and the "declared means declared
completely" rule into two files is how the two drift apart. It is a new path, so it cannot
conflict textually with concurrent work.

**Fixtures added, none removed.** `ts/slack`, `ts/two_vendors`, `ts/twilio`, `py/slack`,
`py/two_vendors`. Every Stripe fixture and every existing indexer test is untouched.

**`_sdk_version` changed signature** in both adapters, from `(repo)` to `(repo, package)`. It is
private and has no callers outside its own module.

**Both indexers now accept construction with no vendor at all.** `TypeScriptAdapter(vendor_adapter=None)`
is what `tests/test_remediation_graph.py` and `tests/test_tsc_verify.py` already do — they reach
`prepare` and `static_verify` and never index. It previously matched a Stripe repository despite
holding no vendor; it now matches nothing, which is the honest answer and is pinned.

## The rebase is not clean, and the reason is that this task shipped twice

The final rebase onto `origin/main` conflicts. `a4161ad fix: take the SDK package from the
vendor, so a second vendor can be indexed at all` landed upstream and is the same task: both
indexers conflict (`UU`), and `tests/fixtures/ts/twilio/package.json` and
`tests/fixtures/ts/twilio/src/insights.ts` are add/add collisions because we both reached for a
Twilio fixture at the same path. Per the brief I stopped rather than resolving in favour of my
side. Branch is at `c7f3cf2`, unrebased, work intact.

The two solutions agree on the load-bearing decision and diverge on three others.

**Agreed.** The package comes from the vendor adapter, through an optional `sdk_bindings`
attribute keyed by language id, read with `getattr` rather than by widening `VendorAdapter` —
both citing `PythonAdapter.unverifiable_reason` as the precedent. Independent arrival at the
same shape is worth something.

**They have, and I do not:**

- **Vendor adapters actually declare their bindings.** `a4161ad` edits
  `sync.signals.stripe.adapter` and `sync.signals.twilio.adapter`. My brief forbade touching
  `sync.signals`, so my branch ships the mechanism with nothing declaring through it and a
  `vendor_id` fallback carrying the registered vendors. Theirs is the real wiring.
- **No fallback, and a better argument against one than I had.** They reject deriving from
  `vendor_id` because an `mcp:`-prefixed id can never be a package name, and four watched MCP
  servers plus four configured vendors would all be claiming packages they do not ship. My
  fallback fails loudly rather than wrongly, but theirs needs no such defence.
- **A widened client rule.** `twilio-node` documents building a client by calling the package's
  default export, so `const client = Twilio(sid, token)` binds nothing under the
  `new Imported(...)` rule inherited from Stripe. They fixed that; I did not, and an idiomatic
  Twilio repository is invisible to my version.

**I have, and they do not:**

- **The symbol root as a field of its own, and this one is a defect in what landed.** Upstream,
  TypeScript's `sdk_bindings` entry is `{"package": "stripe"}` and line 406 builds
  `symbol = f"{self._package}.{chain}"` — so the npm package is simultaneously the manifest key,
  the import specifier and the root of the symbol. That holds for `stripe` and `twilio` and
  fails for every scoped package: a Slack binding of `@slack/web-api` emits
  `@slack/web-api.chat.postMessage`, which no symbol map holds. `@octokit/rest`,
  `@sendgrid/mail` and `@aws-sdk/client-*` are the same shape. The Python side has the same
  conflation from the other end — `symbol = f"{self._module}.{chain}"` roots the symbol at the
  import name, so a vendor would have to key one map by `slack_sdk` in Python and by
  `@slack/web-api` in TypeScript. Their commit message states "TypeScript's npm name is at once
  the manifest key, the import specifier and the root of the symbol"; that sentence is true of
  unscoped packages only, and both fixtures upstream are unscoped, so nothing catches it. My
  `SdkBinding.symbol_root` is the third field this needs.
- **Multi-vendor in one pass.** `vendor_adapters=(...)`, identifier-to-binding attribution,
  per-vendor `sdk_version`, and a parse-count test asserting the traversal cost does not scale
  with the catalogue. Upstream is one vendor per instance (`self._vendor`, `self._package`).
  This was an explicit requirement of my brief and appears to have been absent from theirs.
- **A pinned test for the mid-chain-call limitation**, so the Twilio fetch/update/delete gap is
  documented rather than latent.

**Recommendation.** Take `a4161ad` as the base — it has the real vendor-side wiring and the
callable-default-export rule — and port three things onto it: `symbol_root` as a distinct
binding field with the scoped-package test, the multi-vendor constructor with the parse-count
test, and the mid-chain-call limitation test. That is a smaller and safer change than resolving
the conflict in either direction. The fixture collision should resolve by keeping their
`ts/twilio` and renaming mine, since theirs carries the factory-construction case.

## Gates

Run on `stroland02/m1-forge` at `c7f3cf2`, rebased onto `origin/main` **before** the work and
**not** rebased after, because the rebase conflicts (above):

- `uv run pytest` — full suite
- `uv run lint-imports` — `sync.core depends on nothing KEPT`, 1 contract kept, 0 broken
- `uv run python scripts/lint_encoding.py src scripts tests` — exit 0
- `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` — exit 0
