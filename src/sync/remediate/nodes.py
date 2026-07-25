"""Individual nodes of the remediation graph.

Each node is a plain function of state. Keeping them free of graph wiring makes
them unit-testable and keeps `graph.py` to assembly only.
"""

from __future__ import annotations

from typing import Protocol

from sync.core import Evidence, Patch, RepoRef
from sync.remediate.state import MAX_CI_ATTEMPTS, MAX_STATIC_ATTEMPTS, RunState


class Forge(Protocol):
    def push_branch(self, repo: RepoRef, patch: Patch) -> str: ...
    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]: ...
    def open_pull_request(self, repo: RepoRef, branch: str, evidence: Evidence) -> str: ...


def make_locate(store):
    def locate(state: RunState) -> RunState:
        finding = state["finding"]
        return {
            "site": store.get_call_site(finding.call_site_id),
            "change": store.get_vendor_change(finding.vendor_change_id),
            "static_attempts": 0,
            "ci_attempts": 0,
            "diagnostics": "",
            "outcome": "running",
        }

    return locate


def make_patch(remediator):
    def patch(state: RunState) -> RunState:
        attempts = state.get("static_attempts", 0) + 1
        try:
            proposed = remediator.propose(
                state["finding"], state["change"], state["site"], state["repo"],
                diagnostics=state.get("diagnostics", ""),
            )
        except Exception as exc:
            return {"patch": None, "static_attempts": attempts, "diagnostics": str(exc)}

        if not proposed.diff.strip():
            return {
                "patch": None,
                "static_attempts": attempts,
                "diagnostics": "the remediator produced no change",
            }

        return {"patch": proposed, "static_attempts": attempts, "diagnostics": ""}

    return patch


def route_after_patch(state: RunState) -> str:
    """A run that failed and a run that changed nothing leave the same empty diff.

    Neither may reach `push_branch`: a no-op branch passes CI and would open a
    pull request that claims to fix something and does not.
    """
    if state.get("patch") is not None:
        return "static_verify"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


def make_static_verify(adapter):
    def static_verify(state: RunState) -> RunState:
        result = adapter.static_verify(state["repo"], state["patch"])
        return {"diagnostics": result.diagnostics if not result.ok else ""}

    return static_verify


def route_after_static(state: RunState) -> str:
    if not state.get("diagnostics"):
        return "push_branch"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


def make_push_branch(forge: Forge):
    def push_branch(state: RunState) -> RunState:
        return {"branch": forge.push_branch(state["repo"], state["patch"])}

    return push_branch


def make_await_ci(forge: Forge):
    def await_ci(state: RunState) -> RunState:
        green, url = forge.await_ci(state["repo"], state["branch"])
        return {
            "ci_url": url,
            "ci_attempts": state.get("ci_attempts", 0) + 1,
            "diagnostics": "" if green else f"CI failed: {url}",
        }

    return await_ci


def route_after_ci(state: RunState) -> str:
    if not state.get("diagnostics"):
        return "open_pr"
    if state.get("ci_attempts", 0) >= MAX_CI_ATTEMPTS:
        return "abandon"
    return "patch"


def make_open_pr(forge: Forge):
    def open_pr(state: RunState) -> RunState:
        change = state["change"]
        site = state["site"]
        evidence = Evidence(
            spec_diff=change.raw,
            changelog_entry=state["finding"].rationale,
            call_sites=[f"{site.path}:{site.line}"],
            ci_run_url=state.get("ci_url", ""),
        )
        url = forge.open_pull_request(state["repo"], state["branch"], evidence)
        return {"evidence": evidence, "pr_url": url, "outcome": "opened"}

    return open_pr


def make_abandon(store):
    def abandon(state: RunState) -> RunState:
        reason = state.get("diagnostics") or "unknown"
        finding_id = state["finding"].id
        if finding_id:
            store.set_finding_status(finding_id, "abandoned")
        return {"outcome": "abandoned", "abandon_reason": reason, "pr_url": None}

    return abandon
