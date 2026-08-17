"""A crashed xdist worker must not read as failing tests.

Measured on 2026-08-17: a full run reported roughly thirty `F` marks and no summary after
`[gw0] node down: Not properly terminated`. Every one of those marks was printed against a test
that never ran to a verdict, and the run read as a catastrophic regression that did not exist.
An earlier run of the same tree, allowed to finish, reported `1 failed, 3742 passed`.

The two are not distinguishable by counting. They are distinguishable by one line, and this
module is the check that reads it, so no lane has to know the signature by heart.

`.claude/rules/test-discipline.md` states the doctrine: a test that cannot fail is worse than no
test. A gate whose verdict cannot be trusted is the same defect at the level of the run — it
manufactures a regression rather than confidence, and costs whoever meets it a diagnosis of code
that is fine.
"""

from __future__ import annotations

from scripts.gate_verdict import Verdict, read_verdict

CLEAN = """\
bringing up nodes...
........................................................................ [ 50%]
........................................................................ [100%]
1 failed, 3742 passed, 4 skipped, 4 warnings in 310.43s (0:05:10)
"""

CRASHED = """\
bringing up nodes...
.................................................F.[gw0] node down: Not properly terminated
FFFFFFF......................................F
worker 'gw0' crashed while running 'tests/test_remediation_graph.py::test_a_patch_that_only_typechecks'
60 failed, 3744 passed, 4 skipped, 5 warnings in 991.35s (0:16:31)
"""

TRUNCATED = """\
bringing up nodes...
........................................................................ [ 96%]
.................................................F.[gw0] node down: Not properly terminated
FFFFFFF......................................F
"""

INTERNAL = """\
INTERNALERROR> Traceback (most recent call last):
INTERNALERROR>   File "xdist/dsession.py", line 267, in worker_errordown
INTERNALERROR>     self._active_nodes.remove(node)
INTERNALERROR> KeyError: <WorkerController gw5>
no tests ran in 22.75s
"""


def test_a_clean_run_is_trustworthy() -> None:
    verdict = read_verdict(CLEAN)

    assert verdict.trustworthy is True
    assert verdict.crashed_workers == []
    assert verdict.summary == "1 failed, 3742 passed, 4 skipped, 4 warnings in 310.43s (0:05:10)"


def test_a_crashed_worker_makes_the_run_untrustworthy_however_it_ended() -> None:
    """The dangerous case: a summary line exists and looks like an ordinary verdict.

    `60 failed` is what a reader takes away, and some unknown share of those sixty are marks
    against tests the dead worker never got to. The count is not wrong so much as unattributable,
    which is the same objection this project raises to a finding that cannot name its rung.
    """
    verdict = read_verdict(CRASHED)

    assert verdict.trustworthy is False
    assert verdict.crashed_workers == ["gw0"]


def test_the_crash_names_the_test_that_was_running() -> None:
    """Without this the next reader has a dead worker and nowhere to start."""
    verdict = read_verdict(CRASHED)

    assert verdict.crashed_on == [
        "tests/test_remediation_graph.py::test_a_patch_that_only_typechecks"
    ]


def test_a_run_that_never_reached_a_summary_is_untrustworthy() -> None:
    verdict = read_verdict(TRUNCATED)

    assert verdict.trustworthy is False
    assert verdict.summary is None


def test_an_internal_error_is_untrustworthy_even_though_no_worker_line_appears() -> None:
    """`no tests ran` with a non-zero exit is the other shape of the same lie.

    xdist reports its own bookkeeping crash as `INTERNALERROR`, and the run then claims no tests
    ran — which is true and useless. A lane reading only the last line would record a green.
    """
    verdict = read_verdict(INTERNAL)

    assert verdict.trustworthy is False


def test_the_reason_is_stated_rather_than_left_to_the_reader() -> None:
    reason = read_verdict(CRASHED).reason

    assert reason is not None
    assert "gw0" in reason


def test_a_clean_run_states_no_reason() -> None:
    """Silence is the ordinary case, the way an adapter that binds asserts nothing."""
    assert read_verdict(CLEAN).reason is None


def test_a_verdict_is_readable_without_reading_the_dots() -> None:
    """The rendered line is what a lane pastes into a report, so it carries the verdict word."""
    assert read_verdict(CRASHED).render().startswith("UNTRUSTWORTHY")
    assert read_verdict(CLEAN).render().startswith("TRUSTWORTHY")


def test_verdict_is_a_value_rather_than_a_print() -> None:
    """So a caller can gate on it. A checker that only prints cannot be wired into anything."""
    assert isinstance(read_verdict(CLEAN), Verdict)
