"""`sweep_leaked_databases` must hold its invariant when psycopg's classes are split in two.

`coverage` resolves a dotted `--cov=<module>` by importing that module inside
`coverage.misc.sys_modules_saved()`, whose `restore()` deletes from `sys.modules` every
module the import pulled in. When the named module reaches psycopg -- as
`sync.benchmark.mutate` does -- all 77 psycopg modules are evicted and imported again.

`psycopg/errors.py` is pure Python, so it re-executes and builds a second set of exception
classes. `psycopg_binary._psycopg` is an extension module, cached by the interpreter below
`sys.modules`, so it is *not* re-executed and keeps its references to the first set. The
class its connect generator raises is then absent from the MRO of the class
`except psycopg.Error` names, `isinstance` is False, and the handler does not catch.

The split is process-wide and poisons every later import, so it is constructed in a child
rather than here. `docs/superpowers/reports/2026-07-29-psycopg-error-identity.md` carries
the measurements.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Nothing listens here, and on this machine a closed port times out rather than refusing,
# so the failure arrives from the C connect generator -- which is the half of the split that
# matters. A bare host rather than `localhost` so libpq makes one attempt and not two.
UNREACHABLE = "postgresql://sync:sync@127.0.0.1:1/postgres"

CHILD = '''
import sys

import psycopg

before = psycopg.errors.ConnectionTimeout

evicted = [m for m in sys.modules if m.split(".")[0] in ("psycopg", "psycopg_binary")]
for name in evicted:
    del sys.modules[name]

import psycopg  # noqa: F811

print("SPLIT=%s" % (psycopg.errors.ConnectionTimeout is not before))

# After the eviction, so the handler binds the classes a coverage run would leave it --
# coverage evicts at plugin-load time, before conftest is imported.
sys.path.insert(0, {tests_dir!r})
from conftest import sweep_leaked_databases

print("RETURNED", sweep_leaked_databases({dsn!r}))
'''


def test_the_sweep_survives_psycopg_classes_being_split_in_two(tmp_path: Path) -> None:
    """The invariant is `sweep_leaked_databases`'s own: nothing here may fail the run.

    A handler naming `psycopg.Error` does not hold it, because class identity is not
    guaranteed across the eviction. The child asserts the split happened before it asserts
    anything about the handler, so this cannot pass by failing to reproduce it.
    """
    script = tmp_path / "split.py"
    script.write_text(
        CHILD.format(tests_dir=str(Path(__file__).parent), dsn=UNREACHABLE), encoding="utf-8"
    )

    done = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        timeout=180,
    )

    assert (
        "SPLIT=True" in done.stdout
    ), f"the split did not reproduce, so nothing was tested: {done!r}"
    assert done.returncode == 0, f"the sweep raised instead of returning: {done.stderr}"
    assert "RETURNED []" in done.stdout, done.stdout
