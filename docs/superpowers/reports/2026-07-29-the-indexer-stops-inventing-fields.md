# The indexer read the customer's code more loosely than the vendor's, and invented a field

**Date:** 2026-07-29
**Scope:** B58 — four copies of one node reader; the two over a vendor's SDK decoded strictly, the
two over the customer's repository passed `errors="replace"`.
**Outcome:** an undecodable source file is skipped and named instead of mangled; all four copies
now decode the same way; nine tests, all watched red first; four gates green.

## The asymmetry, as four lines

```
signals/generated/symbols_typescript.py:164   source[a:b].decode("utf-8")                      vendor's SDK
signals/generated/symbols_speakeasy.py:178    source[a:b].decode("utf-8")                      vendor's SDK
index/typescript.py:63                        source[a:b].decode("utf-8", errors="replace")    customer's code
index/python_lang.py:82                       source[a:b].decode("utf-8", errors="replace")    customer's code
```

One helper, four copies, same parser, opposite discipline — and the lenient half is the one pointed
at somebody else's repository. `cli._literal_call_sites` was a fifth reader of the same files and
said it outright: `read_text(encoding="utf-8", errors="replace")`.

The repository had already argued this out twice, in writing, and neither argument reached the
indexer:

- `benchmark/read_checkout` — "Skipped rather than decoded leniently. `errors="replace"` would hand
  the indexer a file full of replacement characters, which is still a file it will parse." So a
  corpus score is measured with undecodable files skipped and named, and a customer scan was run
  with them mangled and silent. Every benchmark number was taken under a rule the product did not
  apply.
- `python_lang._read_manifests` — "Neither is decoded leniently: `errors="replace"` would turn that
  file into requirement strings nothing in it declares." Eighty lines above the loop that did
  exactly that to the source.

`PythonAdapter._syntax_errors` is the sharpest one: it reads the *same file list* with
`read_text(encoding="utf-8")` and records every path that fails, three hundred lines from the
indexing pass that substituted instead. One class, two answers.

## What the leniency actually produced

Measured on one cp1252 file per language — legal cp1252, legal TypeScript, and legal Python under
PEP 263 — with `charges.create({ "coût": 1, amount: 2 })` and a response read as `charge.stâtus`:

```
                        typescript                          python
args_keys               ['amount', 'coFFFDt']               ['amount', 'meta', 'meta.coFFFDt']
response_fields_read    ['st']                              ['st']
```

Two different failures, and the second is the one that matters.

`args_keys` carries a key the customer never wrote. `ParameterDeprecationDetector` joins on that
column, so the row is noise there — recognisable noise, at least, since `U+FFFD` is visible to
anyone who looks.

`response_fields_read` is `st`. The source says `stâtus`; the replacement character was not
inserted, the name was **truncated at the bad byte**. What reached the graph is a claim that this
call site depends on a response field named `st` — a perfectly ordinary field name, on a dependency
that does not exist. `ObservedDriftDetector` reads that column and `PropertyOmitRemediator` patches
against it. Nothing downstream can tell it from a real field, which is why an absence-of-`U+FFFD`
check is not the test for this and the row set is.

`2026-07-26-sync-review-integration.md` puts a false attribution above a missed finding in cost: a
missed one costs an incident, a false one costs the reviewer's willingness to read the next. This
manufactured them out of an encoding.

## What changed

**One gate, both passes.** `_readable_sources` yields `(path, bytes)` for files that decode and
warns naming the ones that do not. Both indexing passes read through it in both languages, so a
file the client pass skipped cannot be walked by the call pass. tree-sitter takes bytes and reports
byte offsets, so bytes are what is yielded and the decode is checked rather than kept.

**All four readers decode strictly.** After the gate, `_text` cannot meet bytes that do not decode,
so it raises rather than repairing — which is what holds a future caller to the gate instead of
letting it re-acquire the old behaviour quietly.

**Warned once per file, not once per pass.** Two passes over one clone would otherwise report one
file twice and read as two faults. A `set` on the adapter, alongside `_baselines` and
`_installed_at`, which are per-clone state for the same reason.

**`_literal_call_sites` skips and names too**, and stays on `read_text` rather than
`read_bytes().decode` — `index_operation_literals` derives line and column from that string,
`read_text` translates CRLF, and decoding by hand would move every position on a Windows checkout.
`read_checkout` makes the same point about the same call.

The warning reaches stderr on a run that configures no logging, through Python's default handler.
Verified rather than assumed:

```
src/legacy.py is not valid UTF-8, so it is not indexed and its call sites are absent from this
scan ('utf-8' codec can't decode byte 0xfb in position 139: invalid start byte)
```

## `_syntax_errors` deliberately does not read through the gate

It answers a different question — whether a patch to this repository can be verified — and an
undecodable file is a reason it cannot. So that pass keeps walking every path and keeps reporting
the ones that do not decode. Filtering them out of both would have let `static_verify` pass a
repository over a file it never looked at, which is the failure mode this change exists to close,
arriving from the other direction.

This is the same two-questions split `checkout.py` draws between "is this path part of the tree" and
"is this path source", and it is why the gate is a second reader rather than a filter inside
`_source_files`.

## The cost, stated

A source file in a legacy encoding now contributes **no** call sites where it used to contribute
corrupt ones. That is a real loss of coverage, not a free fix, and it is the same trade B45 recorded
for manifests. Two things make it the right direction:

- The lost sites were not sites. A truncated field name and a phantom argument key are wrong rows,
  and a wrong row costs more than a missing one.
- The path is named, so the loss is actionable. A reader who sees `src/legacy.ts` in the output
  knows to look; one handed a smaller finding count could not.

What would retire the trade is transcoding rather than guessing — reading the encoding a project
declares (PEP 263 for Python, a `.editorconfig` or tsconfig for TypeScript) and decoding through
it. Nothing here does that, and inferring an encoding from bytes cannot be done honestly: every
byte sequence valid in cp1252 is valid in cp1252.

## Out of scope, and why

**The vendor-side readers still raise on a vendor SDK that is not UTF-8.** `extract_symbols` would
abort the symbol build rather than skip the file. That is arguably correct — a vendor's own
generated SDK not being UTF-8 is a fault worth stopping on, not a legacy checkout — and changing it
is a decision about the signal stage rather than the index stage.

**`_literal_call_sites` still walks only `*.ts`.** A Python repository's model literals are not
indexed at all. Pre-existing, unrelated to encoding, and not touched here.

## Verification

Nine tests in `tests/test_source_decoding.py`, each watched red before the implementation existed —
seven failed, and the two that passed were the vendor-side readers, which is the asymmetry showing
up in the suite rather than only in the diff.

The four gates:

```
uv run pytest                                                      2159 passed, 2 skipped
uv run lint-imports                                                Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src tests                    exit 0
uv run python scripts/lint_dead_links.py src --baseline ...         exit 0
```

The fixtures are the exception `.claude/rules/test-discipline.md` allows — non-ASCII content added
specifically to exercise a decode path — and each is written with an explicit `.encode("cp1252")`,
because the bytes are the subject.
