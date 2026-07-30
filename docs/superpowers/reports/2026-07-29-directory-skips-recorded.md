# A skipped directory entry is now something the caller can count

M3-W94. `sync.signals.registry_tier` refused invisibly: all of `parse_directory`'s skips were
`continue` statements, and the function returned a list of what parsed and nothing else. M3-W93
asserted the consequence directly rather than describing it —
`test_a_skipped_entry_leaves_no_trace_the_caller_could_count` compared a parse of a document holding
four malformed entries against a parse of one that never held them and found them equal. It could
not repair it, because closing it needs the function's signature and both of its callers.

This closes it, and fixes the narrower defect W93 pinned in the same expression.

## The red

W93's equality test is the red, and it is the one the brief named. It is rewritten rather than
deleted, and both forms are worth having on record because the difference is the whole task.

Before, in full:

```python
    assert shape(junk) == shape(clean)
    assert versions_after(parse_directory(junk), "2021-01-01T00:00:00.000Z") == versions_after(
        parse_directory(clean), "2021-01-01T00:00:00.000Z"
    )
```

`shape` reduced each parsed entry to its api id, its preferred version, its version keys and their
timestamps. Both assertions held, which is what made the refusal invisible: four malformed entries
cost four vendors and produced no difference a caller could observe.

After, as `test_a_skipped_entry_leaves_a_trace_the_caller_can_count`, the equality is asserted for
the half it was ever true of and denied for the half that was missing:

```python
    assert shape(junk_entries) == shape(clean_entries)
    assert versions_after(junk_entries, WATERMARK) == versions_after(clean_entries, WATERMARK)

    assert clean_faults == ()
    assert Counter(
        api
        for api in ("scalar.com", "no-versions.com", "all-bad.com", "bad-detail.com")
        for fault in junk_faults
        if api in fault
    ) == {"scalar.com": 1, "no-versions.com": 1, "all-bad.com": 2, "bad-detail.com": 2}
    assert len(junk_faults) == 6
```

The first two lines are load-bearing in the other direction: recording a skip is an addition, and a
malformed entry still costs nothing that parsed. The `Counter` is what pins attribution — two of the
four junk entries produce two records each, because each lost a version and then lost the entry.

The whole file was red at `3bd7592`: 21 of 21 tests failed, because the pair the assertions unpack
did not exist. For the equality test specifically the failure was
`TypeError: 'RegistryEntry' object is not iterable` — the fixture holds exactly two entries, so
`entries, faults = parse_directory(document)` unpacked a two-element list of entries into two
records and there was no second channel to bind. Then `f06d241` was red for the callers: four tests
failed on `assess_repository` having no such parameter and two on the artifact and the command line
reporting nothing, with the two controls passing because they assert what today's behaviour already
did.

## The key and the shape, and why they are not new

`parse_directory` now returns `tuple[list[RegistryEntry], tuple[str, ...]]`. The second element is
`unreadable`: a tuple of strings, each naming its source and its cause, present and empty on a clean
document.

That is `IntakeReport.unreadable`'s key and shape, which M3-W90 already carried into
`ReachabilityRanking` under the same name for the reason it records there — *a reader parsing both
artifacts needs one rule, not two.* Three specifics were copied rather than reinvented:

- **A tuple of prose strings, not a structured record.** `IntakeReport.unreadable` holds
  `"package.json: dependencies does not hold an object"` and
  `"pyproject.toml could not be read: …"`. Three sources already share that list and tell themselves
  apart by the prefix on each string. A directory fault does the same with `registry directory:`.
- **Present and empty, never absent.** `ReachabilityRanking.unreadable` argues this at length: an
  absent key does not distinguish a clean read from an artifact produced by something that never
  recorded a fault. A clean document parses to `(entries, ())`.
- **Second position in the pair.** `read_declared_dependencies` is the closest sibling — a pure
  reader that returns what it read and what it could not, as
  `tuple[tuple[Dependency, ...], tuple[str, ...]]` — and intake merges its second half into the
  report. `parse_directory` is the same shape of function and now has the same shape of return. No
  new container type was introduced, because the codebase already had the answer.

**One deviation, argued.** The strings are prose rather than a machine-readable cause code, so a
reader filtering by cause matches on text. That is the existing rule and it was kept deliberately;
inventing an enum here would have made the directory the one input whose faults a reader parses
differently from every other input in the same list.

## What the four causes look like, and the fifth that W93's table omitted

