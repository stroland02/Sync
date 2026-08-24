"""The four beta gates, measured against this repository.

`docs/superpowers/plans/2026-08-17-sync-to-beta-scope.md` defines four gates and says beta is ready
when all four are "true and demonstrable, not when a milestone list is ticked". Until this script
existed they were demonstrated by a coordinator writing prose, which is the black box this product
exists to replace, pointed at our own readiness.

**`CANNOT TELL` is a first-class verdict and most of the care here goes into it.** A gate that
reported `MET` because it found no rows would be the worst available instance of the defect the
console spends six screens refusing: absence read as zero. So an unreachable database, a missing
report and an empty table each produce `CANNOT TELL`, and only a source that actually answered
produces `MET` or `NOT MET`.

The empty-corpus case is not hypothetical. `B129` found that every scan truncated
`migration_outcome` for weeks, so an empty corpus here cannot distinguish "no run ever opened a
pull request" from "a bug deleted the rows". Saying `NOT MET` there would be inventing a
measurement.

Run it: `uv run python scripts/beta_gates.py`. Add `--run-suite` to measure Gate 4's
green-`main` component, which costs about four minutes; without it that component reports
`CANNOT TELL` rather than assuming either answer.

Exit code is 0 when every gate is `MET`, 1 otherwise. `CANNOT TELL` is not a pass.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]

# Run as a script, `scripts/` is on `sys.path` and the repository root is not, so
# `import scripts.gate_verdict` fails — while under pytest it succeeds, because `pythonpath = ["."]`
# in `pyproject.toml` puts the root there. That difference hid a crash in `--run-suite` behind a
# green test suite: the flag this gate's own message told every reader to pass was the one path
# nothing executed.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MET = "MET"
NOT_MET = "NOT_MET"
CANNOT_TELL = "CANNOT_TELL"

_LABEL = {MET: "MET", NOT_MET: "NOT MET", CANNOT_TELL: "CANNOT TELL"}


class _Store(Protocol):
    def migration_outcomes(self) -> Sequence[Any]: ...


@dataclass(frozen=True)
class Verdict:
    """One gate's answer, and why.

    `evidence` is required rather than optional. A verdict without it is the prose this script
    replaces, in a fixed-width font, and the whole point is that a reader who doubts the answer can
    check it without asking anybody.
    """

    gate: str
    name: str
    status: str
    evidence: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError(f"gate {self.gate} has a verdict with no evidence behind it")


def _field(row: Any, name: str) -> Any:
    """Read a field from a row that may be a model or a mapping.

    The store hands back `MigrationOutcome` objects; the tests hand dicts. Accepting both keeps
    the gate logic testable without a database, which matters because the cases worth pinning here
    are the ones a database cannot easily be put into -- an outage, and an empty corpus.
    """
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)


def _real_runs(outcomes: Sequence[Any]) -> list[Any]:
    """Rows written by a real run.

    `sync rehearse` opens no pull request and marks its rows `is_rehearsal`. Counting one as
    evidence would be a fixture standing in for a measurement, which is exactly what Gate 2 was
    written to refuse.
    """
    return [row for row in outcomes if not _field(row, "is_rehearsal")]


def gate_one_loop_closes(store: _Store, *, resume_built: bool | None) -> Verdict:
    """Gate 1: one run produces a CI-green pull request, and a review comment resumes a run.

    Two claims, both required. B7 alone is half the gate: without the resume half Sync opens a
    pull request and stops watching, which the scope plan's Ruling 3 calls worse than not having
    patched.
    """
    name = "the loop closes"
    try:
        outcomes = list(store.migration_outcomes())
    except Exception as exc:  # noqa: BLE001 -- any failure to read is the same answer
        return Verdict(
            gate="1",
            name=name,
            status=CANNOT_TELL,
            evidence=[
                f"the corpus could not be read: {exc}",
                "an unreachable database says nothing about whether a run ever closed the loop",
            ],
        )

    real = _real_runs(outcomes)
    if not real:
        return Verdict(
            gate="1",
            name=name,
            status=CANNOT_TELL,
            evidence=[
                f"migration_outcome holds {len(outcomes)} row(s), {len(real)} of them from real runs",
                "an empty corpus cannot distinguish a loop that never closed from rows a bug "
                "removed: B129 truncated this table on every scan until it was fixed",
                "re-run this after one real run to get a measurement rather than an absence",
            ],
        )

    green = [
        row
        for row in real
        if _field(row, "pr_number") is not None and _field(row, "ci_result") == "passed"
    ]
    evidence = [
        f"{len(real)} real attempt(s) in the corpus, {len(green)} with a pull request that went green",
        "resume-on-review-comment built: "
        + ("could not be read" if resume_built is None else str(resume_built)),
    ]
    if not green:
        evidence.append("no attempt has produced a CI-green pull request, so B7 has never passed")
        return Verdict(gate="1", name=name, status=NOT_MET, evidence=evidence)
    if resume_built is None:
        evidence.append(
            "the second half could not be measured: the files carrying the resume path could not "
            "be read, which says nothing about whether the path is there"
        )
        return Verdict(gate="1", name=name, status=CANNOT_TELL, evidence=evidence)
    if not resume_built:
        evidence.append(
            "the first half holds and the second does not: no resume path, so a review comment "
            "leaves the run parked forever"
        )
        return Verdict(gate="1", name=name, status=NOT_MET, evidence=evidence)
    return Verdict(gate="1", name=name, status=MET, evidence=evidence)


def gate_two_evidence_exists(
    store: _Store, *, health_reader: Callable[[_Store], dict]
) -> Verdict:
    """Gate 2: the corpus carries real samples for merge rate and three of five axes.

    Reads `sync.dashboard.fleet.precedent_health` rather than recomputing the axes. That function
    already draws the distinction this script depends on -- `status` is `measured` or `unmeasured`
    and `value` is `None` rather than `0.0` when nothing was sampled -- and a second implementation
    of it here would be a fact written twice, which CLAUDE.md calls the most expensive debt in this
    repository because the disagreement is silent.
    """
    name = "the evidence exists"
    try:
        health = health_reader(store)
    except Exception as exc:  # noqa: BLE001
        return Verdict(
            gate="2",
            name=name,
            status=CANNOT_TELL,
            evidence=[
                f"precedent_health could not be read: {exc}",
                "no reading is not the same as a reading of zero",
            ],
        )

    summary = health.get("summary", {})
    measured = summary.get("axes_measured_count")
    total = summary.get("total_axes")
    merged = summary.get("pull_requests_merged")
    opened = summary.get("pull_requests_opened")

    if not summary.get("has_any_samples"):
        return Verdict(
            gate="2",
            name=name,
            status=CANNOT_TELL,
            evidence=[
                f"{measured} of {total} quality axes measured; every axis reports no samples",
                "unmeasured is absence rather than a value of zero, so there is nothing here to "
                "pass or fail yet",
                f"pull requests opened: {opened}, merged: {merged}",
            ],
        )

    evidence = [
        f"{measured} of {total} quality axes carry samples",
        f"pull requests opened: {opened}, merged: {merged}",
    ]
    if (measured or 0) < 3:
        evidence.append("the gate asks for merge rate plus at least three of the five axes")
        return Verdict(gate="2", name=name, status=NOT_MET, evidence=evidence)
    if not merged:
        evidence.append("merge rate has no numerator: no pull request has been recorded merged")
        return Verdict(gate="2", name=name, status=NOT_MET, evidence=evidence)
    return Verdict(gate="2", name=name, status=MET, evidence=evidence)


# What can put a sentence or a figure in front of a reader. Watching all of `web/` meant a token,
# a build config or a script re-opened this gate, and a gate that fires on a CSS tweak teaches the
# lane that clearing it is ceremony. Narrowed to three directories on Lane B's proposal, and that
# narrowing was wrong in a way worth recording rather than quietly widening.
#
# **An include-list of directory names is invisible-by-default, and it hid a real change.**
# `web/src/layouts` renders on every screen -- the deployment-identity sentence sits in the sidebar
# footer -- and was not one of the three, so Gate 3 read MET across `M14-W351`, which the gate could
# not see. Measured: the three-name list reports the console last changed at 13:13:59 and this one
# reports 13:27:20, the difference being `fa6693c`, a `layouts/` commit. `lib/`, `vendor/`,
# `App.tsx` and `main.tsx` were missing for the same reason -- nobody asked what else renders.
#
# So the set names what it excludes, which is the inversion `B129` made when a scan named the one
# table it spared rather than the two it cleared: a directory nobody thought about is watched
# instead of invisible. Tests, stylesheets and markdown stay out, because appearance is measured in
# `DESIGN.md` against rendered pixels and that is a different discipline with a different gate.
#
# The asymmetry justifies erring wide: this gate can only say MET or CANNOT TELL, never NOT MET, so
# a path wrongly left in costs a re-walk and a path wrongly left out costs a false MET on the gate
# about whether screens tell the truth.
CONSOLE_CLAIM_PATHS = (
    "web/src",
    ":(exclude)*.test.*",
    ":(exclude)*.css",
    ":(exclude)*.md",
)

# The line a sign-off writes to say when it was signed. A recorded date rather than the file's
# commit date, because a whitespace edit to the report is not a re-sign and git cannot tell the
# two apart.
_SIGNED = re.compile(r"^Signed:\s*(?P<when>\S+)\s*$", re.MULTILINE)

HISTORICAL = re.compile(r"^Historical:", re.MULTILINE)
"""A report that is unsigned on purpose, and says so, rather than one missing a signature."""

SIGNATURE_LINE = "Signed: <ISO 8601 timestamp>"


def signature_date(text: str) -> str | None:
    """The date a sign-off recorded for itself, or `None` if it recorded none."""
    match = _SIGNED.search(text)
    return match["when"] if match else None


def gate_three_console_truth(reports_dir: Path, *, console_changed_at: str | None) -> Verdict:
    """Gate 3: signed. Confirm the signature still corresponds to the tree.

    This does not re-derive the gate -- re-deriving a sign-off another lane made would be
    asserting a right this script does not have. It asks the cheaper question: is the thing signed
    still the thing here.

    **Every gate-3 report is read, not one named file.** The first version had a single path
    hardcoded, so when Lane B re-signed by landing a second document beside the first, the meter
    went on reading the original and reported the same stale timestamp after a genuine re-sign. A
    lane that does the work and watches the gate ignore it learns the gate is ceremony.

    **The signature date is the one the document records, not the one git holds.** A whitespace
    edit to a report is not a re-sign, and git cannot tell those apart. The cost is that a report
    without the line cannot be read, so that case says exactly which line to add rather than
    failing mysteriously.
    """
    name = "the console tells the truth about that evidence"
    reports = sorted(reports_dir.glob("*gate-3*.md")) if reports_dir.exists() else []
    if not reports:
        return Verdict(
            gate="3",
            name=name,
            status=CANNOT_TELL,
            evidence=[
                f"no gate-3 sign-off found in {reports_dir}",
                "the scope plan records this gate as signed; without a report the signature "
                "cannot be checked, and it is not assumed",
            ],
        )

    signed: list[tuple[str, Path]] = []
    unsigned: list[Path] = []
    historical: list[Path] = []
    for report in reports:
        try:
            text = report.read_text(encoding="utf-8")
        except OSError:
            text = ""
        recorded = signature_date(text) if text else None
        if recorded:
            signed.append((recorded, report))
        elif HISTORICAL.search(text):
            # Unsigned on purpose. `M0-W291` settled that the screen-pass report is the historical
            # record and carries no signature, after two reports disagreed about the mechanism that
            # reads them -- but the gate still listed it as missing one, which is what it would say
            # about a report somebody forgot to sign. A reader could not tell a deliberate omission
            # from a mistake, so every sweep re-asked the same question. Unmeasured is a legitimate
            # verdict here; ambiguous is not.
            historical.append(report)
        else:
            unsigned.append(report)

    evidence = [f"{len(reports)} gate-3 report(s) found: " + ", ".join(r.name for r in reports)]

    if not signed:
        evidence.append(
            "none of them records a signature date, so a re-sign cannot be distinguished from a "
            f"typo fix. Add a line reading `{SIGNATURE_LINE}` to the pass that is current"
        )
        return Verdict(gate="3", name=name, status=CANNOT_TELL, evidence=evidence)

    if historical:
        evidence.append(
            "carries no signature by design, so not read and not missing one: "
            + ", ".join(r.name for r in historical)
        )

    if unsigned:
        evidence.append(
            "not read, because they record no signature date: "
            + ", ".join(r.name for r in unsigned)
        )

    latest, source = max(signed)
    evidence.append(f"latest recorded signature {latest}, from {source.name}")

    if console_changed_at is None:
        evidence.append("the console's history could not be read, so staleness is unknown")
        return Verdict(gate="3", name=name, status=CANNOT_TELL, evidence=evidence)

    evidence.append(
        "console last changed "
        f"{console_changed_at}, over {', '.join(CONSOLE_CLAIM_PATHS)}"
    )
    if console_changed_at > latest:
        evidence.append(
            "the recorded signature date is older than the console change, so the signature "
            "describes a tree that is no longer here. **Walk the screens again and sign with the "
            "date you walked them**, in this report's `Signed:` line. Moving that date without walking "
            "produces a green nobody can "
            "trace to a check, which is the failure this console exists to replace -- and the "
            "gate said the opposite here until CI-W390"
        )
        return Verdict(gate="3", name=name, status=CANNOT_TELL, evidence=evidence)
    return Verdict(gate="3", name=name, status=MET, evidence=evidence)


def _reported_suite(result: str) -> tuple[bool | None, str]:
    """Read a suite verdict CI already produced, rather than producing a second one.

    The nightly's `coverage` job runs the whole suite and gates on it, and on a push `serial`
    does. Running it again here would spend four minutes on a duplicate answer -- the waste B111
    closed when it stopped one pull request running the suite three times -- and two runs that
    disagree leave the report carrying two verdicts about one tree with nothing to choose between.

    `skipped` and `cancelled` are not results. A job that did not run says nothing about the tree,
    and reading either as success would be the same fabrication as an empty table read as zero.
    """
    if result == "success":
        return True, "suite: the job CI already ran reported success"
    if result == "failure":
        return False, "suite: the job CI already ran reported failure"
    return None, f"suite: the job CI ran reported '{result}', which is not a result about the tree"


def gate_four_containment_true(*, run_suite: bool, suite_result: str | None = None) -> Verdict:
    """Gate 4: nothing reaches a pull request unverified and the threat model matches the code.

    Three components. The suite is measured only when asked for, because it costs about four
    minutes and a script nobody runs measures nothing; unasked, that component is `CANNOT TELL`
    rather than an assumption in either direction.
    """
    name = "the containment story is true as written"
    evidence: list[str] = []
    verdicts: list[str] = []

    links_ok, links_note = _dead_links_clean()
    evidence.append(links_note)
    verdicts.append(MET if links_ok is True else (CANNOT_TELL if links_ok is None else NOT_MET))

    wired, wiring_note = _sandbox_wired()
    evidence.append(wiring_note)
    verdicts.append(MET if wired is True else (CANNOT_TELL if wired is None else NOT_MET))

    # In precedence order, and the order is the argument. A verdict CI just produced beats a
    # stored one; running the suite beats reading about it; and reading a stored verdict beats
    # declining to answer, which is what this gate used to do on every invocation while `main` was
    # in fact green.
    if suite_result is not None:
        suite_ok, suite_note = _reported_suite(suite_result)
    elif run_suite:
        suite_ok, suite_note = _suite_green()
    else:
        # `SUITE_RECORD` read here rather than taken as a default argument: a default binds
        # at definition time, so a test pointing the module at another path would be
        # silently ignored and would pass while asserting nothing.
        suite_ok, suite_note = suite_from_record(SUITE_RECORD, head=head_commit())
    evidence.append(suite_note)
    verdicts.append(MET if suite_ok is True else (CANNOT_TELL if suite_ok is None else NOT_MET))

    if NOT_MET in verdicts:
        return Verdict(gate="4", name=name, status=NOT_MET, evidence=evidence)
    if CANNOT_TELL in verdicts:
        return Verdict(gate="4", name=name, status=CANNOT_TELL, evidence=evidence)
    return Verdict(gate="4", name=name, status=MET, evidence=evidence)


def _last_commit_touching(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stamp = (result.stdout or "").strip()
    return stamp or None


def _dead_links_clean() -> tuple[bool | None, str]:
    baseline = REPO_ROOT / "scripts" / "dead_links_baseline.txt"
    try:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "lint_dead_links.py"),
             "src", "--baseline", str(baseline)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"dead-link lint could not run: {exc}"
    if result.returncode == 0:
        return True, "no unbaselined dead links in src/"
    offenders = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return False, "unbaselined dead links: " + "; ".join(offenders[:4])


def _sandbox_wired(baseline_path: Path | None = None) -> tuple[bool | None, str]:
    """Whether anything routes a patch attempt through the container primitives.

    B97's close condition is a patch run that cannot open a socket to a host Sync did not name.
    The mechanism is proven; what has never been true is that anything calls it. This asks the
    question the same way the repository already answers it -- the dead-link baseline accepts
    those symbols as reached from nothing, which is the machine-checkable form of "unwired".

    Matched against actual baseline *entries* (`<path>:<qualname>`, `lint_dead_links.load_baseline`'s
    own format) rather than a substring search over the whole file. A prose comment explaining that
    a symbol stopped violating -- exactly the kind of note this baseline accumulates once something
    is wired -- contains the symbol's bare name too, and a substring match over the whole text read
    that comment as the entry it was retiring. Caught when `ephemeral_container` still read `False`
    here the run after its own baseline entry was deleted, because a neighbouring comment still
    named it.

    `baseline_path` is read inside the function body rather than defaulted at definition time --
    `SUITE_RECORD`'s own comment below gives the reason: a default bound at definition would make
    a test pointing this at another path silently ignored.
    """
    baseline = baseline_path if baseline_path is not None else REPO_ROOT / "scripts" / "dead_links_baseline.txt"
    try:
        from scripts.lint_dead_links import load_baseline
        entries = load_baseline(baseline)
    except OSError as exc:
        return None, f"could not read the dead-link baseline: {exc}"
    unwired = [
        symbol
        for symbol in ("ephemeral_container", "copy_between_containers", "ensure_image_built")
        if any(entry.endswith(f":{symbol}") for entry in entries)
    ]
    if unwired:
        return False, (
            "the sandbox is built and unwired: " + ", ".join(unwired)
            + " are baselined as reached from nowhere, so no patch run is contained (B97)"
        )
    return True, "no sandbox primitive is baselined as unreachable"


SUITE_RECORD = REPO_ROOT / ".cache" / "suite-verdict.json"


def head_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return (result.stdout or "").strip() or None


def record_suite_verdict(
    path: Path, *, commit: str, trustworthy: bool, passed: bool, summary: str
) -> None:
    """Write down what the suite said, when, and about which commit.

    Both halves are required and neither is sufficient. A timestamp with no commit cannot be
    checked against the tree; a commit with no timestamp cannot be aged. Storing one and inferring
    the other is how a record starts describing something nobody meant.
    """
    from datetime import datetime, timezone

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "commit": commit,
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "trustworthy": trustworthy,
                "passed": passed,
                "summary": summary,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def read_suite_record(path: Path = SUITE_RECORD) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def suite_from_record(path: Path = SUITE_RECORD, *, head: str | None = None):
    """A stored suite verdict, used only if it describes the commit in the tree.

    **A green from forty commits ago is not a statement about `main` now.** Gate 3 is currently
    failing on exactly that kind of staleness, and rebuilding it here — reporting a stale record as
    a measurement — would be the gate committing the error it exists to catch. So a record whose
    commit is not `HEAD` is absence, and it names both commits so the reader can decide whether to
    re-run rather than guess what happened.
    """
    record = read_suite_record(path)
    if record is None:
        return None, (
            "main-is-green not measured: run `uv run python scripts/beta_gates.py --run-suite` "
            "once and every later invocation reads the result until the tree moves"
        )
    if head is not None and record.get("commit") != head:
        return None, (
            f"a suite verdict exists but describes {str(record.get('commit'))[:9]}, not the "
            f"current {head[:9]} — measured {record.get('measured_at')}, so it says nothing about "
            "this tree"
        )
    if not record.get("trustworthy"):
        return None, (
            f"the stored run cannot be trusted: {record.get('summary')} "
            f"(measured {record.get('measured_at')})"
        )
    return bool(record.get("passed")), (
        f"suite: {record.get('summary')} at {str(record.get('commit'))[:9]}, "
        f"measured {record.get('measured_at')}"
    )


def worktree_dirty() -> bool:
    """Whether anything is uncommitted, tracked or not.

    A commit names a tree. If the worktree differs from it, the suite measured something no commit
    holds, so a verdict recorded against `HEAD` would claim that commit is green when what passed
    was the commit plus somebody's unsaved work -- and nothing later can tell the two apart.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(result.stdout.strip())


