"""Where a skipped directory entry surfaces, asserted at both call sites rather than at the parser.

`parse_directory` records what it declined, and a channel neither caller reads is the defect that
recording closes, moved one level up. Two callers carry it. `assess_repository` merges it into
`IntakeReport.unreadable`, so it reaches the artifact and -- for free, because
`ReachabilityRanking` already carries that field through -- the ranked artifact as well. `sync
intake` also prints it to stderr. Both are asserted here, because M3-W90 established the
distinction that matters: *stderr is not the artifact.* The JSON is what a caller redirects to a
file, commits and diffs between runs, and a fault visible only in a terminal nobody kept did not
survive the run.

**One key, not two.** `IntakeReport.unreadable` already mixes three sources -- `package.json`,
`pyproject.toml`, `requirements.txt` -- and tells them apart by the prefix on each string rather
than by a key per source. A directory fault is the same kind of fact about a fourth input, and it
narrows *this* repository's answer in exactly the way the field exists to report: a catalogue entry
that would not parse is not a package no tier can serve, any more than an unreadable manifest is a
repository with no dependencies. So it goes under the same key, and each test below that touches
the artifact asserts no second key appeared beside it.

Every test pairs with a control over a directory that reads cleanly. A test that only asserts the
fault is reported cannot tell a working carry from one that reports something unconditionally.

No test here reaches the network. The directory documents are literals in this file, kept to the
fields the parser reads.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from sync.cli import main
from sync.signals.intake import assess_repository
from sync.signals.reachability import rank_reachability
from sync.signals.registry_tier.directory import parse_directory

# Two faults from two causes, and one of them drags its entry down with it: `acme.com` declares a
# version with no `swaggerUrl`, which costs the version and then the whole entry, so this document
# produces three records across two entries.
MALFORMED = {
    "acme.com": {"preferred": "1.0", "versions": {"1.0": {"openapiVer": "3.0"}}},
    "scalar.com": "not an object",
}

READABLE = {
    "acme.com": {
        "preferred": "1.0",
        "versions": {
            "1.0": {
                "added": "2026-01-01T00:00:00.000Z",
                "updated": "2026-06-01T00:00:00.000Z",
                "swaggerUrl": "https://api.apis.guru/v2/specs/acme.com/1.0/openapi.json",
                "openapiVer": "3.0",
            }
        },
    }
}


@pytest.fixture()
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "declares"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps({"dependencies": {"acme-sdk": "^1.0.0"}}), encoding="utf-8"
    )
    return root


def _report(root: Path, document: dict):
    entries, unreadable = parse_directory(document)
    return assess_repository(root, registry_entries=entries, registry_unreadable=unreadable)


# --- caller one: assess_repository, which owns the artifact -------------------------------


def test_assess_repository_carries_a_directory_fault_into_the_report(checkout):
    """The parser's second half has to arrive somewhere, and this is the caller that keeps it."""
    _, faults = parse_directory(MALFORMED)

    report = _report(checkout, MALFORMED)

    assert len(faults) == 3
    assert all(fault in report.unreadable for fault in faults)


def test_a_directory_that_reads_cleanly_leaves_the_report_saying_nothing_was_unreadable(checkout):
    """The control. Present and empty, which is the state the field is defined to have on a clean
    read -- an absent one does not distinguish a clean scan from a caller that never looked."""
    report = _report(checkout, READABLE)

    assert report.unreadable == ()


def test_the_artifact_emits_a_directory_fault_under_the_same_key_as_a_manifest_fault(tmp_path):
    """One rule for a reader, over both inputs.

    A truncated `package.json` and a malformed catalogue entry are faults in two different files
    that narrow the same report, and they land in one list distinguished by the prefix on each
    string. Asserting the key set is what makes that a rule rather than a coincidence: a second
    key beside `unreadable` would be a second thing every reader of this artifact has to know.
    """
    root = tmp_path / "broken"
    root.mkdir()
    (root / "package.json").write_text('{"dependencies": {"acme-sdk": "^1.0.0"', encoding="utf-8")

    payload = json.loads(_report(root, MALFORMED).to_json())

    assert set(payload) == {"counts", "dependencies", "unreadable"}
    assert any("package.json" in problem for problem in payload["unreadable"])
    assert any("registry directory" in problem for problem in payload["unreadable"])


def test_the_ranked_artifact_carries_a_directory_fault_without_being_told_about_directories(
    checkout,
):
    """`ReachabilityRanking` needed no change, and that is the argument for the key.

    M3-W90 carried `IntakeReport.unreadable` into the ranking under the same name and shape for
    exactly this reason. A directory fault reaching the ranked artifact with nothing added to
    `reachability.py` is what a shared vocabulary buys, and asserting it here is what stops a
    later change to either side from quietly dropping it.
    """
    payload = json.loads(rank_reachability(_report(checkout, MALFORMED)).to_json())

    assert set(payload) == {"counts", "rows", "unreadable"}
    assert any("registry directory" in problem for problem in payload["unreadable"])


def test_the_ranked_artifact_of_a_readable_directory_reports_nothing_unreadable(checkout):
    payload = json.loads(rank_reachability(_report(checkout, READABLE)).to_json())

    assert payload["unreadable"] == []


# --- caller two: sync intake, which owns the command line ---------------------------------


def _intake(monkeypatch, capsys, root: Path, document: Path | None):
    argv = ["sync", "intake", "--repo", str(root)]
    if document is not None:
        argv += ["--registry-directory", str(document)]
    monkeypatch.setattr(sys, "argv", argv)
    code = main()
    captured = capsys.readouterr()
    assert code == 0
    return json.loads(captured.out), captured.err


def _document(tmp_path: Path, content: dict) -> Path:
    path = tmp_path / "list.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return path


def test_the_command_line_puts_a_directory_fault_in_the_artifact_and_on_stderr(
    monkeypatch, capsys, tmp_path, checkout
):
    """Both surfaces, because they answer to different readers.

    stdout is the record and stderr is the operator watching the run, and a fault that reached
    only one of them is a fault somebody does not have. Exit code stays 0 for the reason `intake`
    already documents: it says the report was produced, not that the answer was good.
    """
    payload, err = _intake(monkeypatch, capsys, checkout, _document(tmp_path, MALFORMED))

    assert [problem for problem in payload["unreadable"] if "acme.com" in problem]
    assert "scalar.com" in err
    # A catalogue entry is not a manifest, and the line that reports it must not say it is.
    assert "unreadable manifest:" not in err


def test_the_command_line_reports_nothing_for_a_directory_that_reads(
    monkeypatch, capsys, tmp_path, checkout
):
    payload, err = _intake(monkeypatch, capsys, checkout, _document(tmp_path, READABLE))

    assert payload["unreadable"] == []
    assert "registry directory" not in err


def test_a_run_given_no_directory_at_all_is_not_a_fault(monkeypatch, capsys, checkout):
    """Nothing to read is a fact about the invocation; something unreadable is a fault. Intake
    already holds that distinction for a repository with no manifest, and collapsing it here would
    put a line on stderr for every run that did not pass the flag."""
    payload, err = _intake(monkeypatch, capsys, checkout, None)

    assert payload["unreadable"] == []
    assert "registry directory" not in err
