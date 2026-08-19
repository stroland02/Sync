"""GitHub-native notification for findings that get no pull request.

The owner's ruling (`docs/superpowers/plans/2026-08-18-continuous-watch-loop.md`,
ledger, decision 4): the verified pull request is itself the notification for a
remediated change, and a finding Sync deliberately did not remediate opens one
issue on the watched repository -- B94's first human-surface delivery
destination.

Idempotency is the requirement the shape of this module serves. A tick runs
hourly, so the same finding arrives here every hour until somebody acts on it,
and the issue's title is the identity that stops the second arrival opening a
second issue: deterministic over the finding's claim, the call site's vendor
and operation, and nothing else. `gh issue list --search` narrows the
candidates; the exact-title comparison below is the authority, because GitHub's
search matches terms rather than strings.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Literal, Sequence

from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.forge.github import _gh

# Why Sync opened no pull request. Closed, because the issue body renders one
# sentence per member and the tick records the reason it acted under: free text
# could not be aggregated, and an unknown member would render an issue stating
# no reason at all. The values are Sync's own routing outcomes, not anybody
# else's vocabulary.
NOTIFY_REASONS: dict[str, str] = {
    "policy-notify-only": (
        "This repository's policy routes this change to notification rather than "
        "to an automated pull request."
    ),
    "not-mechanically-safe": (
        "Routing judged this change kind not mechanically safe to patch without "
        "a human deciding what the code should now mean."
    ),
    "budget-deferred": (
        "The tick's budget ceiling deferred remediation; the finding stays "
        "queued for a later tick."
    ),
}

# What each rung means, said once here so every issue states it the same way.
# The vocabulary is `sync.core.models.FindingRung`; a member missing from this
# map renders as its bare value rather than failing, because the recorded value
# is the fact and the sentence is only its gloss.
_RUNG_STATEMENTS: dict[str, str] = {
    "static": "read out of the source",
    "resolved": "read out of the source, plus a resolution step",
    "observed": "correlated from watched traffic",
    "unresolved": "an observation nothing correlated to a binding",
    "unattributed": "recorded before rung attribution existed",
}

IssueStatus = Literal["created", "already-open", "failed"]


@dataclass(frozen=True)
class IssueOutcome:
    """What notifying one finding produced.

    `already-open` is a distinct answer rather than a silent success: the tick
    that reads these decides nothing on it today, but an outcome that folded
    "notified an hour ago" into "notified just now" could never say how long a
    finding has been waiting on a human. `url` is None exactly when `status`
    is `failed`; `detail` carries the stderr or the exception text there, and
    a short human sentence otherwise.
    """

    status: IssueStatus
    title: str
    url: str | None
    detail: str


def issue_title_for(finding: Finding, site: CallSite) -> str:
    """The issue's identity, so it is deterministic or it is nothing.

    Built from the claim, the operation and the vendor -- the stable parts of
    the finding's own graph identity -- and never from the rationale or the
    line number, both of which move between indexes of an unchanged problem
    and would open a fresh issue per movement.
    """
    return f"Sync: {finding.claim} on {site.operation_id} ({site.vendor_id})"


def render_issue_body(
    finding: Finding,
    site: CallSite,
    change: VendorChange | None,
    repo: RepoRef,
    reason: str,
) -> str:
    """The finding stated the way the console states facts.

    What changed, which call sites are affected, which rung the claim rests
    on, what Sync did not do and why, and the command that remediates by hand.
    No composite score and no colour language; the severity is the recorded
    value from the closed vocabulary and nothing is derived from it here.
    """
    if reason not in NOTIFY_REASONS:
        raise ValueError(
            f"unknown notify reason {reason!r}; members are {sorted(NOTIFY_REASONS)}"
        )

    if change is not None:
        changed = (
            f"`{change.kind}` on `{change.operation_id}` ({change.vendor_id}), "
            f"{change.from_version} to {change.to_version}. Severity: {change.severity}."
        )
    else:
        changed = (
            f"Detected by `{finding.detector}` from observed behaviour rather than "
            f"a spec diff. Severity: {finding.severity}."
        )

    rung = finding.binding_rung
    rung_statement = _RUNG_STATEMENTS.get(rung, rung)

    if change is not None:
        remediate = (
            "```\n"
            f"sync run --vendor {change.vendor_id} "
            f"--from-version {change.from_version} --to-version {change.to_version} "
            f"--repo {repo.url}\n"
            "```"
        )
    else:
        remediate = (
            "This finding carries no vendor version pair to re-run, so there is no "
            "`sync run` invocation to paste; the call sites above are where the "
            "change belongs."
        )

    sites = "\n".join(f"- `{site.path}:{site.line}`" for site in [site])

    return f"""## What changed