def suite_outcome(
    *, started_at: str | None, finished_at: str | None, dirty: bool,
    returncode: int, trustworthy: bool, summary: str,
) -> tuple[bool | None, str]:
    """Whether this run may be recorded against a commit, and what to say if not.

    Split out from the run itself so the decision can be tested without spending four minutes on
    the suite. The judgement is not "did the tests pass" -- that is `returncode` -- but **"is there
    a commit this result honestly describes"**.

    Two ways there is not, and both were silently ignored before. The tree can move during the run,
    because the suite takes minutes and four lanes land in them; `head_commit()` was read *after*
    the run, so a merge landing meanwhile produced a record naming a commit whose tree nobody
    measured. And the worktree can be dirty, in which case the tested tree is no commit at all.

    Neither refusal is a failing gate. They are `CANNOT_TELL`, which is what this script says
    everywhere else when it could not look.
    """
    if started_at is None or finished_at is None:
        return None, "the suite ran but the commit could not be read, so nothing was recorded"
    if started_at != finished_at:
        return None, (
            f"the tree moved during the run -- started at {started_at[:9]}, finished at "
            f"{finished_at[:9]} -- so this measured a tree that is now no commit's. Nothing was "
            "recorded; re-run on a quiet tree"
        )
    if dirty:
        return None, (
            "the worktree had uncommitted changes, so the suite measured something no commit "
            f"holds and {started_at[:9]} cannot be said to be green. Nothing was recorded; "
            "commit or stash first"
        )
    if not trustworthy:
        return None, f"the suite ran but its verdict cannot be believed: {summary}"
    return returncode == 0, f"suite: {summary}"


