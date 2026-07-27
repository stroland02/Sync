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
    # Routing after static_verify trusts this, not whether diagnostics is
    # non-empty: a real tsc failure can exit non-zero with nothing on either
    # stream (e.g. a silent npx fetch failure), which would otherwise read as
    # success.
    verify_ok: bool
    # Set only when prepare or static_verify raises rather than returning a
    # normal result -- an environment fault (broken registry, lockfile out of
    # sync with package.json), not something a different patch could fix.
    # Routes straight to abandon, bypassing the static-attempt retry budget.
    prepare_ok: bool
    static_fatal: bool
    static_attempts: int
    ci_attempts: int
    branch: str
    ci_url: str
    evidence: Evidence
    pr_url: str | None
    outcome: Outcome
    abandon_reason: str
