"""State carried through the remediation graph and checkpointed at every node."""

from __future__ import annotations

from typing import Literal, TypedDict

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange

Outcome = Literal["running", "opened", "abandoned"]

MAX_STATIC_ATTEMPTS = 3
MAX_CI_ATTEMPTS = 2


class RunState(TypedDict, total=False):
    finding: Finding
    repo: RepoRef
    site: CallSite
    change: VendorChange
    # None means the patch node produced nothing usable -- either the remediator
    # raised, or it returned an empty diff. Both must reach `abandon`, never `push_branch`.
    patch: Patch | None
    diagnostics: str
    static_attempts: int
    ci_attempts: int
    branch: str
    ci_url: str
    evidence: Evidence
    pr_url: str | None
    outcome: Outcome
    abandon_reason: str
