"""No test module may hardcode the development database.

**Measured 2026-08-19, twice in one hour.** `conftest.pytest_configure` gives a run with
`SYNC_DSN` unset its own per-pid database, and its docstring says why: every fixture that touches
Postgres truncates the graph tables, so two runs against one database delete each other's rows.

`test_binding_status.py` was written with the development DSN inlined and so opted itself out of
that protection. Every run of it truncated the database the console reads, while the owner was
testing against it. The seed vanished twice and looked both times like data that had never landed
— which is the expensive part: a hardcoded DSN does not fail, it deletes somebody else's rows and
leaves a screen that reads as a feature not working.

Prose could not have prevented it. `conftest.py` already explains the scheme at length, at the top
of the file every test module sits beside, and it was read and not applied. This is the check
instead: `CLAUDE.md`'s rule is to encode a convention where it fails, and it fails at the moment
somebody types a connection string into a test.
"""

import re
from pathlib import Path

TESTS = Path(__file__).parent

# A module-level constant bound straight to the development database — the one shape that does the
# damage, because it is what a `GraphStore` gets built from.
#
# Narrowed to the assignment deliberately. The first version matched the literal anywhere and
# flagged three modules that never connect: one sets it as an environment variable for a child,
# one passes it to a function taking a fake store, and one is this file's own planted fixture.
# A lint firing on those is a lint somebody adds to `ALLOWED` until it covers nothing.
PINNED_CONSTANT = re.compile(
    r'^\s*[A-Za-z_][A-Za-z0-9_]*\s*=\s*"postgresql://[^"]*@localhost:5433/sync"\s*$'
)

# `conftest` declares the default it redirects *away from*, and `test_parallel_isolation` asserts
# on how a DSN is rewritten. Both would be untestable without writing one down. This file is here
# because its own fixtures are the shape it is looking for.
ALLOWED = {"conftest.py", "test_parallel_isolation.py", "test_no_hardcoded_dsn.py"}


def _offending_lines(source: str) -> list[str]:
    """Lines binding a name straight to the development database, without reading `SYNC_DSN`."""
    return [
        line.strip()
        for line in source.splitlines()
        if PINNED_CONSTANT.match(line) and "SYNC_DSN" not in line
    ]


def test_no_test_module_pins_itself_to_the_console_database():
    offenders: dict[str, list[str]] = {}
    for path in sorted(TESTS.glob("test_*.py")):
        if path.name in ALLOWED:
            continue
        found = _offending_lines(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found

    assert offenders == {}, (
        "these modules hardcode the development database and will truncate whatever is looking at "
        f"it: {offenders}. Read it from the environment instead — "
        'DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")'
    )


def test_the_check_recognises_the_shape_it_is_looking_for():
    """The lint proven against a planted offender rather than trusted.

    `test-discipline.md`: a test that has never failed has never been shown to test anything, and
    a lint that silently matches nothing passes forever while the thing it guards rots.
    """
    planted = 'DSN = "postgresql://sync:sync@localhost:5433/sync"'
    assert _offending_lines(planted) == [planted]

    # And does not fire on the correct form, or every module would be an offender.
    correct = 'DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")'
    assert _offending_lines(correct) == []
