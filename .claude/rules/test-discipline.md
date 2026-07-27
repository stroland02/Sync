---
paths:
  - "tests/**"
---

# Test rules

## Watch it fail first

Write the failing test, run it, watch it fail *for the reason you expect*, then implement. A
test that has never failed has never been shown to test anything.

## A test that cannot fail is worse than no test

It manufactures confidence. When a test asserts on a subprocess, an exit code, or an external
tool, prove it detects a real violation before trusting it — break the thing deliberately,
watch the test go red, restore it.

This has bitten this repository already: the import-boundary test's original form exited 0
without parsing its own argument. It passed for the wrong reason and would have kept passing
through any violation.

## No vendor API, no model API

Fixtures are committed. Local toolchain access is fine — the Postgres container, `npx`
fetching a compiler. The one end-to-end test is marked `@pytest.mark.e2e` and deselected by
default via `addopts`.

## Fixtures are ASCII, so encoding bugs are invisible here

Every fixture in this repository is ASCII. That means **no test will ever catch a missing
`encoding="utf-8"`** — the failure arrives first against real vendor data or a real customer
repository, on Windows, where the default is cp1252.

Do not try to solve this with a test. It is a lint (`scripts/lint_encoding.py`), and the lint
is what runs in CI. If you are adding a fixture with non-ASCII content specifically to
exercise a decode path, that is welcome — but it does not replace the lint, because the lint
covers call sites no fixture reaches.

## Assert on shape, not on incidental values

A test that pins an exact error string, a timestamp, or a dict ordering fails on changes that
break nothing. Assert the property the code promises.

## Run focused while iterating, full before committing

`uv run pytest tests/test_x.py::test_name -v` while working. `uv run pytest` once before the
commit. Never `python3` — that is a Microsoft Store shim on this machine and it will not run.
