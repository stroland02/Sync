"""Individual nodes of the remediation graph.

Each node is a plain function of state. Keeping them free of graph wiring makes
them unit-testable and keeps `graph.py` to assembly only.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sync.core import Evidence, Patch, RepoRef
from sync.remediate.state import MAX_CI_ATTEMPTS, MAX_STATIC_ATTEMPTS, RunState


@runtime_checkable
class Forge(Protocol):
    def push_branch(self, repo: RepoRef, patch: Patch) -> str: ...
    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]: ...
    def open_pull_request(self, repo: RepoRef, branch: str, evidence: Evidence) -> str: ...
    def delete_branch(self, repo: RepoRef, branch: str) -> tuple[bool, str]: ...


def _describe(exc: Exception) -> str:
    """str(KeyError("apiKey")) is "'apiKey'" and str(TimeoutError()) is "" -- the
    class name is sometimes the only part of an exception that says what failed,
    and this text is the whole of what an operator sees in the abandon record.
    """
    return f"{type(exc).__name__}: {exc}"


def _static_feedback(diagnostics: str) -> str:
    """The patch agent is handed feedback from more than one stage with nothing
    in the value itself to tell them apart. Bare tsc output does not name the
    stage that emitted it.
    """
    if not diagnostics:
        return "`tsc --noEmit` rejected the previous attempt without writing to either stream."
    return f"`tsc --noEmit` rejected the previous attempt:\n\n{diagnostics}"


def _ci_feedback(url: str, branch: str, patch: Patch | None) -> str:
    """The run URL is all the operator's abandon record needs; the patch agent
    has WebFetch and WebSearch in its DISALLOWED_TOOLS and cannot read it. The
    diff is the part it can act on, and it cannot recover that from the clone
    either: `push_branch` has already committed it, so `git diff` there is empty.
    """
    return "\n".join([
        f"The previous attempt passed typechecking and was still rejected by the repository's "
        f"own CI, on branch {branch}. The failing run is at {url}, which is there for a human "
        f"reviewer: the tools that read a URL are disabled, so do not spend turns on it.",
        "",
        "Because typechecking already passed, what CI caught is something a typechecker "
        "cannot see: a test asserting the old response shape, a lint rule, or a change in "
        "behaviour at runtime. Read the tests covering the call site before editing.",
        "",
        "This is the diff CI rejected. It is already committed in the clone, so making the "
        "same edit again changes nothing:",
        "",
        patch.diff if patch is not None else "",
    ])


def make_locate(store):
    def locate(state: RunState) -> RunState:
        finding = state["finding"]
        try:
            site = store.get_call_site(finding.call_site_id)
            change = store.get_vendor_change(finding.vendor_change_id)
        except Exception as exc:
            return {"fatal": True, "diagnostics": _describe(exc)}
        return {
            "site": site,
            "change": change,
            "static_attempts": 0,
            "ci_attempts": 0,
            "diagnostics": "",
            "feedback": "",
            "outcome": "running",
            "fatal": False,
        }

    return locate


def route_after_locate(state: RunState) -> str:
    """`Finding.vendor_change_id` is optional, so `get_vendor_change(None)`
    raises for any detector that does not join against a vendor change.
    """
    if state.get("fatal"):
        return "abandon"
    return "prepare"


def make_prepare(adapter):
    def prepare(state: RunState) -> RunState:
        try:
            adapter.prepare(state["repo"])
        except Exception as exc:
            return {"prepare_ok": False, "diagnostics": _describe(exc)}
        return {"prepare_ok": True, "diagnostics": ""}

    return prepare


def route_after_prepare(state: RunState) -> str:
    """A prepare failure is an environment fault -- a broken registry, a
    lockfile out of sync with package.json -- not something a different
    patch could fix. Abandon immediately rather than reaching the patch node
    at all.
    """
    if state.get("prepare_ok", True):
        return "patch"
    return "abandon"


def make_patch(remediator):
    def patch(state: RunState) -> RunState:
        attempts = state.get("static_attempts", 0) + 1
        try:
            proposed = remediator.propose(
                state["finding"], state["change"], state["site"], state["repo"],
                diagnostics=state.get("feedback", ""),
            )
        except Exception as exc:
            return {
                "patch": None,
                "static_attempts": attempts,
                "diagnostics": _describe(exc),
                "feedback": _describe(exc),
            }

        if not proposed.diff.strip():
            return {
                "patch": None,
                "static_attempts": attempts,
                "diagnostics": "the remediator produced no change",
                "feedback": "the remediator produced no change",
            }

        return {"patch": proposed, "static_attempts": attempts, "diagnostics": "", "feedback": ""}

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
        try:
            result = adapter.static_verify(state["repo"], state["patch"])
        except Exception as exc:
            return {
                "static_fatal": True,
                "verify_ok": False,
                "diagnostics": _describe(exc),
            }
        return {
            "diagnostics": result.diagnostics,
            "feedback": "" if result.ok else _static_feedback(result.diagnostics),
            "verify_ok": result.ok,
            "static_fatal": False,
        }

    return static_verify


def route_after_static(state: RunState) -> str:
    # An exception out of static_verify means verification could not be
    # performed at all -- an environment fault, not a patch that failed
    # typechecking. Abandon on the first occurrence rather than spending the
    # remaining static-attempt budget retrying against the same fault.
    if state.get("static_fatal"):
        return "abandon"
    # `ok`, not whether diagnostics happens to be non-empty: a real tsc
    # failure can exit non-zero with nothing on either stream.
    if state.get("verify_ok"):
        return "push_branch"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


def make_push_branch(forge: Forge):
    def push_branch(state: RunState) -> RunState:
        try:
            branch = forge.push_branch(state["repo"], state["patch"])
        except Exception as exc:
            return {"fatal": True, "diagnostics": _describe(exc)}
        return {"branch": branch, "fatal": False}

    return push_branch


def route_after_push(state: RunState) -> str:
    """A protected branch, an expired token, a rejected non-fast-forward: none
    of them is a patch that a further attempt could improve on.
    """
    if state.get("fatal"):
        return "abandon"
    return "await_ci"


def make_await_ci(forge: Forge):
    def await_ci(state: RunState) -> RunState:
        try:
            green, url = forge.await_ci(state["repo"], state["branch"])
        except Exception as exc:
            return {"fatal": True, "diagnostics": _describe(exc)}
        return {
            "ci_url": url,
            "ci_attempts": state.get("ci_attempts", 0) + 1,
            "diagnostics": "" if green else f"CI failed: {url}",
            "feedback": "" if green else _ci_feedback(url, state["branch"], state.get("patch")),
            "fatal": False,
        }

    return await_ci


def route_after_ci(state: RunState) -> str:
    # A red verdict is a patch that failed and retries; a poll that raised
    # produced no verdict at all, so the patch is not what there is to fix.
    if state.get("fatal"):
        return "abandon"
    if not state.get("diagnostics"):
        return "open_pr"
    if state.get("ci_attempts", 0) >= MAX_CI_ATTEMPTS:
        return "abandon"
    # static_attempts bounds total patch attempts for the whole run, not just
    # attempts since the last push: a red CI run must not spend one more of
    # them once that budget is already gone.
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
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
        try:
            url = forge.open_pull_request(state["repo"], state["branch"], evidence)
        except Exception as exc:
            return {"fatal": True, "diagnostics": _describe(exc)}
        return {"evidence": evidence, "pr_url": url, "outcome": "opened", "fatal": False}

    return open_pr


def route_after_open_pr(state: RunState) -> str:
    """`gh pr create` fails on a rate limit, or on a branch that already has an
    open pull request. Reaching `abandon` rather than END is what keeps the
    finding's status honest and leaves `pr_url` unset.
    """
    if state.get("fatal"):
        return "abandon"
    return "end"


def make_abandon(store, forge):
    def abandon(state: RunState) -> RunState:
        reason = state.get("diagnostics") or "unknown"
        finding_id = state["finding"].id
        if finding_id:
            store.set_finding_status(finding_id, "abandoned")

        # `branch` is set only by a push that succeeded, which is the one signal the
        # forge cannot derive for itself: it cannot tell a finding that abandoned
        # after pushing from one whose pull request has not been opened yet.
        branch = state.get("branch")
        if branch:
            try:
                forge.delete_branch(state["repo"], branch)
            except Exception:
                # The finding has already failed and `reason` is what the operator
                # needs. A cleanup that failed on top of it must not displace that.
                pass

        return {"outcome": "abandoned", "abandon_reason": reason, "pr_url": None}

    return abandon
