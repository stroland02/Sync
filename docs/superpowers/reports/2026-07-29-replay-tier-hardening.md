# Hardening the replay tier

`src/sync/verify/` sits between `static_verify` and `push_branch`. Eighteen statements across
its two modules had never been executed by any test. The task was to find out what they do and
pin them; the question worth asking first was narrower.

## The question

`src/sync/remediate/graph.py` records the distinction the tier turns on:

> A replay failure is a patch that is wrong, so it re-enters the same retry loop a failed
> typecheck does. **A replay that could not run is not a failure and does not:** it reaches the
> push path carrying the fact that this run was not replay-verified.

So: is there any input for which a replay that could not run is recorded as a replay that
passed? There was, and the answer took one fixture to establish.

A module that prints the harness's marker line and ends the process runs nothing at all. On
`9e6c301` that produced `ReplayResult("passed")`, `ok=True`, and the evidence line "the patched
call path was executed against a response built from the new specification and consumed it
cleanly" — for a run in which no call path was executed. `route_after_replay` sends that to
`push_branch`.

```
tests/test_replay.py::test_a_run_that_executed_nothing_is_never_recorded_as_a_run_that_passed
E       assert 'passed' == 'declined'
```

The mechanism is that the verdict travels on the same stdout the module under test writes to,
and a marker alone does not establish who wrote a line. Two positions defeat it and they defeat
it in opposite directions:

- A module printing the marker **while it loads** lands before the harness reports. Reading the
  first marked line takes the forgery.
- A module printing one **from an exit handler** lands after the harness reports, because exit
  handlers run once the entry point has finished. Reading the last marked line — which is what
  `_payload` did — takes the forgery.

Neither end of the stream is safe to prefer. Position is not evidence of origin.

The second fixture is the sharper one, because it forges over a real failure rather than over
silence: `forges_a_verdict` is the `mishandles` patch with an exit handler that claims a pass.
The call path genuinely threw on the null the new specification permits, and the tier reported
`passed`.

## What was wrong, and what was done about it

### The verdict channel was unauthenticated

The marker is now signed with a per-run nonce. `run.mjs` takes it out of `process.env` and
deletes the variable before the module under test loads, so a line carrying it was written by
the harness and a line without it is output. That gives back both halves of the property the
module docstring already claimed: a `console.log` in the customer's code can neither forge a
verdict nor destroy one.

The deletion is the load-bearing part, and it has its own fixture. `forges_with_the_nonce`
reads the environment back and signs a forged pass with whatever it finds; the run may only end
in the throw its call path actually performs.

### A verdict that was not an object crashed instead of declining

`json.loads` on a marked line returned whatever the line held. `SYNC_REPLAY_RESULT 3` parsed to
`3`, and the next line called `.get` on it:

```
'SYNC_REPLAY_RESULT 3'          -> 3    _run would raise: AttributeError 'int' object has no attribute 'get'
'SYNC_REPLAY_RESULT "passed"'   -> 'passed'
```

`_payload` is annotated `dict[str, Any] | None` and now returns that. This is the smaller of
the three changes and the one whose condition the nonce also closes from outside; it is kept
because the annotation should be true and because `stdout` is a subprocess boundary.

### A file Node could not load was reported as a patch that threw

This is the same conflation running the other way, and it needs no hostile input at all.

`tsc` compiles a TypeScript enum. Node's strip-only mode refuses it — an enum has a runtime
representation, so there is nothing to strip — and the module never loads. The harness caught
that in the same `try` as the call and emitted `threw`.

```
E       AssertionError: TypeScript enum is not supported in strip-only mode
E       assert 'threw' == 'declined'
```

`threw` is in `_REPLAY_FAILURES`, so `route_after_replay` sends the run back to `patch` and it
spends the static-attempt budget. Every attempt meets the same enum. The run abandons a patch
that was never shown to be wrong, and `abandon_reason` blames replay for it. That is the
"retries forever on an environment problem" failure the brief names, and the module docstring
already said the opposite was true: "a file using enums or namespaces declines rather than
running."

An import the clone cannot resolve behaves identically and is the case that would retry
hardest, because replay installs nothing — the vendor package is intercepted rather than
resolved, so anything else a module imports has to be there already.

Loading is now separated from calling. A module that throws while it *evaluates* did run, so
that stays a verdict on the patch; only Node's own refusal to produce a module is a decline.

## Where the answer stands now

`passed` requires `_run` to return `executed`, which requires a signed verdict, which only the
harness can produce, and the harness emits `executed` only after `await call(...)` has resolved.
A pass now implies the named export was called and returned.

Two residuals, both fail-safe and both worth naming rather than leaving to be rediscovered:

- A module writing to stdout without a trailing newline can prefix the harness's line, so it no
  longer begins with the marker and the run declines. A verdict destroyed, never forged.
- A decline still reaches the push path. That is the designed behaviour — replay is an
  additional tier, not a precondition — and the run carries `replay_outcome` saying it was not
  verified here.

## Coverage

```
uv run pytest -q --cov=sync.verify --cov-report=term-missing

before   mock_response.py  74  8  89%   112-114, 119, 203-205, 241
         replay.py        100 10  90%   191-192, 221, 344-345, 349-350, 367-369
         TOTAL            177 18  90%

after    mock_response.py  74  1  99%   204
         replay.py        104  1  99%   193
         TOTAL            181  2  99%
```

What the eighteen were: the two spellings of a nullable declaration and a type that is only
null; a schema declaring a type this module has no rule for; an array whose element shape is
not declared; the dedup of one path seen several times; no `node` on `PATH`; a call path that
never returns; a child that produced no verdict; and a marked line that would not parse.

