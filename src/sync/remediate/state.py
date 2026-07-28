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
    # Two audiences, two keys. `diagnostics` is one line for an operator: it is
    # what `make_abandon` records and what the CLI prints for a run that opened
    # no pull request. `feedback` is what the next patch attempt is told, which
    # for a CI rejection runs to several paragraphs and a diff. Serving both
    # from one key means one of them gets the other's format.
    diagnostics: str
    feedback: str
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
    # The same rule for the nodes whose failures are neither an adapter's nor a
    # remediator's: a store lookup that raised, a rejected push, a CI poll that
    # never produced a verdict, a pull request that could not be opened. One key
    # rather than one per node because the treatment is identical and every
    # writer routes on it immediately, so no two of them are ever in flight at
    # once. `patch` is deliberately not among them -- patch generation can
    # succeed on a second attempt, so it retries rather than setting this.
    fatal: bool
    static_attempts: int
    ci_attempts: int
    # Corpus bookkeeping, at the grain of one `migration_outcome` row per attempt.
    # `static_attempts` is the attempt index: it increments once per `make_patch` call and
    # `route_after_ci` already treats it as the bound on total patch attempts for the whole
    # run. `ci_attempts` counts CI polls, and a run can spend its whole budget without ever
    # reaching CI, so it cannot number attempts.
    #
    # These are cleared when an attempt starts and read when it ends. They are deliberately
    # separate from `verify_ok` and `diagnostics`: those are routing inputs, and a recording
    # concern must not be able to change where the graph goes next.
    attempt_started_at: float
    attempt_strategy: str | None
    attempt_static_passed: bool | None
    attempt_ci_result: str | None
    branch: str
    ci_url: str
    evidence: Evidence
    pr_url: str | None
    outcome: Outcome
    abandon_reason: str