Each record names the api id, and the version too where the skip was scoped to one, because the
causes are different repairs and a reader who cannot tell them apart cannot make any of them.

| Cause | Scope | Record |
|---|---|---|
| body is not an object | entry | `registry directory: '<api>' is not an object` |
| `versions` is absent, not an object, or empty | entry | `registry directory: '<api>' declares no versions object` |
| a version's detail is not an object | version | `registry directory: '<api>' version '<v>' is not an object` |
| no `swaggerUrl` string | version | `… declares no swaggerUrl string, so there is nothing to download` |
| no usable timestamp | version | `… declares no usable updated or added timestamp, so nothing can compare it against a watermark` |
| the entry kept no version | entry | `registry directory: '<api>' is not discoverable -- none of the N version(s) it declares could be read, each recorded above` |

Two departures from W93's four-row enumeration.

**The `versions` guard is recorded, and W93's table did not list it.** It was already covered by
`test_an_entry_missing_its_versions_map_is_skipped_rather_than_raising`, so it was not among the four
unexecuted statements the task went looking for. It is still a skip that loses a vendor, and a
channel that recorded four of five would leave one entry vanishing silently — which is the defect,
not a smaller version of it.

**A missing `swaggerUrl` and an unusable timestamp are two records, where W93 read one condition.**
`not isinstance(spec_url, str) or not isinstance(updated, str)` was one statement, so W93 counted it
once. They are two repairs: nothing to download and nothing to compare against a watermark are
different absences in the vendor's entry, and one message covering both sends a reader back to the
document to find out which. The guard is split into two, each with its own message.

## The consequential fifth record, and why it is not a fifth cause

An entry that lost every version is downstream of the three version-scoped skips. Recording it as an
independent malformation would count the same fault twice: a reader summing the list would find five
things wrong with a document holding three.

It is recorded anyway, because it is the only record that says the **vendor** is gone rather than one
of its versions. An entry with three versions and one bad one also produces a version record, and
survives; nothing else in the list distinguishes that from an entry that disappeared. Suppressing it
would leave the most consequential fact in the channel — a vendor Sync will never offer to watch —
inferable only by subtraction, which is the shape of failure this task exists to remove.

What keeps it from being read as a cause is its wording and its position. It states that the entry is
*not discoverable*, names how many versions it declared, and says the causes are recorded above it —
so it reads as the consequence of the records that precede it rather than as a malformation of its
own. Document order is preserved by both loops, so the causes always precede their consequence and
the same document always produces the same list, which is what keeps the stage idempotent.

## What each caller now surfaces, and where

`parse_directory` has one production call site, in `sync/cli.py`. `sync/signals/intake.py` is the
other caller in the sense that matters: it receives the entries and owns the artifact. Both carry it.

**`assess_repository` merges it into `IntakeReport.unreadable`.** A new `registry_unreadable`
parameter arrives beside `registry_entries` — the two halves of one return — and is concatenated onto
the manifest faults. So it reaches `report.to_json()`, which is the artifact, and no new key appears
beside it. It defaults empty rather than being required, unlike `ReachabilityRanking.unreadable`: a
deployment that passed no directory has no directory faults, so empty there is the truth rather than
a silent claim, and the parameter it pairs with is defaulted for the same reason.

**`ReachabilityRanking` needed no change at all**, and that is the argument for the key rather than an
accident of it. M3-W90 carried `IntakeReport.unreadable` into the ranking under the same name, so a
directory fault reaches the ranked artifact with nothing added to `reachability.py` — a file this
task does not own. It is asserted anyway, so a later change to either side cannot quietly drop it.

**`sync intake` prints it to stderr**, in the loop that already printed manifest faults. Both
surfaces, because they answer to different readers: stdout is what a caller redirects to a file,
commits and diffs between runs, and stderr is the operator watching the run. M3-W90's distinction
holds — *stderr is not the artifact* — so the artifact was the requirement and stderr is the
addition.

That loop's prefix changed from `unreadable manifest:` to `unreadable:`. The list holds faults from
four inputs now and every string already names its own source, so a prefix naming one of them was
wrong for the rest. `test_cli_wiring_reachability.py`'s assertion moved with it, from
`"unreadable manifest:" in captured.err` to `"unreadable: package.json" in captured.err`, which is a
stronger statement than the one it replaced — it pins the prefix *and* the source.

