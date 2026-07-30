# M3-W96: the parameter reduction cannot bind a call site to the wrong operation, and can lie about coverage

`_PARAMETER = re.compile(r"\{[^}]*\}")`, defined identically in `symbols_typescript.py` and
`symbols_speakeasy.py`, collapses every brace-delimited span of a route to a bare `{}` before an
SDK's routes are compared against the specification's. `2026-07-29-typescript-symbol-reader.md`
left it as the module's one residual wrong-binding path:

> One residual wrong-binding path exists — an SDK interpolating a non-parameter where the spec
> writes one — but that is the documented `_PARAMETER` reduction shared with Speakeasy, not this
> reading.

This task constructed that input rather than reasoning about it. Two things came back.

**The claim is one level too strong.** The reduction is not on the path a call site resolves
through. `operation_for_symbol` builds its `OperationRef` from `ExtractedOperation.path`, which is
the SDK's route verbatim, and `_comparable` is called from nowhere but `report_extraction`. So a
colliding key cannot attach a vendor change to a call site the customer does not write.
`grep -rn "_comparable" src/` is the whole of the evidence: per flavour, its definition and three
uses, all three inside `report_extraction`, and no other reference anywhere in `src/`.

**What it can do instead is worse than it sounds.** A collision deflates the coverage denominator
and turns the cross-check's verdict on a route from "the specification does not declare this" into
"it does". The cross-check is what `symbols.py` calls "what makes the result refutable", and this is
the input on which it stops refuting. Both failures are silent, and both produce a number that reads
as a measurement.

**And it does not happen.** Over every specification this repository pins — 1,657 operations across
three vendors and four documents — no comparable key has more than one specification operation
behind it. The exposure is a latent shape, not a live defect, so the deliverable is the measurement
and the tests that fail the day it stops being true rather than a repair.

## Was a wrong binding reproduced? No. Here is the exact input, and what happened

Two constructions, both in `tests/test_parameter_reduction.py`.

### A. Two specification operations behind one comparable key

The SDK, hand-built because Stainless emits nothing like it:

```ts
export class Models extends APIResource {
  list() { return this._client.get('/v1/models', {}); }
  members() { return this._client.get(path`/v1/${workspaceID}/members`, {}); }
}
```

The specification, three operations:

    GET /v1/models
    GET /v1/{workspace_id}/members
    GET /v1/{organization_id}/members

The last two both reduce to `(GET, /v1/{}/members)`. What the reader does:

    stainless-typescript: 2 symbols extracted, reaching 2 of 2 specification operations (100.0%)

    spec_operation_count  2   (the vendor published 3)
    covered_count         2
    coverage_ratio        1.0
    unknown_to_spec       ()

**It does not pick one, does not pick the first, and does not decline — it never sees the
collision.** `report_extraction` builds `declared` as a `set` of comparable keys, so two operations
reducing to one key are one member of it. The denominator is one smaller than the number of
operations the vendor published, coverage reads 100% of an API the SDK reaches two thirds of, and
every number in the line is internally consistent with every other, which is exactly what makes it
unreadable as a warning.

### B. An SDK interpolating a non-parameter where the specification writes one

The residual path the earlier report named. The SDK interpolates a segment chosen at runtime:

```ts
  pinned() { return this._client.get(path`/v1/${this.channel}/models`, {}); }
```

against a specification declaring `GET /v1/models` and `GET /v1/{api_version}/models`. Extracted
route: `/v1/{this.channel}/models`. Reduced: `/v1/{}/models`, which is the specification's
`{api_version}` route. Result:

    unknown_to_spec       ()
    covered_count         2

The specification declares no route this SDK sends, and the cross-check says it declares one. The
control is what makes that mean something: the identical SDK against a specification declaring only
`GET /v1/models` reports `models.pinned` in `unknown_to_spec`. So the affirmation is produced by the
reduction meeting a parameterised specification route, not by the route being unremarkable.

