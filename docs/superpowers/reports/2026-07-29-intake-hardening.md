# Hardening the intake reader

**Date:** 2026-07-29
**Task:** M3-W87
**Module:** `src/sync/signals/intake.py`
**Branch:** `stroland02/m1-static-gate`

## The short answer

Seventeen statements had never run. All seventeen now run, and each is pinned by a test that has
been shown red against a mutation of the code it covers.

One defect was found, and it was found by testing the boundary rather than by reading the code: a
`package.json` whose `dependencies` value is not an object raised `TypeError` out of
`assess_repository`, so a customer with a manifest of that shape got a traceback instead of a
report. The test came first and failed first. The fix is nine lines in `_read_npm`.

One branch is unreachable and was left alone rather than reached through a private path. One
question the task asked — can a fault be counted and dropped — has a qualified answer: not on this
module's own surface, but yes on the ranked path through the CLI, which is out of scope here and
is recorded below as the next task.

## 1. The measurement

Both figures come from the same command, run on the full suite:

```
uv run pytest -q --cov=sync --cov-report=term-missing
```

**Before**, at `1924016` (`origin/main`):

```
src\sync\signals\intake.py    155    17    89%   200, 224, 227-228, 279-280, 300-307, 313-315
```

**After**:

```
src\sync\signals\intake.py    163      0   100%
```

The statement count rises from 155 to 163 because the defect fix adds statements. Nothing was
deleted to reach the number. Suite-wide coverage moves from 96% to 97%, and the suite from 2100
passing to 2113.

Coverage is a map of what has never run, and it has a blind spot that matters here. `_read_npm`
catches `json.JSONDecodeError` and `UnicodeDecodeError` on one line, so the existing
`broken_manifest` fixture marked that line covered while the `UnicodeDecodeError` arm had never
once been entered. The same is true of the `tomllib.TOMLDecodeError`/`UnicodeDecodeError` pair in
`_read_pypi`. Two of the three decode handlers this task exists to exercise were invisible to the
metric that selected the module. They are covered now because a mutation removing
`UnicodeDecodeError` from each tuple kills a test (M6, M8), not because a line number changed
colour.

## 2. What each newly covered branch does

| Line (before) | Branch | What it does |
|---|---|---|
| 200 | `read_sdk_repositories`, container guard | Evidence that is not a list raises `ValueError` naming the path *and* the shape. |
| 224 | `read_registry_apis`, container guard | The same, for the directory tier. |
| 227-228 | `read_registry_apis`, entry guard | An entry missing `package` or `api` raises rather than being skipped. A skipped entry drops a package out of the middle category and reports no fault. |
| 279-280 | `_read_npm`, non-object guard | A `package.json` that is valid JSON and not an object is recorded as a fault. It parses cleanly and declares nothing, and "declares nothing" is the answer a project with no dependencies gives. |
| 300-304 | `_read_pypi`, pyproject read and decode arm | An unreadable `pyproject.toml` is recorded and `data` falls back to `{}`, so `requirements.txt` beside it is still read. |
| 305-307 | `_read_pypi`, `[project] dependencies` | The declared requirements are collected, filtered to strings — TOML arrays are heterogeneous, so this filter guards a condition that really occurs. |
| 313-315 | `_read_pypi`, requirements decode arm | `requirements.txt` has no parser to fail, so a decode error is the only failure it has. Recorded, and the line list falls back to empty. |

Nothing in the seventeen was a condition that cannot occur. Every one of them is a shape a
customer's repository can actually hold.

## 3. The defect

**Found:** a `package.json` whose `dependencies` or `devDependencies` value is not an object.

`_read_npm` validated the top level and then splatted the two tables under it:

```python
declared: dict[str, Any] = {
    **(data.get("dependencies") or {}),
    **(data.get("devDependencies") or {}),
}
```

Three shapes of one malformation produced three different outcomes:

