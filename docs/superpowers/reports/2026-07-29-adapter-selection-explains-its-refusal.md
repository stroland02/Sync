# Adapter selection stops blaming the repository for our missing configuration

**Date:** 2026-07-29
**Scope:** B55 — `cli.select_language_adapter` answered five different declines with one sentence,
and for one of them the sentence was false.
**Outcome:** each indexer now accounts for its own decline; a UTF-16 `package.json` is declined
instead of raising out of `matches`; nine tests, all watched red first; four gates green.

## What the refusal used to say

Five situations reach the end of the selection loop, and every one of them produced this:

```
https://example.invalid/r declares no SDK any indexer recognises; tried: python, typescript
```

They are five different jobs. Named in the order a reader has to act on them:

| situation | whose fault | what fixes it |
|---|---|---|
| the vendor's adapter declares no SDK package | **ours** | an `sdk_bindings` entry |
| a manifest declares the package and will not parse or decode | the repository's, mechanically | fix the file |
| there is no manifest at all | neither | point Sync at a project with one |
| a manifest was read and does not name the package | neither | nothing; the answer is correct |
| a UTF-16 `package.json` | **ours** | it did not decline at all — see below |

The first row is the one that matters most, because the sentence was not merely vague there, it
was wrong. Four of the six registered vendors — anthropic, cloudflare, openai, vercel — are served
by `GeneratedSpecAdapter`, which declares no binding in any language. Run against a repository
that imports `@anthropic-ai/sdk`, selection told the customer their repository declares no SDK any
indexer recognises. The repository declares one. What is absent is a line of this deployment's
configuration, and the message sent whoever read it to audit the wrong file.

`registry.vendor_sdk_bindings` already says this gap "is reported rather than hidden", and
`sync.signals.intake` is what reports it — one reason per dependency, with `MISSING_SDK_BINDING`
naming which half is missing. Selection was the surface still hiding it, and it is the surface
where a run actually stops.

## What it says now

The same five cases, re-run against the fix:

```
1. vendor declares no binding; repository imports @anthropic-ai/sdk
  no indexer claims https://example.invalid/r for vendor 'anthropic':
  typescript: vendor 'anthropic' declares no typescript package, so no manifest could match it
              -- the absent configuration is sdk_bindings, not anything in this repository
  python: vendor 'anthropic' declares no python distribution, so no manifest could match it
          -- the absent configuration is sdk_bindings, not anything in this repository

2. package.json declares stripe but does not parse
  typescript: package.json could not be read: Expecting property name enclosed in double quotes:
              line 1 column 38 (char 37), so what this repository declares is unknown
  python: no pyproject.toml or requirements.txt in this repository declares a dependency

3. requirements.txt declares stripe and is UTF-16
  typescript: no package.json in this repository declares a dependency
  python: requirements.txt could not be read: 'utf-8' codec can't decode byte 0xff in position 0:
          invalid start byte, so what this repository declares is unknown

4. repository genuinely does not depend on the vendor
  typescript: package.json declares 1 dependency and 'stripe' is not one of them
  python: no pyproject.toml or requirements.txt in this repository declares a dependency

5. no manifest of any kind
  typescript: no package.json in this repository declares a dependency
  python: no pyproject.toml or requirements.txt in this repository declares a dependency
```

Case 4 names the package that was looked for, which is the only way a customer can check the one
claim in the set that is about their repository. It does not name what the manifest *does* declare:
a dependency list is the customer's business and does not belong in a log line.

## The crash nobody had found

`TypeScriptAdapter._declared_dependencies` caught `json.JSONDecodeError` and nothing else, so a
UTF-16 `package.json` raised `UnicodeDecodeError` out of `matches` and took the run down at
selection:

```
  File "src\sync\index\typescript.py", line 202, in matches
    return self._package is not None and self._package in self._declared_dependencies(repo)
  File "src\sync\index\typescript.py", line 194, in _declared_dependencies
    data = json.loads(manifest.read_text(encoding="utf-8"))
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte
```

