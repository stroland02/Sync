"""The GitHub-native notification surface: a finding that gets no pull request
gets one open issue on the watched repository, and never two.

The gh subprocess is faked the way `test_github_forge.py` fakes it -- by
replacing the notifier's `_run` -- so nothing here touches git, `gh`, or the
network. The fake keeps the issues it "created" so the idempotency tests
exercise the real sequence: first call creates, second call finds and refuses.
"""

import json
import subprocess

import pytest

from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.forge.notify import (
    NOTIFY_REASONS,
    IssueNotifier,
    IssueOutcome,
    issue_title_for,
    render_issue_body,
)

REPO = RepoRef(repo_id="r1", url="https://github.com/o/r", local_path="/tmp/r", head_sha="0" * 40)
FINDING = Finding(
    detector="vendor_change",
    claim="response-property-removed:/status",
    call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking",
    binding_rung="static",
    rationale="response-property-removed on GetCharges: call site reads `status` (src/billing.ts:6)",
)
SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=2, vendor_id="stripe",
    operation_id="GetCharges", symbol="stripe.charges.retrieve",
    response_fields_read=["status"], sdk_version="14.0.0", content_hash="h",
)
CHANGE = VendorChange(
    vendor_id="stripe", from_version="2024-01-01", to_version="2024-06-01",
    kind="response-property-removed", operation_id="GetCharges",
    path_ptr="/v1/charges", severity="breaking", source="oasdiff",
)


def test_issue_title_is_deterministic_and_carries_vendor_and_operation():
    """The title is the dedup key: an hourly tick re-notifying the same finding
    must compose the identical string, and a human scanning the issue list must
    see which vendor and which operation without opening anything."""
    title = issue_title_for(FINDING, SITE)
    assert title == issue_title_for(FINDING, SITE)
    assert "stripe" in title
    assert "GetCharges" in title
    assert FINDING.claim in title


def test_two_claims_on_one_operation_get_two_titles():
    """`claim` is part of the graph's identity for a finding, so it has to be
    part of the issue's identity too -- otherwise the first claim's issue
    absorbs every later claim against the same operation silently."""
    other = FINDING.model_copy(update={"claim": "request-parameter-removed:/limit"})
    assert issue_title_for(other, SITE) != issue_title_for(FINDING, SITE)


def test_issue_body_states_the_facts_the_console_would():
    body = render_issue_body(FINDING, SITE, CHANGE, REPO, reason="not-mechanically-safe")
    # What changed, with the versions that bound it.
    assert "response-property-removed" in body
    assert "2024-01-01" in body
    assert "2024-06-01" in body
    # Which call sites are affected, as file:line.
    assert "src/billing.ts:6" in body
    # The provenance rung, as the recorded value.
    assert "static" in body
    # What Sync did not do, and why.
    assert "pull request" in body.lower()
    assert NOTIFY_REASONS["not-mechanically-safe"] in body
    # The command that remediates by hand, complete enough to paste.
    assert "sync run" in body
    assert "--vendor stripe" in body
    assert "--from-version 2024-01-01" in body
    assert "--to-version 2024-06-01" in body
    assert f"--repo {REPO.url}" in body


def test_issue_body_without_a_vendor_change_does_not_invent_versions():
    """Two detectors raise findings from telemetry with no vendor change at all.
    Their issue must carry the finding's own rationale and must not render a
    `sync run` command whose required version pair would have to be made up."""
    telemetry_finding = FINDING.model_copy(
        update={"vendor_change_id": None, "binding_rung": "observed",
                "claim": "shape-drift:/data/status",
                "rationale": "observed responses stopped carrying /data/status"}
    )
    body = render_issue_body(telemetry_finding, SITE, None, REPO, reason="policy-notify-only")
    assert "observed responses stopped carrying /data/status" in body
    assert "observed" in body
    assert "--from-version" not in body
    assert "src/billing.ts:6" in body