**And the binding is still right.** Through `GeneratedSpecAdapter` on that same tree:

    OperationRef.operation_id   GET /v1/{this.channel}/models
    OperationRef.path           /v1/{this.channel}/models

not the specification's `/v1/{api_version}/models`. A `call_site` row carries the route the SDK
sends. That is the sentence the earlier report needed and did not have.

## Per-vendor collision count over the real pinned specifications

The count is `(method, reduced_route)` keys with more than one specification operation behind them,
where "operation" means distinct after `_route` — so the query marker this project already drops on
both sides is not counted as a collision. That reduction is deliberate and separately measured; only
what `_PARAMETER` merged is at issue here.

| Vendor | Document | Entries | Distinct after `_route` | Distinct after `_comparable` | **Collisions** |
|---|---|---|---|---|---|
| Anthropic | `anthropic_spec_operations.json`, the spec `anthropic.stats.yml` names | 131 | 121 | 121 | **0** |
| Vercel | `vercel_spec_operations.json`, the spec `workflow.yaml` names | 359 | 359 | 359 | **0** |
| Stripe | `.cache/specs/v2320.json`, 414 paths | 587 | 587 | 587 | **0** |
| Stripe | `.cache/specs/v2330.json`, 414 paths | 587 | 587 | 587 | **0** |

**Measured by** `test_the_reduction_collides_no_{anthropic,vercel,stripe}_operation`, which read the
committed operation-set fixtures and the pinned OpenAPI documents, group every entry by the
production `_comparable`, and assert no group holds two distinct routes. Not a script: the count is
producible from a test, so it is one, and it runs in the default suite. The two Stripe documents are
gitignored — 7.8 MB apiece, fetched by `scripts/fetch_measurement_inputs.py` — so those two skip
where nobody has fetched them.

Anthropic's 131 → 121 is the query marker and nothing else: all ten collisions under `_route` are a
`?beta=true` twin of a route already listed, for example `GET /v1/models` and
`GET /v1/models?beta=true`. Between 121 and 121 the parameter reduction merges nothing.

Stripe is in the table although neither flavour ever reads its SDK — it has a hand-written adapter.
It is there because injectivity over 490 operations could hold by luck, and 587 over 414 paths is the
largest real document this repository pins. A rule injective over the first and not the second would
be a rule holding by accident.

### Why zero is not luck

Two paths collide under this reduction exactly when they are identical after templating. The OpenAPI
Specification forbids that outright — templated paths with the same hierarchy and different templated
names must not both exist, because they are the same path — and gives `/pets/{petId}` beside
`/pets/{name}` as its example of an invalid document. So on the specification side the collision is
not a shape a valid document can carry, which is why four real documents produce four zeros and why
adding a branch for it would be validating a condition that cannot occur.

That argument covers one side and not the other. On the SDK side a brace span is not a parameter
name — it is whatever `_tagged_route` found inside a `${...}`, an arbitrary TypeScript expression —
and nothing forbids one of those from reducing onto a parameterised specification route. That is
case B, it is reachable, and it is the exposure that remains.

## What changed, and why declining beats picking

**No behavioural change.** Two docstring paragraphs, one per flavour, and sixteen tests.

The reason is the intersection of two constraints that leave nothing to build.

**Case A cannot occur on a valid specification**, so a branch that detected the collision would be
validation for a condition that cannot arise — the thing `CLAUDE.md` names directly. Its protection
is the measurement, held by a test over the real documents, which goes red the day a pinned document
acquires the shape.

**Case B cannot be fixed at `_comparable` without a guess.** The difference the reduction exists to
absorb and the difference it must not absorb are *the same shape*: `${modelID}` against `{model_id}`
is intended, `${this.channel}` against `{api_version}` is not, and both are a brace span in the same
position reducing to the same key.
`test_the_intended_absorption_and_the_residual_path_are_one_shape` asserts that equality, because it
is the argument. Telling them apart means deciding which brace spans hold parameter names, which is a
rule about one vendor's SDK conventions living in a reduction two generators share — the thing
`CLAUDE.md` forbids most explicitly, and the thing the brief forbade in advance.

