---
paths:
  - "tests/**"
  - "web/src/**/*.test.ts"
  - "web/src/**/*.test.tsx"
---

# Tests

`CLAUDE.md` carries *test first, and watch it fail for the reason you expect*, and
`src/sync/CLAUDE.md` carries the fixture and admin-connection rules. These are what only matters
once you are inside a test file.

## A skip is a test that cannot fail, in a different shape

It reports as neither pass nor fail, so a skip with no real reason manufactures the same false
confidence. `scripts/lint_test_skips.py` is the check: **a skip is permitted only when its reason
names a platform or a genuinely absent local toolchain.** "because" and "flaky" name neither.

Prove that lint the way you prove any other: plant an unqualified `pytest.skip(...)`, watch the
linter exit non-zero naming the file and line, remove it, watch it pass.

## Assert on shape, not on incidental values

A test pinning an exact error string, a timestamp or a dict ordering fails on changes that break
nothing. Assert the property the code promises.

## Encoding bugs are a lint, not a test

Do not try to catch a missing `encoding="utf-8"` with a test — every fixture here is ASCII, so no
test can. It is `scripts/lint_encoding.py` plus a PostToolUse hook. A fixture with non-ASCII content
added to exercise a decode path is welcome, but it does not replace the lint, which covers call
sites no fixture reaches.

## Run focused while iterating, full before committing

`uv run pytest tests/test_x.py::test_name -v` while working. The full suite once before the commit.

## Console tests

Scope is **classification, derivation and structural invariants — never class names, never
snapshots**; `web/CLAUDE.md` carries why, and where a rule belongs when the payload could answer it
instead.

**The proven-RED requirement applies here exactly as in `tests/`.** Every guard in
`web/src/**/*.test.*` was shown red against a deliberately broken subject before it was trusted.
That is a permanent increase in per-task cost, stated rather than hidden.