def test_issue_body_carries_no_composite_score():
    """The console rule binds here exactly as it binds a React component: a
    recorded severity from the closed vocabulary is fine, a scalar is not."""
    body = render_issue_body(FINDING, SITE, CHANGE, REPO, reason="budget-deferred")
    assert "breaking" in body
    for banned in ("confidence", "score", "health"):
        assert banned not in body.lower()


def test_an_unknown_reason_is_refused_at_construction_time():
    """The reason is part of a closed vocabulary because the body renders a
    sentence per member. An unknown member would render an issue that states no
    reason at all, silently, every hour."""
    with pytest.raises(ValueError, match="because-i-said-so"):
        render_issue_body(FINDING, SITE, CHANGE, REPO, reason="because-i-said-so")


def _notifier() -> tuple[IssueNotifier, list[list[str]], list[dict]]:
    """A notifier whose gh keeps state: issues created earlier are found by the
    listing later, which is what the idempotency tests turn on."""
    notifier = IssueNotifier()
    calls: list[list[str]] = []
    open_issues: list[dict] = []

    def fake_run(args):
        calls.append(args)
        if args[1:3] == ["issue", "list"]:
            return json.dumps(open_issues)
        if args[1:3] == ["issue", "create"]:
            title = args[args.index("--title") + 1]
            number = len(open_issues) + 1
            url = f"https://github.com/o/r/issues/{number}"
            open_issues.append({"number": number, "title": title, "url": url})
            return url
        raise AssertionError(f"unexpected gh invocation: {args}")

    notifier._run = fake_run
    return notifier, calls, open_issues


def test_the_first_call_creates_an_issue_on_the_watched_repository():
    notifier, calls, open_issues = _notifier()
    outcome = notifier.notify_finding_issue(REPO, FINDING, SITE, CHANGE, reason="not-mechanically-safe")

    assert outcome.status == "created"
    assert outcome.url == "https://github.com/o/r/issues/1"
    create = next(args for args in calls if args[1:3] == ["issue", "create"])
    # `--repo` explicitly, for the reason `open_pull_request` passes it: on a
    # forked clone gh infers the fork's parent, a repository Sync must not write to.
    assert create[create.index("--repo") + 1] == REPO.url
    assert create[create.index("--title") + 1] == issue_title_for(FINDING, SITE)
    assert create[create.index("--body") + 1] == render_issue_body(
        FINDING, SITE, CHANGE, REPO, reason="not-mechanically-safe"
    )


def test_the_second_call_finds_the_open_issue_and_refuses_to_create_another():
    """The hard requirement. A tick runs hourly; the same finding must not open
    a second issue, and "already open" is a distinct answer rather than a
    silent success."""
    notifier, calls, open_issues = _notifier()
    first = notifier.notify_finding_issue(REPO, FINDING, SITE, CHANGE, reason="not-mechanically-safe")
    second = notifier.notify_finding_issue(REPO, FINDING, SITE, CHANGE, reason="not-mechanically-safe")

    assert first.status == "created"
    assert second.status == "already-open"
    assert second.url == first.url
    assert len(open_issues) == 1
    assert sum(1 for args in calls if args[1:3] == ["issue", "create"]) == 1


def test_a_fuzzy_search_hit_with_a_different_title_does_not_suppress_creation():
    """`gh issue list --search` matches terms, not strings: an issue titled with
    the same vendor and operation but a different claim comes back from the
    search. Only an exact title match is the same finding."""
    notifier, calls, open_issues = _notifier()
    open_issues.append({
        "number": 9,
        "title": issue_title_for(FINDING.model_copy(update={"claim": "loop"}), SITE),
        "url": "https://github.com/o/r/issues/9",
    })

    outcome = notifier.notify_finding_issue(REPO, FINDING, SITE, CHANGE, reason="not-mechanically-safe")
    assert outcome.status == "created"
    assert len(open_issues) == 2