**On declining versus picking, where a decline were available.** Nothing here picks, so the choice
did not arise as posed; and had it, declining a colliding key would still be wrong for a reason worth
recording. A decline drops the key from `declared`, which puts the SDK's route into
`unknown_to_spec` — loud, which is the attraction — but the disagreement it reports is the
reduction's, not the SDK's. `_route`'s own docstring carries what that costs: a cross-check that
fires on a difference in how two artifacts spell the same thing trains a reader to ignore it, which
is worse than no cross-check. It would also deflate the denominator a second time, from 2 to 1 on
case A, making the number worse rather than honest. **Neither picking nor declining is what this
wants; the reduction wanting a denominator that counts specification operations rather than
comparable keys is, and that is a change to `ExtractionReport` — see below.**

### The two docstring paragraphs

`_comparable` in both flavours now states that the reduction bears on the comparison and never on a
binding, and that a collision therefore costs the denominator and the cross-check's verdict rather
than resolving a call site elsewhere. That is not narration: it is the fact the earlier report got
wrong, it is not visible from `_comparable`'s own body — it requires knowing what
`operation_for_symbol` reads — and it is backed by
`test_the_reduction_is_not_on_the_path_a_call_site_resolves_through`. The Speakeasy paragraph also
records that its reduction is inert *in outcome* rather than unreached, with the two counts.

## What a decline here would cost, given that declines in this module are silent

The question matters even though nothing declines, because the next reader will reach for it.

`ExtractionReport` carries four things — `operations`, `spec_operation_count`, `unknown_to_spec`,
`covered_count` — and `render()` composes its line from those four. There is no field for a construct
the reader met and declined, which is the finding
`2026-07-29-typescript-symbol-reader.md` recorded across nineteen branches: every partial loss in
this module is silent, and the only two loud failures are the `UnrecognisedSdkShape` raises, both of
which need the SDK's shape to be *totally* absent.

So a decline at the comparable key would cost:

- **The operation, invisibly.** A declined key is a key the SDK's route cannot match, so the route
  lands in `unknown_to_spec` and reads to an operator as the SDK disagreeing with its own
  specification. On the Anthropic fixture that is five of the twelve symbols, reaching four
  distinct routes — every parameterised route it has — reported as a disagreement caused by our
  reduction.
  `test_a_parameter_spelled_differently_on_each_side_still_covers_its_operation` is the test that
  fails on any fix which declines that broadly.
- **The denominator, twice over.** The collision already removed one operation from it; declining
  removes the survivor too.
- **Nothing said about why.** `unknown_to_spec` carries an `ExtractedOperation`, not a reason. An
  operator reading the warning learns that a route did not match and cannot learn that two
  specification operations were indistinguishable, which is a different repair from a misread source.

**`ExtractionReport` should carry a decline, and this task did not add it.** That is the same
conclusion the previous task reached by a different route, it lives in `symbols.py`, and it changes
what all three flavours emit — so it is queued, not done as a drive-by, exactly as the brief
directed. The stronger version of the same change is a denominator counted in specification
operations rather than in comparable keys, which would make case A a visible number instead of an
invisible one.

## Does the Speakeasy flavour's inertness still hold? Yes, and it is inert in outcome, not unused

The `_PARAMETER` comment claims it from a measurement taken once against one checkout at v1.28.12,
and nothing held it. Re-measured against the committed 20-file tree and the full 359-operation
specification, with the reduction replaced by a pattern matching nothing:

| | With the reduction | Reduction disabled |
|---|---|---|
| `spec_operation_count` | 359 | 359 |
| `covered_count` | 15 | 15 |
| `unknown_to_spec` | `()` | `()` |
| `operations` | 15 symbols | identical |