This is the defect B45 closed for `requirements.txt`, one language over and still open. B45's own
report is precise about which branch it fixed and why the neighbouring one was already correct;
nobody looked at the other indexer, and the failure it shipped is worse there — Python's version
declared nothing, TypeScript's aborted the run. `sync.signals.intake._read_npm` catches both
exceptions and has since it was written, so the two surfaces reading the same file disagreed about
what an undecodable one means.

Both are caught now, and the case is covered for `package.json`, `pyproject.toml` and
`requirements.txt` in one parametrised test.

## Why `decline_reason` is optional

`LanguageAdapter.matches` stays `(RepoRef) -> bool`. `core.conformance._check_matches` requires
that shape explicitly — "The caller writes `if adapter.matches(repo)`" — and widening the protocol
would break every third-party adapter to add a message.

So `decline_reason(repo) -> str` is read with `getattr`, which is the pattern
`PythonAdapter.unverifiable_reason` already established for exactly this reason: an adapter that
has never heard of the attribute keeps working unchanged. An indexer that does not implement it is
listed as `declined without saying why`, which is a fact about that adapter and more useful than a
blank line.

`_decline_line` cannot raise, and that is the whole reason it is a function rather than an
expression inside the loop. It runs while the run is already stopping and it is the one place every
indexer's account is assembled, so one adapter's failure would trade all of them for a traceback
*about the refusal* instead of the refusal. A missing `language_id`, a missing explanation and a
failing one all resolve to something printable that names the adapter. That defence is not new — it
is what the `getattr` in the old code was written for, carried across to the new method.

## The reader split, and why both indexers grew a second return

`decline_reason` needs a fact `matches` throws away: whether the manifest was read at all. Both
indexers now have a reader that returns the declaration *and* the unreadability, with the old
single-value method kept as a thin wrapper over it — `_read_manifest` under
`_declared_dependencies` in TypeScript, `_read_manifests` under `_requirement_lines` in Python.

This is the shape `intake.read_declared_dependencies` already uses, returning
`(dependencies, unreadable)`, and `IntakeReport` states the argument for it: a manifest that does
not parse "is a fact a customer needs, because a repository whose manifest is unreadable is not a
repository with no dependencies -- and reported as the latter it reads as a clean scan of an empty
project." Selection was reporting it as the latter.

Python returns a list rather than one reason, because it reads two files and either can fail
independently of the other.

## What this deliberately does not change

- **The exit code is still 2 for all five cases.** "Our configuration is missing" and "this
  repository does not use the vendor" are different outcomes and arguably deserve different codes,
  but nothing consumes the distinction yet, and inventing an exit code for a caller that does not
  exist is configuration nobody reads.
- **The conformance kit does not check `decline_reason`.** Checking it would make it de-facto
  mandatory for any adapter that runs the kit, which is the opposite of the design. The protection
  against a third party's version misbehaving is `_decline_line` catching, not the kit refusing.
- **An unreadable manifest still declares nothing.** B45 accepted that trade and its report names
  the cost: one non-UTF-8 byte anywhere loses adapter selection. That is unchanged. What changed is
  that the refusal now names the file, so the cost is payable by whoever reads it rather than
  silent.

## Verification

Nine new tests in `tests/test_adapter_selection_refusal.py`, each watched red before the
implementation existed. Seven failed on the assertion, and two errored instead — the UTF-16
`package.json` parameter raised `UnicodeDecodeError` where the test expected `LookupError`, which
is that case's correct red, and the third-party-adapter case raised `RuntimeError` out of the
selection loop.

The four gates, run on the finished branch:

```
uv run pytest                                                      2150 passed, 2 skipped
uv run lint-imports                                                Contracts: 1 kept, 0 broken
uv run python scripts/lint_encoding.py src tests                    exit 0
uv run python scripts/lint_dead_links.py src --baseline ...         exit 0
```

`tests/test_python_repository.py::test_a_repository_in_neither_language_is_refused_rather_than_guessed`
passes unchanged: it asserts both language ids appear in the refusal, which the per-language
prefixes satisfy.
