# The decode-handler drivers stop being keyed by position

**Date:** 2026-07-30
**Scope:** B63 — key `DRIVERS` in `tests/test_decode_handlers.py` by scope rather than by line
number, and correct the docstring paragraph that said no stable key existed.
**Outcome:** keys are `path::scope::caught`, eighteen handlers still resolve to eighteen distinct
keys, and the two failures the file exists to produce were each reproduced against a real
mutation of `src/` rather than asserted.

## The claim that had to be checked first

The file's docstring said there was "no stable identity to key on instead -- a handler has no
name, and two in one file can catch the same exceptions". The second half is true and the
conclusion does not follow: a handler has no name, but the scope it sits in does, and the
exceptions it catches distinguish the two arms that share a scope.

Measured over `src/` before anything was changed:

```
handlers: 18
distinct keys: 18
collisions: 0
```

Two pairs share a file and a scope and are separated only by what they catch, which is why
`caught` is part of the key rather than decoration:

```
sync/index/python_lang.py::PythonAdapter._read_manifests::TOMLDecodeError+UnicodeDecodeError
sync/index/python_lang.py::PythonAdapter._read_manifests::UnicodeDecodeError
sync/signals/intake.py::_read_pypi::TOMLDecodeError+UnicodeDecodeError
sync/signals/intake.py::_read_pypi::UnicodeDecodeError
```

The names are sorted inside the key. The order a clause lists its exceptions in changes nothing
about what the chain catches, so a key that moved when somebody reordered them would be
positional again in a second spelling.

## Watched red first

`test_a_key_survives_an_unrelated_edit_above_its_handler` writes a one-handler module, reads the
inventory, writes the same module with three comment lines above it, and reads it again. Against
the positional key:

```
AssertionError: assert ['reader.py:5'] == ['reader.py:8']
```

That is the whole defect in two lines of output: an edit that touched no behaviour renamed the
handler. `test_two_handlers_the_key_cannot_tell_apart_are_refused_naming_both` and
`test_no_two_decode_handlers_share_a_key` failed with `NameError: colliding_keys is not defined`,
which is the honest red for a check that did not exist.

## What the new key gives up, and where that is caught

Uniqueness. Two chains in one scope catching the same exceptions collide, and one driver's entry
would then vouch for the other's handler — the precise failure `test_handler_spans_do_not_overlap`
already guards on the observation side. `colliding_keys` refuses it on the inventory side, and the
refusal names both positions rather than only the key, because a reader who is told two handlers
collide still has to find the second one.

## Every check proved against a real mutation

None of these three is asserted from the shape of the code. Each was produced by breaking `src/`,
watching the named failure, and restoring.

| mutation | check that fired | what it printed |
|---|---|---|
| a new decode handler appended to `sync/telemetry/ingest.py` | `test_every_decode_handler_has_been_entered` | `sync/telemetry/ingest.py::_mutation_probe::UnicodeDecodeError` |
| `ValueError` added to `parse_feed`'s caught tuple | `test_no_driver_names_a_handler_that_is_gone` | `sync/signals/feed/consumer.py::parse_feed::JSONDecodeError+UnicodeDecodeError` |
| the same handler written twice in one function | `test_no_two_decode_handlers_share_a_key` | the key `at sync/telemetry/ingest.py:129, sync/telemetry/ingest.py:133` |

The second is worth reading twice. `json.JSONDecodeError` is a subclass of `ValueError`, so that
mutation changes nothing about what the chain catches at runtime — and the key changes anyway,
because the key is what the source says rather than what the interpreter does. That is the
residual cost of this scheme, and it is the right one to keep: a caught set that was edited is a
handler whose contract was edited, which is a question a reader should answer rather than a
position to bump.

## What a reader does when a key goes stale now

The failure names the handler by scope, so a stale key means the scope was renamed, the handler
moved to another function, or its caught set changed. All three are questions about `src/`. The
old advice — re-anchor to the line the failure printed and re-run — is gone from the docstring,
because it was advice for a key that carried no information.

`test_driver_enters_the_handler_it_names` now prints the keys the run *did* enter beside the one
it expected. A driver that reaches a sibling arm rather than its own is the mistake this file was
built to catch, and it reads better as two lists than as one absence.

## Gates

```
uv run pytest                                             2463 passed, 1 skipped, 1 failed
uv run lint-imports                                       Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src scripts tests  exit 0
uv run python scripts/lint_dead_links.py src --baseline scripts/dead_links_baseline.txt   exit 0
```

The one failure is `test_symbol_map_pin.py::test_the_staged_map_matches_the_pin_this_corpus_records`,
and it is not this task's. The staged symbol map in this worktree digests to `78dbd1e0…` where the
corpus pin records `5f71dcd3…`; the staged map is a fetched artifact rather than source, the test
skips outright when it is absent, and the failure reproduces with this branch's tree clean and
nothing of B63 applied. Either the artifact was refreshed against a newer spec or the pin moved,
and both are the pin task's to settle — overwriting either one from here would silence the check
that noticed.

`tests/test_decode_handlers.py` on its own: **25 passed**.

## The closure conditions, re-checked independently

The four conditions the backlog set for this item were each re-run against real `src/` after the
work above, by a second pass that had not written it. Each edited one module, ran the check that
is supposed to answer, restored the file, and confirmed the restoration byte-for-byte.

| condition | experiment | result |
|---|---|---|
| keys survive an unrelated edit above a handler | three comment lines above `read_checkout`'s handler | 25 passed |
| a handler with no driver still fails by name | a decode handler appended to `sync/benchmark/checkout.py` | fails naming `sync/benchmark/checkout.py::read_one::UnicodeDecodeError` |
| a driver whose handler is gone still fails | `read_checkout` renamed to `read_checkout_tree` | fails naming the stale key |
| a collision is refused naming both | the same chain written twice in `read_checkout` | fails naming `checkout.py:81` and `checkout.py:85` |

The first is the one worth stating plainly: under the positional key that edit re-anchored a key
and failed the file. It now changes nothing, which is the whole of what B63 was for.

## One thing found that is not this task

The worktree this task was dispatched into, `m2-depth`, was 149 commits behind `main` and carried
no commits of its own. `tests/test_decode_handlers.py` does not exist at its `HEAD`, which is the
most likely reason the previous attempt at B63 produced nothing: the file the brief names is not
there, and every search for it fails. The work here was done on `b63-scope-keys`, branched from
`main` inside that worktree; the `stroland02/m2-depth` ref was left where it was.
