# The kit refuses what the store would

**Date:** 2026-07-30
**Scope:** B67 — `check_detector` certified a detector every one of whose findings
`GraphStore.insert_finding` was going to reject. Four rules, none about the rung.
**Outcome:** a fifth rule, `_check_findings_name_a_rung`, rejecting `unattributed` and nothing else
about which rung it is. Both halves proved, the five shipped detectors still conform, four gates
green.

## What the rule is, and what it deliberately is not

**It checks that a rung was named. It never checks which one.** The rung names the binding whose
wrongness would make the finding wrong, which is the detector author's judgement: a claim read off
the static index is `static`, one resting on a span-to-operation correlation carries the
correlator's own rung through, including `unresolved` when nothing correlated. The kit cannot know
which applies to somebody else's detector, so it does not guess.

It runs after `_check_findings_are_usable`, which is what establishes that each result is a
`Finding` at all, and before the two cross-finding rules. That grouping is deliberate — shape rules
about one finding first, rules about a set afterwards — and it had a consequence worth naming: two
existing fixtures, `TwoClaimsOneKey` and `Drifts`, built their findings without a rung and were
being rejected by the new rule before reaching the rule they exist to exercise. Both now name one,
with a comment saying why: a fixture broken in two ways tests neither.

**B66's refusal at the store stays exactly as it was.** This is an earlier net, not a replacement.
A detector can be written, or changed, after the kit last ran.

## Should the kit also check the rung is a member of `BindingRung`?

No, because it cannot fail there: `Finding.binding_rung` is typed `FindingRung`, so Pydantic
rejects a value outside the vocabulary at construction — measured, `binding_rung="banana"` raises
`ValidationError` before any scan can yield it — which leaves `unattributed` as the only member
that is not a rung a binder emits, and therefore the only one this rule has to name.

## Verification

**Watched red first**, for the reason expected:

```
FAILED test_a_detector_whose_findings_name_no_rung_fails    DID NOT RAISE ConformanceFailure
```

**The accepting half is real, and it caught something.** `_CorrectDetector` — the kit's own example
of a conforming detector — did not set a rung, so `test_a_correct_detector_passes` went red the
moment the rule landed. The kit's published example was emitting findings the store would have
refused. It now names `static`, with the reason stated in its docstring rather than asserted:
that example reads a vendor change against the static index and nothing else is load-bearing.

**Then the rule was mutated three ways to see which test notices:**

```
== the rule is never called
   RED:   test_a_detector_whose_findings_name_no_rung_fails
   RED:   test_one_finding_out_of_two_naming_no_rung_fails
   GREEN: test_a_correct_detector_passes

== the rule reads only the first finding
   GREEN: test_a_detector_whose_findings_name_no_rung_fails
   RED:   test_one_finding_out_of_two_naming_no_rung_fails
   GREEN: test_a_correct_detector_passes

== the rule refuses every rung, not only the unattributed one
   RED:   test_a_detector_whose_findings_name_no_rung_fails
   GREEN: test_one_finding_out_of_two_naming_no_rung_fails
   RED:   test_a_correct_detector_passes
```

The middle one is why the second test exists: a detector that attributes most findings and forgets
on one branch is likelier than one that never attributes at all, because the forgetful branch is
usually the one with the fewest fixtures behind it. Only that test sees a rule reading
`findings[:1]`. The third mutation is the guard on "never asserts a particular rung" — invert the
predicate and the accepting half is what goes red.

**The five shipped detectors still conform**, run rather than reasoned about:
`tests/test_shipped_conformance.py -k detector` → `6 passed, 20 deselected`. They attribute since
B65, and this is the control that says the rule is not vacuous against the real ones.

The four gates:

```
uv run pytest                                             2552 passed, 1 skipped in 120.93s
uv run lint-imports                                       sync.core depends on nothing KEPT
                                                          Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests  exit 0
uv run python scripts/lint_dead_links.py src --baseline …  exit 0
```

Two tests added, so the collected total moves from the brief's 2551 to 2553. `lint-imports` is the
gate that mattered: `UNATTRIBUTED` comes from `sync.core.models`, so `sync.core` still imports
nothing from a sibling.

No corpus figures, because this brief did not ask for them and nothing here is on the scorer's
path: the change is confined to `sync.core.conformance`, its tests, and the adapter document.

## One correction to the adapter document, beyond what was asked

`docs/writing-a-vendor-adapter.md` is where a third-party detector author reads what the kit
checks, so the rung rule is stated there in the same prose style as the others. While in that
section: the collision paragraph still described the finding key as the triple
`(detector, call_site_id, vendor_change_id)`. `claim` joined that key before this brief, and the
conformance module's own docstring records the change — the document did not. It now names the
quadruple, and says it was corrected here.

## What is left

**A detector can still be written after the kit runs.** That is the gap the kit cannot close by
construction and the reason B66's store refusal stays: the kit is a check an author chooses to run,
and the store is the one nothing routes around.