def _suite_green() -> tuple[bool | None, str]:
    """Run the suite and judge it with `gate_verdict`, which is the point of that script.

    A tally from a run that died counts absences as failures, so "is main green" cannot be read
    off an exit code alone.
    """
    from scripts.gate_verdict import read_verdict

    log = REPO_ROOT / ".cache" / "beta-gates-suite.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    # Before the run, not after: this is the commit whose tree pytest is about to read.
    started = head_commit()
    try:
        result = subprocess.run(
            # `-n auto`, measured rather than assumed: 125s here and 185s on a Linux runner,
            # both TRUSTWORTHY with no worker lost. `-n 4` was a workaround for starvation on the
            # npx resolve lock, which Lane D fixed in `2cf2e62`, and it now costs 233s for the
            # same tree -- the workaround outliving its cause and charging for it.
            ["uv", "run", "pytest", "tests/", "-q", "-n", "auto"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3600,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"the suite could not be run: {exc}"
    output = (result.stdout or "") + (result.stderr or "")
    log.write_text(output, encoding="utf-8")
    verdict = read_verdict(output)

    ok, detail = suite_outcome(
        started_at=started, finished_at=head_commit(), dirty=worktree_dirty(),
        returncode=result.returncode, trustworthy=verdict.trustworthy,
        summary=verdict.summary or verdict.reason or "no summary line",
    )
    # Recorded only when the result describes a commit. An untrustworthy run is still recorded,
    # because "this commit produced a run that died" is a fact about that commit -- but a run whose
    # commit is unknown has nothing to be a fact about, and writing it against either end would be
    # the record asserting something nobody measured.
    if started is not None and started == head_commit() and not worktree_dirty():
        record_suite_verdict(
            SUITE_RECORD,
            commit=started,
            trustworthy=verdict.trustworthy,
            passed=result.returncode == 0,
            summary=verdict.summary or "no summary line",
        )
    return ok, detail


def render(verdicts: Sequence[Verdict]) -> str:
    lines = ["Beta gates, measured against this repository", ""]
    for verdict in verdicts:
        lines.append(f"Gate {verdict.gate} -- {verdict.name}: {_LABEL[verdict.status]}")
        for item in verdict.evidence:
            lines.append(f"    {item}")
        lines.append("")
    met = sum(1 for v in verdicts if v.status == MET)
    unknown = sum(1 for v in verdicts if v.status == CANNOT_TELL)
    lines.append(f"{met} of {len(verdicts)} met; {unknown} cannot be told from here")
    return "\n".join(lines)


_MARK = {MET: "✅", NOT_MET: "❌", CANNOT_TELL: "❔"}


def render_markdown(verdicts: Sequence[Verdict]) -> str:
    """The same verdicts, for a reader who has not cloned the repository.

    A reader skims glyphs and bold text before words, so `CANNOT TELL` and `NOT MET` are given
    different marks as well as different words. Rendering them alike here would re-introduce the
    absence-versus-zero collapse the script refuses internally, at the one place anybody actually
    looks — which is how a meter starts lying without a single wrong number in it.
    """
    met = sum(1 for v in verdicts if v.status == MET)
    unknown = sum(1 for v in verdicts if v.status == CANNOT_TELL)

    lines = [
        "## Beta gates",
        "",
        f"**{met} of {len(verdicts)} met**, {unknown} cannot be told from this environment.",
        "",
        "This is a readiness report, not a test. It does not fail the build: a gate nobody "
        "promised to have met today going red teaches everyone to ignore CI.",
        "",
    ]
    for verdict in verdicts:
        lines.append(
            f"{_MARK[verdict.status]} **{_LABEL[verdict.status]}** — Gate {verdict.gate}: {verdict.name}"
        )
        lines.append("")
        for item in verdict.evidence:
            lines.append(f"- {item}")
        lines.append("")
    lines.append(
        "❔ means the environment could not answer, not that the answer is zero. A gate that "
        "needs the corpus cannot be measured where there is no corpus."
    )
    corpus_gates = [v.gate for v in verdicts if v.status == CANNOT_TELL and v.gate in ("1", "2")]
    if corpus_gates:
        lines.append("")
        lines.append(
            f"Gate{'s' if len(corpus_gates) > 1 else ''} {', '.join(corpus_gates)} "
            f"cannot be answered anywhere without a corpus, so a `CANNOT TELL` here is structural "
            "rather than news — it will read the same on every run until this is measured somewhere "
            "that has one. To answer it, run `uv run python scripts/beta_gates.py` against a "
            "database with real migration outcomes in it."
        )
    return "\n".join(lines)


def _console_changed_at() -> str | None:
    """When the console last changed in a way that could alter a claim about data.

    A pathspec rather than a directory: `CONSOLE_CLAIM_PATHS` carries git's own `:(exclude)` form
    so a vitest file changing does not re-open a gate about what a screen tells a reader.
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", *CONSOLE_CLAIM_PATHS],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stamp = (result.stdout or "").strip()
    return stamp or None


def measure(*, run_suite: bool, suite_result: str | None = None) -> list[Verdict]:
    store, store_error = _open_store()
    health_reader = _health_reader(store_error)
    resume_built = _resume_path_exists()

    return [
        gate_one_loop_closes(store, resume_built=resume_built),
        gate_two_evidence_exists(store, health_reader=health_reader),
        gate_three_console_truth(
            REPO_ROOT / "docs" / "superpowers" / "reports",
            console_changed_at=_console_changed_at(),
        ),
        gate_four_containment_true(run_suite=run_suite, suite_result=suite_result),
    ]


class _DeadStore:
    """Stands in when the database cannot be opened, so every gate reports the same reason."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def migration_outcomes(self):
        raise self._error


def _open_store():
    try:
        from sync.graph.store import DEFAULT_DSN, GraphStore

        import os

        store = GraphStore(dsn=os.environ.get("SYNC_GRAPH_DSN", DEFAULT_DSN))
        store.migration_outcomes()
        return store, None
    except Exception as exc:  # noqa: BLE001
        return _DeadStore(exc), exc


def _health_reader(store_error: Exception | None):
    if store_error is not None:
        def refuse(_store):
            raise store_error
        return refuse

    from sync.dashboard.fleet import precedent_health

    return precedent_health


def _resume_path_exists() -> bool | None:
    """Gate 1's second half, asked of the code rather than of a run.

    A real answer needs a pull request receiving a review comment and a follow-up commit appearing
    with nobody re-running anything, which this script cannot stage. What it can say is whether the
    path exists at all, and that is reported as what it is rather than as the gate.

    **`None` when a file could not be read, and that is not the same as `False`.** This returned
    `False` on `OSError`, so a file it could not open reported the resume path as *missing* and
    Gate 1 failed with "no resume path, so a review comment leaves the run parked forever" -- a
    specific claim about the code, made on the strength of not having read it. This script already
    makes the opposite argument for the database it cannot reach; the same sentence is true of a
    file it cannot open.
    """
    durable = REPO_ROOT / "src" / "sync" / "remediate" / "durable.py"
    webhook = REPO_ROOT / "src" / "sync" / "forge" / "webhook.py"
    try:
        return (
            "def resume_durable_run" in durable.read_text(encoding="utf-8")
            and "pull_request_review_comment" in webhook.read_text(encoding="utf-8")
        )
    except OSError:
        return None


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--run-suite",
        action="store_true",
        help="measure Gate 4's green-main component by running the suite (~4 minutes)",
    )
    parser.add_argument("--json", action="store_true", help="emit the verdicts as JSON")
    parser.add_argument(
        "--summary",
        metavar="PATH",
        help="also write the report as markdown to PATH (use $GITHUB_STEP_SUMMARY in CI)",
    )
    parser.add_argument(
        "--suite-result",
        metavar="RESULT",
        help=(
            "a suite verdict CI already produced (success|failure|skipped|cancelled), read "
            "instead of running the suite a second time"
        ),
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help=(
            "exit 0 whatever the verdicts are. For CI, where this is a readiness report rather "
            "than a test; a crash still exits non-zero"
        ),
    )
    args = parser.parse_args(list(argv[1:]))

    verdicts = measure(run_suite=args.run_suite, suite_result=args.suite_result)
    if args.json:
        print(json.dumps([v.__dict__ for v in verdicts], indent=2))
    else:
        print(render(verdicts))
    if args.summary:
        Path(args.summary).write_text(render_markdown(verdicts) + "\n", encoding="utf-8")
    if args.exit_zero:
        return 0
    return 0 if all(v.status == MET for v in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
