"""Run the remediation pipeline as far as static verification, and stop there.

`docs/superpowers/specs/2026-07-25-sync-graph-surface-design.md` specifies
`sync_propose_patch` as returning a diff, a verification result and evidence -- and states
that Sync returns patches as data and never writes to the customer's repository. The node
immediately after static verification is `push_branch`. Stopping before it is the whole
contract of this module.

Nothing here reimplements the pipeline. `sync.remediate.nodes` publishes its node factories
and its routers separately, so this composes the shipped ones and follows the shipped routing.
A second copy of that logic would drift from the pipeline it claims to preview, and the preview
being wrong is worse than not having one.

The clearest guarantee that this cannot write is structural rather than asserted: `push_branch`,
`await_ci`, `open_pull_request` and `delete_branch` are all methods on `Forge`, and this driver
never accepts a `Forge`. There is nothing here to call them with.

`abandon` is likewise never reached. Its job is to close a corpus row and delete a branch that
was pushed; no branch is ever pushed here, so there is nothing to clean up, and the reason for
stopping is returned to the caller instead.
"""

from __future__ import annotations

from typing import Any

from sync.core import Finding, RepoRef
from sync.remediate.nodes import (
    make_locate,
    make_patch,
    make_prepare,
    make_static_verify,
    route_after_locate,
    route_after_patch,
    route_after_prepare,
    route_after_static,
)
from sync.remediate.state import RunState

# What the truncated run established. These are not the pipeline's own `Outcome` values --
# a run that stops before pushing has not opened anything and has not abandoned anything, so
# borrowing those words would misreport it.
PROPOSED = "proposed"
UNVERIFIED = "unverified"
BLOCKED = "blocked"
NO_PATCH_WARRANTED = "no_patch_warranted"


def run_to_static_verify(
    finding: Finding,
    repo: RepoRef,
    *,
    store: Any,
    adapter: Any,
    remediator: Any,
    catalogue: Any = None,
) -> RunState:
    """Drive `locate -> prepare -> patch -> static_verify` under the pipeline's own routing.

    The retry loop between `patch` and `static_verify` is the pipeline's, including its
    attempt budget: a failed typecheck feeds its diagnostics back into the next patch, which
    is the only reason a second attempt differs from the first.

    `record` is left at its default on `make_patch`, so no corpus row is written. A preview an
    agent asked for is not a migration attempt, and recording it would put rows in the
    benchmark corpus for runs that never tried to open a pull request.
    """
    locate = make_locate(store, catalogue)
    prepare = make_prepare(adapter)
    patch = make_patch(remediator)
    static_verify = make_static_verify(adapter)

    state: RunState = {"finding": finding, "repo": repo}

    state.update(locate(state))
    if route_after_locate(state) == "abandon":
        return _finish(state, BLOCKED)

    state.update(prepare(state))
    destination = route_after_prepare(state)
    if destination == "abandon":
        return _finish(state, BLOCKED)
    if destination == "report":
        # Tier -1: the routing matrix decided no patch is warranted for this change kind.
        # That is a real finding and an answer, not a failure to produce one.
        return _finish(state, NO_PATCH_WARRANTED)

    while True:
        state.update(patch(state))
        destination = route_after_patch(state)
        if destination == "abandon":
            return _finish(state, UNVERIFIED)
        if destination == "patch":
            continue

        state.update(static_verify(state))
        destination = route_after_static(state)
        if destination == "abandon":
            # `static_fatal` separates a toolchain that could not run from a patch that
            # failed to compile. Only the first is unmeasurable; the second is a verdict.
            return _finish(state, BLOCKED if state.get("static_fatal") else UNVERIFIED)
        if destination == "push_branch":
            return _finish(state, PROPOSED)


def _finish(state: RunState, outcome: str) -> RunState:
    state["outcome"] = outcome
    return state