| manifest | before |
|---|---|
| `["stripe", "twilio"]` (top level) | fault recorded, correct |
| `{"dependencies": []}` | **silently zero dependencies** |
| `{"dependencies": ["stripe"]}` | **`TypeError: 'list' object is not a mapping`, uncaught** |

The middle row is the silent narrowing `IntakeReport.unreadable` exists to prevent, in the exact
words of its own docstring: *"a repository whose manifest is unreadable is not a repository with
no dependencies -- and reported as the latter it reads as a clean scan of an empty project."* The
bottom row is worse, because the exception propagates out of `read_declared_dependencies`, out of
`assess_repository`, and out of `sync intake`. A customer gets a traceback where the module's
whole design promises a report with a fault in it.

The falsy case is what makes this more than theory. `"dependencies": []` already flows through
this code today and produces a wrong answer quietly; the shape is not hypothetical, it is just
one character away from the one that crashes.

**Fixed**, in the module's existing idiom — the new arm is the same shape as the top-level guard
immediately above it, reporting the fault and reading nothing further from the file:

```python
declared: dict[str, Any] = {}
for table in ("dependencies", "devDependencies"):
    section = data.get(table)
    if section is None:
        continue
    if not isinstance(section, dict):
        unreadable.append(f"package.json: {table} does not hold an object")
        return []
    declared.update(section)
```

`None` still means "not declared", which covers both an absent key and an explicit JSON `null`.
Every other non-object value is a fault, so `[]` and `["stripe"]` now answer the same way — the
inconsistency between them is what left the crash latent.

This is the only production change. `CLAUDE.md` puts a customer's manifest squarely in the class
of thing that gets validated rather than trusted, and this is that rule applied one level deeper
than it already was.

## 4. The branch that is unreachable

`_read_npm` ends with:

```python
return [
    Dependency(name=name, version=str(version), ecosystem=NPM)
    for name, version in declared.items()
    if isinstance(name, str)
]
```

**`isinstance(name, str)` can never be false.** `declared` is now built only from values that
passed an `isinstance(section, dict)` check, and those dicts come from `json.loads` with no
`object_pairs_hook` and no `object_hook`. JSON object keys are strings by the grammar, and
`json.loads` produces `str` keys for every one of them — including `{"1": 2}`, which yields the
key `"1"` and not `1`. There is no input to this function that makes the filter drop anything.

It was not tested. Reaching it would mean calling `_read_npm` with a hand-built dict or
monkeypatching `json.loads`, and a test that constructs an impossible state through a private path
is coverage theatre: it reports assurance about a customer manifest that no customer manifest can
produce.

Statement coverage never flagged it, and could not — the comprehension is one statement and it
runs on every readable manifest. The line was green throughout.

**It should be deleted.** `CLAUDE.md` is explicit that validation for conditions that cannot occur
does not belong, and the cost of leaving it is that a reader takes it as evidence that non-string
keys are a thing that happens here. It is left in place only because this task permits a
production change where a test proves a defect, and a dead filter produces no wrong answer, so no
test can prove one. It is a two-line deletion for whoever next has the module open.

The sibling filter in `_read_pypi` is **not** the same case and must not be deleted with it. TOML
arrays are heterogeneous, so `dependencies = ["stripe", 12, true]` is valid TOML, and without that
filter a `Dependency` would be constructed with `name=12`. It is now tested (M15).

## 5. Can a fault be counted and dropped?

**On this module's own surface, no**, and it is now asserted rather than assumed.
`test_every_manifest_fault_reaches_the_artifact_rather_than_being_counted_and_dropped` breaks all
three manifests in one repository and checks the serialised artifact, not the accumulator: three
faults appear in `to_json()["unreadable"]` beside a `counts()` of three zeroes. The zeroes are
only honest because the faults travel with them, so the test asserts them together. Deleting the
`"unreadable"` key from `to_json` kills it (M13).