So the claim holds. What the comment implies and does not say is that inert means inert *in
outcome*: the reduction rewrites **8 of the SDK's 15** readable routes and **258 of the
specification's 359**, and the verdicts agree anyway, because Speakeasy writes the document's own
parameter names through unchanged. Those two counts are pinned separately by
`test_the_speakeasy_reduction_is_inert_rather_than_unreached`, because a reduction that had quietly
stopped matching anything would satisfy every inertness assertion while proving nothing.

**One honest limit.** The original measurement was over a full `vercel/sdk` checkout, 349 request
modules and 352 symbols. That checkout is not on disk and is not committed, so this re-measurement is
over the committed subset — 15 symbols — against the whole specification. The property re-measured is
per-route and the subset carries eight parameterised routes across three resource families, so it
exercises the mechanism; it does not re-establish the 352-symbol figure.

### Is the overlay case it is kept for reachable? In mechanism yes, in effect no

`vercel/sdk`'s own `.speakeasy/workflow.yaml`, committed beside the fixture, declares
`overlays: [overlay-title.yaml]`. So this vendor really does apply an overlay to the specification
before generating, and the document the cross-check reads is not the document the SDK was generated
from. The condition the reduction is kept for is a property this generator has, not one imagined for
it, and `test_the_overlay_the_speakeasy_reduction_is_kept_for_is_declared_by_this_vendor` pins the
declaration so it goes red if a future tag drops it.

What that overlay actually does is **not** readable from what is committed. Only `workflow.yaml` is,
and its filename is the sole thing saying "title". The evidence that it renames no path parameter is
the agreement itself — all fifteen extracted routes resolve to routes the fetched document declares —
rather than the filename. So: reachable in mechanism, unexercised in effect, and the reduction is
holding a door nothing has yet walked through. Keeping it is right, and the reason is the mechanism,
not the observation.

## Mutation table

Harness: `--color=no`, exit code read rather than inferred, mutated text `compile()`d before any
run, `ERROR ` lines counted separately from `FAILED ` lines, and the restored baseline asserted green
afterwards — `restored baseline: exit 0, 0 failed, 0 errors`. Blast radius was
`tests/test_parameter_reduction.py` plus the three existing symbol-reader files, 93 tests.

The three known false-survival modes were all distinguishable and **none occurred**: no mutation
produced a `SyntaxError`, every exit code was 0 or 1, and colour was off throughout. One of the three
did fire while building the harness, against the harness rather than a mutation:
`pytest -p no:xdist` exits 4 with `unrecognized arguments: -n` because `-n auto` comes from
`pyproject.toml`, which is the UNREADABLE mode exactly as described. It is named here because a
harness that had read that as "no failures" would have reported nine survivals.