**One key, not two, and that is asserted rather than described.** Two tests compare the artifact's
key set against an exact set, so a second key beside `unreadable` fails them. The argument for
merging is the one `IntakeReport.unreadable` already makes: a repository whose manifest is unreadable
is not a repository with no dependencies, and a package whose catalogue entry would not parse is not
a package no tier can serve. Both narrow the same report, and both are read by somebody asking what
this answer does not cover.

## The unusable-versus-falsy fix

W93 pinned this by test because the code did not read the way it behaved:

> `detail.get("updated") or detail.get("added")` falls back when `updated` is *falsy*, not when it
> is *unusable*. A numeric `updated` is truthy, wins the `or`, then fails the string check — so the
> version is skipped while a perfectly readable `added` sits beside it unused.

Replaced by `_timestamp`, which asks each field in turn whether it is usable:

```python
    for key in ("updated", "added"):
        value = detail.get(key)
        if isinstance(value, str) and value:
            return value
    return None
```

**Usable means a non-empty string, and the emptiness half is not incidental.** `versions_after`
compares timestamps as strings, and `""` compares less than every real one, so a version admitted
with an empty timestamp would be reported as one that never moves. The old expression got that right
by accident in one direction — an empty `updated` is falsy, so it fell back — and wrong in the other:
with `updated` absent and `added` empty, `None or ""` is `""`, `isinstance("", str)` is true, and the
version was admitted carrying a timestamp nothing can compare. Defining usable as `isinstance(value,
str)` alone would have kept that hole and added the first direction to it. So both routes now answer
the same way, and the second is pinned by
`test_a_timestamp_that_is_an_empty_string_is_unusable_rather_than_a_value_to_compare`.

W93's pinning test could not be kept: it asserted the defect. It was rewritten in place as
`test_a_numeric_timestamp_falls_back_to_a_readable_added_rather_than_skipping_the_version`, over the
same fixture — a numeric `updated` beside a string `added` — asserting the opposite outcome: the
version is kept, its `updated` is the string from `added`, and nothing was recorded as unreadable. Its
docstring carries what it used to say, so the change is legible from the test rather than only from
here.

## Mutation table

Harness at `%TEMP%\w94_mutate.py`, not committed. It runs
`pytest -q --color=no -p no:randomly -n0` over `test_registry_directory.py`,
`test_registry_directory_reporting.py` and `test_cli_wiring_reachability.py`, `compile()`s each
mutated source before pytest sees it, and classifies four outcomes. Baseline asserted green at 49
passed before the first mutation and again after the last, at the same count, so a blind harness is
distinguishable from a clean one.