**On the ranked path, yes, and it is out of scope here.** `sync intake --rank-by-repo-id` prints
`ranking.to_json()` instead of `report.to_json()`. `rank_reachability` takes the whole
`IntakeReport` and builds its rows from `report.assessments` alone; `ReachabilityRanking.to_json`
emits `counts` and `rows` and has no `unreadable` key. So the machine-readable artifact for a
ranked run carries no record that a manifest would not parse, and a repository with an unreadable
`package.json` is indistinguishable in that JSON from one that declares nothing.

The faults are not lost entirely — `cli.py` runs its `for problem in report.unreadable` loop after
the if/else, so both paths still print them to stderr. But stderr is not the artifact, and the
whole argument for `unreadable` is that the fault has to travel with the answer.

`src/sync/cli.py` is forbidden to this task and `src/sync/signals/reachability.py` is not among
its owned files, so neither was touched. **Next task:** carry `unreadable` into
`ReachabilityRanking` so the ranked artifact answers what the unranked one already answers.

## 6. The non-UTF-8 fixtures

`scripts/lint_encoding.py` scans `*.py` only — `_python_files` is `target.rglob("*.py")` — so a
committed non-UTF-8 `package.json` under `tests/fixtures/` would not have tripped it. The choice
was therefore not forced by the lint, and the lint was not weakened.

**The bytes are constructed in the test and written with `write_bytes`.** Two reasons:

1. A file in the tree whose bytes are deliberately illegal is repaired silently by anything that
   round-trips it as text — an editor, a formatter, an agent asked to tidy the fixtures. The test
   would then run against a valid UTF-8 file and pass, while appearing to cover the decode
   handler. That is precisely the manufactured confidence `CLAUDE.md` warns about, and it would be
   invisible because the test still passes.
2. `tests/test_corpus_binary_files.py` already does exactly this, for exactly this reason. Its
   `PNG_BYTES` and its cp1252 string are constructed in the module rather than committed.

The bytes chosen are cp1252 for an accented identifier:

```python
NOT_UTF8_PACKAGE_JSON = b'{"dependencies": {"caf\xe9-sdk": "^1.0.0"}}'
NOT_UTF8_PYPROJECT = b'[project]\ndependencies = ["caf\xe9-sdk>=1.0.0"]\n'
NOT_UTF8_REQUIREMENTS = b"caf\xe9-sdk==1.0.0\n"
```

Each is **valid in its own manifest syntax once decoded as cp1252** and raises
`UnicodeDecodeError` as UTF-8 (`0xE9` is a three-byte lead byte followed by `-`, which is not a
continuation byte). So the decode is the only thing that can fail — a test that passed because the
JSON was also malformed would prove nothing about the decode arm. This is the failure `CLAUDE.md`
says no fixture in this repository can catch, and it is one accented package name away from a real
customer repository.

The readable malformed fixtures — a truncated manifest, a top-level array, a mapping where a list
belongs — are committed under `tests/fixtures/intake/`, because a reader can inspect them and
nothing can silently repair them into something else. `tests/fixtures/intake/README.md` records
which is wrong in which way, so the next person does not fix them.

## 7. The mutation table

"Fails first" for a test pinning existing behaviour means the test has been shown red against a
break in the code it covers. Every mutation below was applied to `src/sync/signals/intake.py` on
its own, the intake suite was run, and the file was restored. A baseline run after the last
restore was clean.