def test_a_gh_failure_is_recorded_with_its_stderr_rather_than_raised():
    notifier = IssueNotifier()

    def failing_run(args):
        raise RuntimeError("gh issue list failed: HTTP 403: rate limit exceeded")

    notifier._run = failing_run
    outcome = notifier.notify_finding_issue(REPO, FINDING, SITE, CHANGE, reason="budget-deferred")
    assert outcome.status == "failed"
    assert "rate limit exceeded" in outcome.detail


def test_notify_findings_returns_one_outcome_per_finding_in_order():
    notifier, calls, open_issues = _notifier()
    other = FINDING.model_copy(update={"claim": "request-parameter-removed:/limit"})
    outcomes = notifier.notify_findings(
        REPO,
        [(FINDING, SITE, CHANGE), (other, SITE, CHANGE), (FINDING, SITE, CHANGE)],
        reason="policy-notify-only",
    )

    assert [outcome.status for outcome in outcomes] == ["created", "created", "already-open"]
    assert outcomes[0].title == issue_title_for(FINDING, SITE)
    assert outcomes[1].title == issue_title_for(other, SITE)
    assert outcomes[2].url == outcomes[0].url


def test_a_duplicate_within_one_batch_is_refused_without_trusting_the_search_index():
    """`gh issue list --search` reads GitHub's search index, which is eventually
    consistent: an issue created seconds ago can be invisible to it. The fake
    here models exactly that -- the listing never reflects anything -- so only
    the wrapper's own memory of what it just created can stop the duplicate."""
    notifier = IssueNotifier()
    creates: list[str] = []

    def lagging_run(args):
        if args[1:3] == ["issue", "list"]:
            return "[]"
        if args[1:3] == ["issue", "create"]:
            creates.append(args[args.index("--title") + 1])
            return f"https://github.com/o/r/issues/{len(creates)}"
        raise AssertionError(f"unexpected gh invocation: {args}")

    notifier._run = lagging_run
    outcomes = notifier.notify_findings(
        REPO, [(FINDING, SITE, CHANGE), (FINDING, SITE, CHANGE)], reason="policy-notify-only"
    )

    assert [outcome.status for outcome in outcomes] == ["created", "already-open"]
    assert outcomes[1].url == outcomes[0].url
    assert len(creates) == 1


def test_notify_findings_never_lets_a_failure_kill_the_tick():
    """gh answering garbage is a subprocess boundary, and the wrapper is the
    tick's protection: one finding's failure is that finding's outcome, not the
    batch's exception. The malformed listing here raises inside `json.loads`,
    which is a different route than a nonzero exit."""
    notifier = IssueNotifier()

    def garbled_run(args):
        return "not json at all"

    notifier._run = garbled_run
    outcomes = notifier.notify_findings(REPO, [(FINDING, SITE, CHANGE)], reason="budget-deferred")
    assert len(outcomes) == 1
    assert outcomes[0].status == "failed"
    assert outcomes[0].detail


def test_the_subprocess_layer_obeys_the_encoding_rules(monkeypatch):
    """The repository's subprocess rules, asserted on the real `_run` rather
    than trusted: text mode decoded as UTF-8, replacement rather than a reader-
    thread crash for diagnostic output, and PYTHONIOENCODING set in the child's
    environment -- overlaid on the inherited one, not replacing it."""
    captured: dict = {}

    def fake_subprocess_run(args, **kwargs):
        captured.update(kwargs)

        class Result:
            returncode = 0
            stdout = "[]"
            stderr = ""

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    monkeypatch.setenv("SYNC_TEST_SENTINEL", "present")

    IssueNotifier()._run(["gh", "issue", "list"])

    assert captured["text"] is True
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
    assert captured["env"]["SYNC_TEST_SENTINEL"] == "present"


def test_outcome_is_a_recorded_value_from_a_closed_vocabulary():
    """The tick stores these outcomes; a status outside the vocabulary would be
    a row nothing downstream can aggregate."""
    assert set(IssueOutcome.__annotations__) >= {"status", "title", "url", "detail"}
