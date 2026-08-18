"""The register is one table of unique ids, and nothing but a check keeps it that way.

`M0-W346`: `WORKLOG.md` reached 32 nested copies of itself -- 1,533,135 lines and 10.7MB holding
9,686 rows for 335 work items -- because a merge conflict spanning the whole file was resolved by
keeping both sides, and the next merge then had two whole sides to keep. It grew by doubling, so it
was invisible for a day and then enormous in an hour.

No memory prevents this. A rule in `CLAUDE.md` did not, because the agent resolving the conflict is
not reading about registers; it is reading a conflict. So it is a check.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_worklog", _ROOT / "scripts" / "check_worklog.py"
)
check_worklog = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_worklog)

CLEAN = [
    "# Work items",
    "",
    "| id | what | state | files |",
    "|---|---|---|---|",
    "| M0-W001 | first | landed | `a.py` |",
    "| M0-W002 | second | landed | `b.py` |",
]


def test_a_clean_register_reports_nothing():
    assert check_worklog.faults(CLEAN) == []


def test_a_second_heading_is_the_duplication_itself():
    """One `# Work items` per file. Two means a copy was concatenated on."""
    faults = check_worklog.faults(CLEAN + CLEAN)
    assert any("# Work items" in f for f in faults)


def test_a_repeated_id_is_reported_with_the_id_and_both_line_numbers():
    """Two lanes taking one number is the collision the push-is-the-lock rule exists to stop."""
    faults = check_worklog.faults(CLEAN + ["| M0-W001 | again | landed | `c.py` |"])
    assert any("M0-W001" in f for f in faults)
    assert any("5" in f and "7" in f for f in faults), faults


def test_the_repeated_id_check_does_not_fire_on_a_mention_inside_another_row():
    """`M0-W002` citing `M0-W001` in its prose is normal and is not a second claim on the number."""
    cited = CLEAN[:-1] + ["| M0-W002 | supersedes `M0-W001` | landed | `b.py` |"]
    assert check_worklog.faults(cited) == []


def test_the_real_register_is_clean():
    """The check runs against the file it guards, not only against fixtures."""
    register = _ROOT / "docs" / "superpowers" / "WORKLOG.md"
    assert check_worklog.faults(register.read_text(encoding="utf-8").splitlines()) == []


# --- the resolver, which must not trust the side it is told is authoritative ------------------

_R_SPEC = importlib.util.spec_from_file_location(
    "rebuild_worklog", _ROOT / "scripts" / "rebuild_worklog.py"
)
rebuild_worklog = importlib.util.module_from_spec(_R_SPEC)
_R_SPEC.loader.exec_module(rebuild_worklog)


def test_the_resolver_normalises_a_corrupt_skeleton():
    """Every lane branch holds the corrupt file, so `--ours` is usually the bad side.

    A resolver that trusts its skeleton would carry thirty-two copies straight through the
    resolution that was supposed to end them.
    """
    corrupt = CLEAN + CLEAN + CLEAN
    merged = rebuild_worklog.rebuild(corrupt, CLEAN)
    assert check_worklog.faults(merged) == []


def test_the_resolver_keeps_every_id_from_either_side():
    theirs = CLEAN + ["| M0-W003 | only on their side | landed | `c.py` |"]
    merged = rebuild_worklog.rebuild(CLEAN + CLEAN, theirs)
    assert check_worklog.faults(merged) == []
    assert [line for line in merged if "M0-W003" in line]
    assert [line for line in merged if "M0-W001" in line]


def test_the_resolver_is_safe_in_either_orientation():
    """Same inputs, swapped, must reach the same set of ids."""
    theirs = CLEAN + ["| M0-W003 | only on their side | landed | `c.py` |"]
    ids = lambda out: {  # noqa: E731
        m.group(1) for line in out if (m := check_worklog.ROW.match(line))
    }
    assert ids(rebuild_worklog.rebuild(CLEAN + CLEAN, theirs)) == ids(
        rebuild_worklog.rebuild(theirs, CLEAN + CLEAN)
    )


def test_the_resolver_keeps_rows_that_only_exist_inside_a_later_copy():
    """The row that gets lost by the obvious fix, and it was 32 of 335 in the real file.

    Once the file is several copies deep, new rows land at the end of whichever copy the appending
    agent's editor reached -- not at the end of the first one. Truncating the input at the second
    `# Work items` heading produces a clean file that is quietly missing them.
    """
    buried = CLEAN + CLEAN + ["| M0-W009 | appended inside the third copy | landed | `d.py` |"]
    merged = rebuild_worklog.rebuild(buried, CLEAN)
    assert check_worklog.faults(merged) == []
    assert [line for line in merged if "M0-W009" in line], "row inside a later copy was dropped"


def test_at_the_first_doubling_the_resolver_is_exact():
    """Why this pair is enough, and why neither half is over-built.

    `normalise` deduplicates rows but not prose, so replayed against the real 32-copy file it
    returns every id and still carries repeated prose. That residue only exists because the file was
    allowed to reach 32 copies. `check_worklog` fires at the *first* doubling, where the two halves
    are identical and truncating at the second heading is exactly right -- so the guard keeps the
    resolver in the regime where it is lossless in both directions.
    """
    assert rebuild_worklog.normalise(CLEAN + CLEAN) == CLEAN