Sixteen are now executed. The two that remain cannot be reached, and the reason is the same in
both cases: an invariant a constructor maintains, not a type the checker enforces.

**`replay.py:193` — the body of the nullable upgrade in `replay_shapes`.** The `elif` above it
is now executed, because a body carrying an array of several elements reaches the same key
twice; it is the assignment behind the condition that never runs. Every shape there is built by
`ObservedShape.from_observation`, which sets `json_type=_json_type_of(value)` and
`nullable_seen=(value is None)`. `_json_type_of` returns `"null"` exactly when the value is
`None`, so `nullable_seen` and `json_type == "null"` are the same fact. Two shapes sharing the
key `(field_path, json_type)` therefore share `nullable_seen`, and the guard
`shape.nullable_seen and not existing.nullable_seen` is `x and not x`.

**`mock_response.py:204` — the null branch of `_value_for`.** Reaching it needs
`json_type == "null"` with `nullable` false. `_spec_type` returns `("null", True)` from the only
path that yields `"null"`, and on the observed path a dominant shape typed `"null"` is itself
one of the shapes the `any(...)` disjunction reads, so it sets `nullable`. Every `FieldDecision`
this module builds satisfies `json_type == "null" implies nullable`.

Neither is prevented by the type system. `ObservedShape(nullable_seen=False, json_type="null")`
and `FieldDecision(json_type="null", nullable=False)` both construct fine. Both branches are
dead because of an invariant held elsewhere in the code, which is exactly the kind of deadness
that comes back to life when the invariant moves.

Neither was removed. No test demonstrates a defect in either, and the brief is explicit that a
diff without one is not wanted. The right order for `replay.py:193` is to state the invariant
where it is maintained — a test in `sync.core.models` asserting
`nullable_seen == (json_type == "null")` for everything `from_observation` builds — and delete
the branch once that test exists. `mock_response.py:204` is simpler: its invariant lives three
functions away in the same file and the branch can go with it.

## Every test shown red

Most of these pin behaviour that already worked, so "watch it fail first" means breaking the
branch each one covers and watching it go red. Two mutations per branch where one mutation could
only reach one arm of a condition. No survivors, so no mutation had to be re-examined.

| Mutation | Test it killed |
|---|---|
| M1 `_payload` matches the bare marker, ignoring the nonce | `..._executed_nothing_is_never_recorded_as_a_run_that_passed`, `..._verdict_the_module_prints_cannot_forge_a_pass`, `..._marked_line_from_another_run_...`, `..._nonce_alone_decides_which_line_...` |
| M2 `run.mjs` leaves `SYNC_REPLAY_NONCE` in the environment | `..._nonce_is_out_of_reach_by_the_time_customer_code_loads` |
| M3 `_payload` returns a parsed non-object | `..._something_that_is_not_an_object_is_no_verdict` |
| M4 malformed JSON on a signed line returns a verdict | `..._marker_carrying_malformed_json_is_no_verdict` |
| M5 stdout with no signed line returns a verdict | `..._stdout_with_no_marker_at_all_is_no_verdict` |
| M6 `ERR_UNSUPPORTED_TYPESCRIPT_SYNTAX` dropped from `REFUSED_TO_LOAD` | `..._file_node_cannot_type_strip_declines_...` |
| M6b `ERR_MODULE_NOT_FOUND` dropped from `REFUSED_TO_LOAD` | `..._import_the_clone_cannot_resolve_declines` |
| M7 a missing `node` returns `passed` | `..._no_node_on_path_declines` |
| M8 `TimeoutExpired` returns `executed` | `..._call_path_that_never_returns_is_bounded_...` |
| M9 no verdict returns `executed` | `..._module_that_ends_the_process_declines_...`, `..._executed_nothing_is_never_recorded_...` |
| M10 the child's last line is dropped from the reason | `..._reason_carries_the_last_thing_the_child_said` |
| M10b the exit code is dropped when the child said nothing | `..._module_that_ends_the_process_declines_...` |
| M11 `replay_shapes` keys on `field_path` alone | `..._one_row_per_path_and_type_...` |
| M11b `replay_shapes` gives every element its own key | `..._one_row_per_path_and_type_...` |
| M12 `from_observation` retains any string, not only a published member | `..._no_value_from_the_body_reaches_a_row_the_store_would_hold` |
| M13 `_spec_type` does not read the type-list spelling | `..._type_list_spelling_of_nullable_...`, `..._union_of_two_real_types_...`, `..._declaration_that_is_only_null_...` |
| M14 an always-null field is not nullable | `..._declaration_that_is_only_null_...` |
| M15 an undeclared type yields a placeholder | `..._schema_that_names_no_type_...`, `..._type_this_module_has_no_rule_for_...`, `..._untyped_property_is_still_a_key_...` |
| M16 an undeclared element shape is invented | `..._array_with_no_declared_element_...`, `..._array_whose_items_are_a_boolean_schema_...` |

M12 is the one that reaches outside these two modules. `ObservedShape.from_observation` in
`sync.core.models` is the single place a value becomes a shape; the mutation was applied there,
watched, and reverted, and nothing in that file is committed by this task.

## Two things the tests here are trying not to be

The verification regime spec names the failure this module was asked to avoid: rules that pass
without exercising anything. Two tests are shaped around that specifically.

The privacy test asserts against a body carrying a person, a contact route, a card, an opaque
token, a free-text note and an amount, and it asserts first that the reduction actually reached
those paths — otherwise the absence of their values from the rows would mean nothing, and an
empty shape list would satisfy it. Mutating `ObservedShape.from_observation` to retain any
string rather than only a published enum member turns it red.

The dedup test asserts a count as well as a membership. A test that only checked "these keys are
present" would survive a reduction that wrote one row per array element.