| File | Mutation | Outcome | Killed by |
|---|---|---|---|
| `directory.py` | body guard records nothing | KILLED, 4 failed | `…body_is_not_an_object_is_recorded_against_its_api_id`, `…leaves_a_trace…`, `…assess_repository_carries…`, `…command_line_puts_a_directory_fault…` |
| `directory.py` | no-versions guard records nothing | KILLED, 2 failed | `…declaring_no_versions_object_is_recorded…`, `…leaves_a_trace…` |
| `directory.py` | version-detail guard records nothing | KILLED, 3 failed | `…detail_is_not_an_object_is_recorded_against_that_version`, `…kept_no_version_is_recorded_as_a_consequence…`, `…leaves_a_trace…` |
| `directory.py` | `swaggerUrl` guard records nothing | KILLED, 4 failed | `…recorded_as_different_faults`, `…kept_no_version…`, `…leaves_a_trace…`, `…assess_repository_carries…` |
| `directory.py` | timestamp guard records nothing | KILLED, 2 failed | `…recorded_as_different_faults`, `…empty_string_is_unusable…` |
| `directory.py` | consequence is not recorded | KILLED, 3 failed | `…kept_no_version_is_recorded_as_a_consequence…`, `…leaves_a_trace…`, `…assess_repository_carries…` |
| `directory.py` | consequence recorded for every entry, not only a lost one | KILLED, 12 failed | every cause test, both clean-read controls, and `…reports_nothing_for_a_directory_that_reads` |
| `directory.py` | an entry that kept no version is admitted anyway | KILLED, 3 failed | `…every_version_was_skipped_is_skipped_in_turn`, `…kept_no_version…`, `…leaves_a_trace…` |
| `directory.py` | the channel is always empty (`return entries, ()`) | KILLED, 11 failed | all six cause tests and all five carry tests |
| `directory.py` | the two version-scoped absences share one message | KILLED, 1 failed | `…recorded_as_different_faults` |
| `directory.py` | the fallback reads falsy again (W93's pinned defect restored) | KILLED, 2 failed | `…numeric_timestamp_falls_back…`, `…empty_string_is_unusable…` |
| `directory.py` | an empty string counts as a usable timestamp | KILLED, 1 failed | `…empty_string_is_unusable…` |
| `intake.py` | `assess_repository` drops the carry | KILLED, 4 failed | `…assess_repository_carries…`, `…same_key_as_a_manifest_fault`, `…ranked_artifact_carries…`, `…command_line_puts…` |
| `cli.py` | the command line never passes it on | KILLED, 1 failed | `…command_line_puts_a_directory_fault_in_the_artifact_and_on_stderr` |
| `cli.py` | the stderr prefix calls every fault a manifest again | KILLED, 2 failed | `…command_line_puts…`, `test_intake_ranked_puts_an_unreadable_manifest_in_the_artifact_and_not_only_on_stderr` |
| `directory.py` | *control:* an unclosed paren | DID-NOT-COMPILE | — |

15 of 15 real mutations killed. No survivals.

Two are worth reading rather than counting. *The channel is always empty* is the mutation that would
have survived a channel nobody read — it kills eleven tests, five of them at the two call sites, which
is the property the brief asked for: a fault must not be inferable only by subtraction. And
*consequence recorded for every entry* kills both clean-read controls, which is what makes the
present-and-empty state a claim rather than a default; without those controls a carry that reported
something unconditionally would have passed every other test in the file.

### All three false-survival modes are detected, and two were exercised

The brief named three modes that have produced false survivals on this project. Each is answered, and
the answer was checked rather than assumed.

- **Colourised summaries.** `--color=no`, and the verdict is read from the summary *counts* rather
  than from `FAILED ` line prefixes, so a colour code cannot hide a kill.
- **A non-1 exit with no `FAILED` lines.** Any exit code that is not 0 or 1 is UNREADABLE. Verified
  by reproducing W93's own harness bug deliberately — the three test paths passed as a single `argv`
  item — which gave **exit 4 with no counts at all** and was classified
  `UNREADABLE (exit 4, counts {})`. A two-outcome harness would have called that a clean run.
- **A `SyntaxError` arriving as `ERROR` rather than `FAILED`.** Every mutated source is `compile()`d
  before pytest is invoked. Verified by a deliberate control mutation, the last row above, which was
  reported DID-NOT-COMPILE up front and never reached pytest.

A fourth guard was added and also checked: a run that exits 0 with a passing count different from the
asserted baseline is UNREADABLE, not a survival, because the test set moved. `classify(0, {"passed":
41}, 49)` returns `UNREADABLE (exit 0 but 41 passed, baseline 49)`.

No mutation hit UNREADABLE or DID-NOT-COMPILE by accident. Both were reached only by the deliberate
controls, which is why the controls exist.

## Two line-number registries moved, and one caught it by name

`tests/test_decode_handlers.py` keys each decode-handler driver by `path:line`. The docstrings added
to `intake.py` pushed all three of its handlers down seven lines, and the file failed with three
parametrised cases plus `test_no_driver_names_a_handler_that_is_gone`. That is the file working: a
driver outliving its handler would keep proving something that no longer exists. The keys are
repointed to 282, 318 and 329.

The four `directory.py:NN` references in the directory tests moved too, and the one W93 wrote as
`directory.py:90` became two because the version guard was split. They are updated rather than
dropped — a docstring pointing at the wrong line teaches a reader nothing — but the drift is a
standing cost of citing line numbers in prose, and this is the second task to pay it.

## The sibling mechanism this deliberately did not unify

`sync.signals.mcp_server` answers the same question differently: eight of its nine refusals reach a
caller as a countable row or an exception, none of them through an `unreadable` list. W93 established
that, and this task was scoped to the sibling that refused invisibly rather than to reconciling the
two.

They are not obviously the same mechanism. A `VendorChange` row is a claim about what a vendor did,
and `mcp-tool-schema-not-comparable` is the adapter saying it cannot compare a tool — a row in the
graph, which a detector queries. An `unreadable` string is a fact about an input that would not parse,
which narrows an artifact's coverage and is read by a person. Merging them would put one of those in
the other's channel. **Recorded as a next task rather than decided here:** whether a refusal that
already produces a graph row should *also* appear in an `unreadable` list, so that one query answers
"what did this run not cover" across every signal source.