{changed}

{finding.rationale}

## Affected call sites

{sites}

## Provenance

This claim rests on a `{rung}` binding: {rung_statement}.

## What Sync did not do

Sync opened no pull request for this finding. {NOTIFY_REASONS[reason]}

## Remediate by hand

{remediate}

---

Opened by **Sync**. This issue is the notification for a finding Sync
deliberately did not remediate; a verified pull request would have been the
notification otherwise.
"""


class IssueNotifier:
    """Opens at most one issue per finding on the watched repository, via the
    same authenticated `gh` the rest of the forge shells to."""

    def _run(self, args: list[str]) -> str:
        # No cwd, unlike `GitHubForge._run`: every invocation names its
        # repository with `--repo`, and a notification must not depend on a
        # clone existing on disk -- the telemetry detection pass raises
        # findings in ticks that never cloned anything.
        #
        # `errors="replace"` for the reason github.py gives: nothing
        # load-bearing here can be corrupted by a replacement character (URLs
        # and gh's JSON field names are ASCII), and what it buys is a gh error
        # message reaching the RuntimeError below instead of dying on the
        # reader thread. PYTHONIOENCODING travels with the child in case the
        # child is Python underneath; it says which bytes arrive, where
        # `encoding=` only says how to decode them.
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        if result.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def notify_finding_issue(
        self,
        repo: RepoRef,
        finding: Finding,
        site: CallSite,
        change: VendorChange | None,
        reason: str,
    ) -> IssueOutcome:
        """One issue for one finding, or the fact that it already has one.

        The listing is consulted before every create because the title is the
        only identity shared between ticks -- nothing else about a previous
        tick survives into this one. The search narrows; the exact comparison
        decides.

        Nothing raises out of here for a gh fault, deliberately and with the
        same argument `delete_branch` makes: notification runs inside a tick
        whose useful signal is its findings, and an exception here would
        replace all of them with itself. The one exception is an unknown
        `reason`, which is a defect in the caller rather than weather, and is
        refused before any subprocess runs.
        """
        title = issue_title_for(finding, site)
        body = render_issue_body(finding, site, change, repo, reason=reason)
        try:
            listing = json.loads(self._run(
                [_gh(), "issue", "list",
                 "--repo", repo.url,
                 "--state", "open",
                 "--search", f'"{title}" in:title',
                 "--json", "number,title,url",
                 "--limit", "50"],
            ))
            existing = next(
                (issue for issue in listing if issue.get("title") == title), None
            )
            if existing is not None:
                return IssueOutcome(
                    status="already-open",
                    title=title,
                    url=existing.get("url"),
                    detail=f"already open as #{existing.get('number')}",
                )

            url = self._run(
                [_gh(), "issue", "create",
                 "--repo", repo.url,
                 "--title", title,
                 "--body", body],
            )
        except Exception as exc:
            return IssueOutcome(status="failed", title=title, url=None, detail=str(exc))
        return IssueOutcome(status="created", title=title, url=url, detail=f"created {url}")

    def notify_findings(
        self,
        repo: RepoRef,
        findings: Sequence[tuple[Finding, CallSite, VendorChange | None]],
        reason: str,
    ) -> list[IssueOutcome]:
        """The batch form the watch tick injects: one outcome per finding, in
        order, and never an exception -- a failed notification is that
        finding's outcome, not the tick's.

        The wrapper remembers what it created within this batch rather than
        asking GitHub again, because the listing behind `notify_finding_issue`
        reads GitHub's search index and that index is eventually consistent:
        an issue created seconds ago can be invisible to it, and two findings
        in one batch that share a title would both create. Across ticks the
        index has an hour to catch up; within one batch it gets no time at
        all, so the batch cannot rely on it.
        """
        settled: dict[str, IssueOutcome] = {}
        outcomes: list[IssueOutcome] = []
        for finding, site, change in findings:
            title = issue_title_for(finding, site)
            earlier = settled.get(title)
            if earlier is not None:
                outcomes.append(IssueOutcome(
                    status="already-open",
                    title=title,
                    url=earlier.url,
                    detail="already opened earlier in this batch",
                ))
                continue
            outcome = self.notify_finding_issue(repo, finding, site, change, reason=reason)
            if outcome.status != "failed":
                settled[title] = outcome
            outcomes.append(outcome)
        return outcomes
