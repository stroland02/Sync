"""`sync vendors probe`: does every configured row still point at something that exists?

`CI-W581` closed this class of defect with a test, and a test is the wrong shape for the person
who needs the answer: finding a stale row should not require knowing pytest, a marker name and a
deselect rule. The row for the most-called vendor in the corpus pointed at a 404 for eleven days
with every gate green, and the operator-facing way to have noticed did not exist.

Every case here injects the fetch. The command reaches the network when a person runs it and
never when the suite does.
"""

from __future__ import annotations

import argparse

from sync.cli import vendors_probe


def _args(**over) -> argparse.Namespace:
    return argparse.Namespace(**over)


def _reachable(url: str) -> tuple[bool, str]:
    return True, "200"


def test_a_configuration_that_resolves_reports_every_row_and_exits_zero(capsys):
    code = vendors_probe(_args(), probe=_reachable)

    printed = capsys.readouterr().out
    assert code == 0
    assert "stripe" in printed and "anthropic" in printed
    # The count is the operator-facing half: "18 rows, 18 reachable" is a different sentence
    # from silence, and silence is what a probe that found nothing used to look like.
    assert "18" in printed


def test_a_stale_row_is_named_and_the_command_exits_non_zero(capsys):
    def one_gone(url: str) -> tuple[bool, str]:
        return (False, "404") if "openai" in url else (True, "200")

    code = vendors_probe(_args(), probe=one_gone)

    printed = capsys.readouterr()
    assert code == 1
    assert "openai" in printed.err
    assert "404" in printed.err
    # What to do about it, not merely that it happened.
    assert "moved" in printed.err.lower() or "repoint" in printed.err.lower()


def test_the_probe_reports_which_document_of_a_multi_document_row_is_gone(capsys):
    """A vendor publishing several documents has several ways to go stale, and naming the vendor
    alone would leave an operator opening four URLs by hand."""
    def one_document_gone(url: str) -> tuple[bool, str]:
        return (False, "404") if "twilio_verify_v2" in url else (True, "200")

    code = vendors_probe(_args(), probe=one_document_gone)

    assert code == 1
    assert "twilio_verify_v2" in capsys.readouterr().err


def test_the_command_reaches_no_network_of_its_own_when_a_probe_is_given():
    """The injection point is the whole reason this file can run in the default suite."""
    asked: list[str] = []

    def recording(url: str) -> tuple[bool, str]:
        asked.append(url)
        return True, "200"

    vendors_probe(_args(), probe=recording)

    assert asked, "the probe was never called, so this test could not fail"
    assert all(url.startswith("https://raw.githubusercontent.com/") for url in asked)