| # | Mutation | Target | Verdict | Tests killed |
|---|---|---|---|---|
| M1 | `_PARAMETER` → `\{.*\}`, so the span crosses two parameters | typescript | killed, exit 1, 7 failed | `test_the_reduction_collides_no_anthropic_operation`, `..._no_stripe_operation[v2320]`, `[v2330]`, `test_the_collision_measurement_can_fail`, `test_both_flavours_reduce_a_parameter_the_same_way`, plus 2 existing |
| M2 | `_PARAMETER` → a pattern matching nothing | typescript | killed, exit 1, 9 failed | `test_two_specification_operations_behind_one_key_deflate_the_denominator`, `test_a_collision_is_reported_nowhere`, `test_the_intended_absorption_and_the_residual_path_are_one_shape`, `test_an_sdk_interpolating_a_non_parameter_is_affirmed_by_the_cross_check`, `test_a_parameter_spelled_differently_on_each_side_still_covers_its_operation`, `test_both_flavours_reduce_a_parameter_the_same_way`, plus 3 existing |
| M3 | `_comparable` returns `_route` unreduced | typescript | killed, exit 1, 9 failed | the same nine as M2 |
| M4 | `declared` built from `_route`, reducing one side only | typescript | killed, exit 1, 7 failed | `test_two_specification_operations_behind_one_key_deflate_the_denominator`, `test_a_collision_is_reported_nowhere`, `test_an_sdk_interpolating_a_non_parameter_is_affirmed_by_the_cross_check`, `test_a_parameter_spelled_differently_on_each_side_still_covers_its_operation`, plus 3 existing |
| M5 | `ExtractedOperation.path` stores the reduced route, putting the reduction on the binding path | typescript | killed, exit 1, 6 failed | `test_the_reduction_is_not_on_the_path_a_call_site_resolves_through`, `test_an_sdk_interpolating_a_non_parameter_is_affirmed_by_the_cross_check`, plus 4 existing |
| M6 | `_PARAMETER` → a pattern matching nothing | speakeasy | killed, exit 1, 2 failed | `test_the_speakeasy_reduction_is_inert_rather_than_unreached`, `test_both_flavours_reduce_a_parameter_the_same_way` |
| M7 | `_PARAMETER` → `\{.*\}` | speakeasy | killed, exit 1, 4 failed | `test_the_speakeasy_reduction_changes_no_verdict`, `test_the_reduction_collides_no_vercel_operation`, `test_both_flavours_reduce_a_parameter_the_same_way`, plus 1 existing |
| M8 | the reduction writes `[]` rather than `{}`, so the two flavours disagree | speakeasy | killed, exit 1, 1 failed | `test_both_flavours_reduce_a_parameter_the_same_way` |
| M9 | `unknown = ()`, so no undeclared route is ever reported | typescript | killed, exit 1, 4 failed | `test_the_same_route_is_reported_when_the_specification_parameterises_nothing`, plus 3 existing |

Fifteen of the sixteen new tests are killed by at least one production mutation. **The sixteenth,
`test_the_overlay_the_speakeasy_reduction_is_kept_for_is_declared_by_this_vendor`, is killed by
none**, and no mutation could: it reads a committed vendor manifest, so nothing in `src/` can falsify
it. Its non-vacuity was established the other way, by running it against the wrong expected list and
watching it report the real one — the same wrong-pin-first step every measurement in this file went
through, which is what the four failures in the first run of the injectivity tests were.

M2 and M3 killing nine each, and M5 six, is the intended reading rather than noise: the reduction and
the verbatim extracted path are load-bearing for the whole cross-check, and a mutation to either that
killed only a new test would mean the new test was measuring something the module does not depend on.

## Gates

Run on the final tree.

| Gate | Exit | Result |
|---|---|---|
| `uv run pytest -q` | 0 | 2321 passed, 2 skipped. Run unpiped, so this is pytest's own status |
| `uv run python scripts/lint_encoding.py src scripts tests` | 0 | clean |
| `PYTHONIOENCODING=utf-8 uv run lint-imports` | 0 | 1 contract kept, 0 broken |
| `uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt` | 0 | clean |

## What this leaves for the next task

1. **`ExtractionReport` still has no field for a decline, and now has a second reason to want one.**
   The previous task queued it for the nineteen silent declining branches; this one adds that a
   colliding comparable key is silent in the same way and additionally deflates a denominator nobody
   can audit. The stronger form of the change is a `spec_operation_count` counted in specification
   operations rather than in comparable keys, which would make case A a number instead of an absence.
   Still `symbols.py`, still a contract change across three flavours.
2. **Case B has no repair inside these modules, and may have one outside them.** Distinguishing a
   parameter name from an arbitrary interpolated expression is vendor-SDK knowledge, so it belongs to
   an adapter and not to a reduction two generators share. The place it could live is the extractor's
   own reading of a `template_substitution` — a Stainless-specific rule in a Stainless-specific
   module — and that is a different argument from this one, with its own measurement to take.
3. **The `\{[^}]*\}` first-closing-brace behaviour is still as the previous task recorded it.** It
   leaves debris in the comparable for an interpolation containing a `}`, matches nothing, and costs
   a binding rather than misdirecting one. Unchanged, and now covered by M1 from the other side: a
   greedier reduction collides real Stripe paths, which is the reason not to widen it.