| # | Mutation | Test(s) killed |
|---|---|---|
| M1 | `read_sdk_repositories`: message stops naming the path | `test_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape` |
| M2 | `read_registry_apis`: message stops naming the path | `test_registry_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape` |
| M3 | `read_registry_apis`: not-a-list guard removed | `test_registry_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape` |
| M4 | `read_registry_apis`: a partial entry is skipped instead of raising | `test_a_registry_evidence_entry_missing_a_field_raises_rather_than_being_skipped` |
| M5 | `_read_npm`: not-an-object guard removed | `test_a_package_json_that_is_valid_json_and_not_an_object_is_reported` |
| M6 | `_read_npm`: `UnicodeDecodeError` dropped from the except tuple | `test_package_json_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash`, `test_every_manifest_fault_reaches_the_artifact...` |
| M7 | `_read_npm`: a non-object dependency table is skipped instead of reported (the defect) | `test_a_dependency_table_that_is_not_an_object_is_a_fault_rather_than_a_crash` |
| M8 | `_read_pypi`: `UnicodeDecodeError` dropped from the pyproject except tuple | `test_pyproject_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash`, `test_every_manifest_fault_reaches_the_artifact...` |
| M9 | `_read_pypi`: an unparseable pyproject abandons `requirements.txt` too | `test_an_unparseable_pyproject_is_reported_and_the_other_manifest_is_still_read`, `test_every_manifest_fault_reaches_the_artifact...` |
| M10 | `_read_pypi`: the pyproject `[project] dependencies` read removed | `test_both_python_manifests_are_read_when_a_project_carries_both`, `test_a_non_string_in_the_dependency_array_is_dropped...` |
| M11 | `_read_pypi`: `requirements.txt` never read | six tests, including two that predate this task |
| M12 | `_read_pypi`: `requirements.txt` decode failure left uncaught | `test_requirements_bytes_that_are_not_utf8_are_a_fault_rather_than_a_crash`, `test_every_manifest_fault_reaches_the_artifact...` |
| M13 | `IntakeReport.to_json` drops the `unreadable` key | `test_every_manifest_fault_reaches_the_artifact_rather_than_being_counted_and_dropped` |
| M14 | `read_sdk_repositories`: not-a-list guard removed | `test_evidence_that_is_not_a_list_raises_naming_the_file_and_the_shape` |
| M15 | `_read_pypi`: the non-string filter on the dependency array removed | `test_a_non_string_in_the_dependency_array_is_dropped_and_the_rest_still_read` |

Fifteen mutations, fifteen killed.

### The two things the mutation run caught that the tests did not

**The harness was wrong before the tests were.** The first run reported all thirteen mutations
surviving, which is not a believable result. The cause was in the harness, not the module: it
matched summary lines with `line.startswith("FAILED ")`, and pytest colourises them, so every line
actually begins with an ANSI escape and nothing ever matched. `--color=no` fixed it. This is the
third time on this project that a surviving mutation was the mutation's fault rather than the
test's, and the check that caught it is cheap — a baseline run with the file restored, asserted
clean, so a harness that reports nothing failing is distinguishable from a harness that cannot
see failures.

**M3 survived legitimately, and the test was too weak.** Removing the container guard from
`read_registry_apis` left the test green, because iterating a mapping yields its string keys,
`"acme-sdk"["package"]` raises `TypeError`, and the entry-level handler turns that into a
`ValueError` naming the same path. The original assertion — raises `ValueError`, message contains
the filename — was true with the guard and without it.

The guard's real contribution is telling two faults apart: the container is wrong, or an entry in
it is wrong, and those are different repairs. Both not-a-list tests now assert
`"does not hold a list"` as well as the path, and M3 and M14 kill them. The under-specified
version would have let either guard be deleted with the suite still green.

## 8. Scope

Production code changed: `_read_npm` only, for the defect in §3. Nothing was refactored to have a
diff.

Left alone and reported instead: the unreachable filter in §4, the ranked-artifact gap in §5, and
one smaller observation — a non-string entry inside a `[project] dependencies` array is dropped
without being recorded, which is a narrower contract than `unreadable` sets elsewhere in the
module. It is pinned by a test as the behaviour it is rather than endorsed. It is consistent with
the identical filter in the npm reader, so it is a design question about what "unreadable" covers
rather than a defect, and answering it belongs with whoever owns that decision.
