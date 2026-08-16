"""Individual nodes of the remediation graph.

Each node is a plain function of state. Keeping them free of graph wiring makes
them unit-testable and keeps `graph.py` to assembly only.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from sync.core import CallSite, Evidence, Patch, RepoRef, VendorChange
from sync.remediate import corpus
from sync.remediate.state import MAX_CI_ATTEMPTS, MAX_STATIC_ATTEMPTS, RunState
from sync.remediate.tiered import routing_facts
from sync.route.matrix import NO_PATCH, route


@runtime_checkable
class Forge(Protocol):
    def push_branch(self, repo: RepoRef, patch: Patch) -> str: ...
    def await_ci(self, repo: RepoRef, branch: str) -> tuple[bool, str]: ...
    # Returns what it created rather than only where it lives. The number is what the merge
    # webhook joins a delivery to a corpus row by, and it is the forge's to answer: deriving
    # it from the URL here would be a second implementation of knowledge this call already has.
    def open_pull_request(
        self, repo: RepoRef, branch: str, title: str, body: str,
    ) -> Any: ...
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


def _decide_tier(
    change: VendorChange, site: CallSite, catalogue, repo: RepoRef | None = None
) -> tuple[int | None, str | None]:
    """The tier the decision table assigns, and the row that assigned it.

    This is the one place the route is determined and `RunState` is the one place it is
    stored, so the branch out of `prepare` reads a value a node set deliberately. It is
    decided here, at `locate`, because this is where the table's inputs are established.

    `TieredRemediator` asks the table again inside `propose`, and the two cannot disagree
    only while they are given the same inputs: both call `sync.route.matrix.route()` over
    `tiered.routing_facts()`, one pure function. `repo` is one of those inputs. Row 4 turns
    on whether the argument is a literal, which is read off the clone, so omitting `repo`
    here would record the row a run holding no clone would have taken -- an upper bound
    rather than the row that decided, in the column that exists to make "tier 0 was wrong
    for this change kind" a query. Only this call happens before the branch, which is what
    lets a tier -1 finding reach `END` without the patch node running at all.

    `(None, None)` means the table had no jurisdiction, which is not tier -1 and must not be
    treated as one. A deprecation's kind is `deprecation/model-retired`, which no oasdiff
    catalogue carries; routing those to the report node would switch off the one signal that
    costs no tokens.
    """
    if not catalogue:
        return None, None
    rule = catalogue.get(change.kind)
    if rule is None:
        return None, None
    return route(rule, routing_facts(change, site, repo))


def make_locate(store, catalogue=None):
    def locate(state: RunState) -> RunState:
        finding = state["finding"]
        try:
            site = store.get_call_site(finding.call_site_id)
            change = store.get_vendor_change(finding.vendor_change_id)
        except Exception as exc:
            return {"fatal": True, "diagnostics": _describe(exc)}
        tier, row = _decide_tier(change, site, catalogue, state["repo"])
        return {
            "site": site,
            "change": change,
            "tier": tier,
            "routing_row": row,
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
    # Whether this adapter can verify a patch, read once from the adapter rather than per run.
    # An adapter that declares nothing verifies: that leaves every existing one unchanged and
    # needs no widening of `LanguageAdapter`, and it is the safe default, because an adapter
    # wrongly assumed to verify still meets a real gate at `static_verify` while one wrongly
    # assumed not to would silently stop repairing a language Sync can repair.
    gap = str(getattr(adapter, "unverifiable_reason", "") or "")

    def prepare(state: RunState) -> RunState:
        try:
            adapter.prepare(state["repo"])
        except Exception as exc:
            return {"prepare_ok": False, "diagnostics": _describe(exc)}
        return {
            "prepare_ok": True,
            "diagnostics": "",
            "verifiable": not gap,
            "verify_gap": gap,
        }

    return prepare


def route_after_prepare(state: RunState) -> str:
    """A prepare failure is an environment fault -- a broken registry, a
    lockfile out of sync with package.json -- not something a different
    patch could fix. Abandon immediately rather than reaching the patch node
    at all.

    Tier -1 reaches the report node from here, and reading the tier `locate` stored is the
    whole point: catching `NoPatchWarranted` inside `patch` instead would leave `patch` in
    the executed node sequence, which is the outcome the routing-matrix spec's Verification
    section forbids, and would make the corpus record a patch attempt where none was
    warranted.

    An environment fault outranks a routing decision. A run that could not install its
    dependencies has not established anything about the change, and reporting on it would
    claim a verdict Sync did not reach.
    """
    if not state.get("prepare_ok", True):
        return "abandon"
    if state.get("tier") == NO_PATCH:
        return "report"
    # A language whose adapter cannot verify reaches the same node, for a different reason and
    # in second place. Tier -1 is the truer statement where both hold: it says no edit anywhere
    # resolves this change, which outranks Sync being unable to check one here.
    #
    # Reported rather than abandoned, and reported rather than dropped. The finding is real --
    # a Python repository calling a changed vendor operation is a genuine break -- and the only
    # thing Sync cannot do is verify a repair, which is a fact about Sync's coverage and not
    # about the change. Sending it to `patch` would spend the whole static-attempt budget and
    # an agent run per attempt on a verdict knowable before the first token.
    if not state.get("verifiable", True):
        return "report"
    return "patch"


def _attempted_strategy(exc: Exception, remediator) -> str | None:
    """Which tier ran, for an attempt whose remediator raised.

    A cascade attaches it to the exception, because only the cascade knows which of its
    tiers was in hand. A plain remediator answers for itself. `TieredRemediator` itself
    answers `"tiered"`, which is composition rather than a strategy, and `tier_for` drops
    the row instead of recording a label no query could interpret.
    """
    carried = getattr(exc, "tier_strategy", None)
    return carried if carried else getattr(remediator, "strategy", None)


def _close_previous_attempt(state: RunState, record) -> None:
    """Write the row for the attempt this one is replacing.

    An attempt ends at exactly one of four places -- another attempt starting, `abandon`,
    `open_pr` succeeding, or `report` halting a verified patch an assembly with no forge
    cannot push -- and those four are mutually exclusive, which is what makes "one row per
    attempt" hold with no de-duplicating bookkeeping here. The last three are terminal, so
    none can be followed by another attempt, and the first `patch` call has no previous
    attempt to close. `corpus.record` drops a call that describes no attempt.
    """
    if record is not None:
        record(state, terminal_status="retried")


def make_patch(remediator, record=None):
    def patch(state: RunState) -> RunState:
        # This attempt starting is what ends the previous one, so the previous row is
        # written from the state that still describes it, before anything is overwritten.
        _close_previous_attempt(state, record)

        attempts = state.get("static_attempts", 0) + 1
        started = {
            "static_attempts": attempts,
            "attempt_started_at": corpus.now(),
            "attempt_static_passed": None,
            "attempt_ci_result": None,
        }

        try:
            proposed = remediator.propose(
                state["finding"], state["change"], state["site"], state["repo"],
                diagnostics=state.get("feedback", ""),
            )
        except Exception as exc:
            return {
                **started,
                "patch": None,
                "attempt_strategy": _attempted_strategy(exc, remediator),
                "diagnostics": _describe(exc),
                "feedback": _describe(exc),
            }

        if not proposed.diff.strip():
            return {
                **started,
                "patch": None,
                # The remediator returned a `Patch`, so the tier that produced this
                # nothing is known even though the diff is empty.
                "attempt_strategy": proposed.strategy,
                "diagnostics": "the remediator produced no change",
                "feedback": "the remediator produced no change",
            }

        return {
            **started,
            "patch": proposed,
            "attempt_strategy": proposed.strategy,
            "diagnostics": "",
            "feedback": "",
        }

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
            "attempt_static_passed": result.ok,
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
    #
    # Still "push_branch" now that replay sits between the two, because this
    # name is a decision and not a destination: it means the typecheck passed
    # and the run proceeds down the path that ends in a push. `graph.py` maps
    # it to `replay`, and `sync.mcp.propose` reads the same string to decide a
    # patch is verified without ever building a node to push from.
    if state.get("verify_ok"):
        return "push_branch"
    if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
        return "abandon"
    return "patch"


# Replay verdicts that describe the patch. Everything else -- `declined`,
# `not-attempted` -- describes replay, and a fact about replay is not evidence
# about a patch, so it must not spend a retry or block the push.
_REPLAY_FAILURES = frozenset({"threw", "unsatisfied", "timed-out"})


def _replay_feedback(outcome: str, reason: str) -> str:
    """What the next patch attempt is told, naming the stage that rejected it.

    The same problem `_static_feedback` solves: the agent is handed feedback
    from more than one stage and nothing in a bare error message says which.
    A `TypeError` out of a call path reads exactly like one out of anything
    else, and the agent needs to know it came from executing the patched call
    against the new response rather than from a compiler.
    """
    if outcome == "unsatisfied":
        return (
            "The patched call path ran against the new response shape and read fields it no "
            f"longer carries: {reason}"
        )
    if outcome == "timed-out":
        return f"The patched call path did not return when replayed: {reason}"
    return (
        "The patched call path threw when replayed against the new response shape:\n\n"
        f"{reason}"
    )


def _replay_evidence(outcome: str, reason: str, operation_id: str) -> str:
    """The sentence a reviewer reads, which must claim exactly what happened.

    The spec promises "the patched path was executed against the new response shape and
    consumed it cleanly". That is the passing case and it is the ceiling: replay exercises one
    call path against a mock, so it says nothing about whether the application works, and the
    line must not be readable as though it did. A run replay could not execute says so
    outright rather than staying silent, because silence beside three other green gates reads
    as a fourth.
    """
    if outcome == "passed":
        return (
            f"The patched call path was executed against a mocked {operation_id} response "
            "built from the new specification and consumed it cleanly. This exercises that "
            "call path only; it is not a test of the application."
        )
    if outcome in _REPLAY_FAILURES:
        return f"The patched call path failed replay against the new response shape: {reason}"
    return (
        "Not verified by replay: the patched call path was not executed, so nothing here "
        f"says how it behaves against the new response shape ({reason})."
    )


def make_replay(store=None):
    """Execute the patched call path against a mock of the new response.

    Between `tsc` and CI, which is where the spec puts it: stronger than typechecking because
    it exercises runtime behaviour against the new shape, and cheaper and earlier than a CI
    run. It closes the gap that a green CI run proves little when no test covers the patched
    call, which is most customers.

    It runs on nothing the compiler already rejected. `route_after_static` reaches this only
    on a passing typecheck, so a sandboxed process is never spent discovering what `tsc` said
    for free.

    The observed baseline is read here rather than passed in, because `build_graph` already
    holds the store and a second argument would be a second thing a caller can forget. A store
    with no reader for it, or a lookup that raises, leaves the baseline empty -- which is the
    ordinary case anyway, since the shape store cannot be backfilled.
    """
    from sync.verify.replay import replay_from_specification

    def replay(state: RunState) -> RunState:
        site = state["site"]
        plan = state.get("replay_plan") or {}
        if not plan.get("export"):
            return _declined(
                "not-attempted",
                "no replay plan was supplied for this run",
                site.operation_id,
            )

        try:
            result = replay_from_specification(
                state["repo"],
                site,
                plan.get("schema") or {},
                _observed(store, site),
                export=plan["export"],
                vendor_packages=tuple(plan.get("vendor_packages", ())),
                arguments=tuple(plan.get("arguments", ())),
                credential_env=tuple(plan.get("credential_env", ())),
            )
        except Exception as exc:
            # Replay itself broke. That is a fact about the tier and not about the
            # patch, so it declines rather than spending an attempt on a patch no
            # evidence has been gathered against.
            return _declined("declined", _describe(exc), site.operation_id)

        failed = result.outcome in _REPLAY_FAILURES
        return {
            "replay_outcome": result.outcome,
            "replay_reason": result.reason,
            "replay_ok": result.ok,
            "replay_evidence": _replay_evidence(
                result.outcome, result.reason, site.operation_id
            ),
            "replay_shapes": [shape.model_dump(mode="json") for shape in result.shapes],
            # Names the stage, because this becomes `abandon_reason` and a bare
            # `TypeError` there says nothing about which gate rejected the patch --
            # the operator-facing half of what `_replay_feedback` does for the agent.
            "diagnostics": (
                f"replay ({result.outcome}): {result.reason}" if failed else ""
            ),
            "feedback": _replay_feedback(result.outcome, result.reason) if failed else "",
        }

    return replay


def _declined(outcome: str, reason: str, operation_id: str) -> RunState:
    """A run replay could not verify, which is not a run replay passed.

    `diagnostics` and `feedback` stay untouched: they are the routing and retry channel for
    a stage that reached a verdict, and writing a decline into them would hand the next patch
    attempt a note about Sync's own plumbing to act on.
    """
    return {
        "replay_outcome": outcome,
        "replay_reason": reason,
        "replay_ok": False,
        "replay_evidence": _replay_evidence(outcome, reason, operation_id),
        "replay_shapes": [],
    }


def _observed(store, site: CallSite) -> tuple:
    if store is None or not hasattr(store, "observed_shapes"):
        return ()
    try:
        return tuple(store.observed_shapes(site.vendor_id, site.operation_id))
    except Exception:
        # An empty baseline is the ordinary case and the mock falls back to the
        # specification's shape, so a store that cannot answer costs fidelity
        # rather than the run.
        return ()


def route_after_replay(state: RunState) -> str:
    """A replay failure is a verification failure, not an abandonment.

    It means this patch is wrong, which is what the retry loop exists for, so it spends the
    same static-attempt budget a failed typecheck does. The two gates reject for different
    reasons and the budget is one because it bounds patch attempts, not compiler runs.

    Everything replay could not establish routes on to the push path. Replay is an additional
    tier and not a precondition: blocking every finding whose call path replay cannot execute
    would stop the pipeline on the population it was built to serve, and the run already
    carries `replay_outcome` saying it was not verified here.
    """
    if state.get("replay_outcome") in _REPLAY_FAILURES:
        if state.get("static_attempts", 0) >= MAX_STATIC_ATTEMPTS:
            return "abandon"
        return "patch"
    return "push_branch"


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
            "attempt_ci_result": "passed" if green else "failed",
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


def make_open_pr(forge: Forge, record=None):
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
            pull_request = forge.open_pull_request(state["repo"], state["branch"], evidence)
        except Exception as exc:
            # No row here: the attempt has not ended, it has failed on its way out, and
            # `abandon` is the node that closes it.
            return {"fatal": True, "diagnostics": _describe(exc)}

        if record is not None:
            # Passed rather than read off `state`, and that is what holds the grain. This node
            # closes one attempt -- the one that opened the pull request -- and every other
            # `record` call site omits the number, so a retried attempt keeps a null by
            # construction rather than by the order two writes happen to run in. A merge
            # written against every row of a run would inflate the numerator of the axis this
            # whole chain exists to compute, and inflate it silently.
            record(state, terminal_status="opened", pr_number=pull_request.number)

        return {
            "evidence": evidence,
            "pr_url": pull_request.url,
            "pr_number": pull_request.number,
            "outcome": "opened",
            "fatal": False,
        }

    return open_pr


def route_after_open_pr(state: RunState) -> str:
    """`gh pr create` fails on a rate limit, or on a branch that already has an
    open pull request. Reaching `abandon` rather than END is what keeps the
    finding's status honest and leaves `pr_url` unset.
    """
    if state.get("fatal"):
        return "abandon"
    return "end"


def make_report(halt_reason: str | None = None, record=None):
    """Tier -1: the table found no patch is warranted, so the run says so and stops.

    `halt_reason` is supplied only by an assembly that removed the push path, and it is what
    that assembly's runs say instead. A graph built with no forge has no `push_branch` node,
    so the decision that would have pushed arrives here -- and the sentence tier -1 writes
    would be the opposite claim about a patch that verified. Which of the two applies is read
    from `verify_ok`, the boolean `static_verify` set deliberately and the same one
    `route_after_static` routes on: it is true on exactly the runs that reached this node
    carrying a verified patch, and unset on every run that reached it from `prepare`.

    Three things it deliberately does not do, and each has a reason worth keeping.

    It does not write `abandon_reason`. Abandonment means Sync tried and could not finish;
    this means there was correctly nothing to try. That field is where routing learns which
    change kinds are not mechanically safe, and "this kind never needed a patch" written
    there would corrupt the signal it exists to carry.

    It does not touch the finding's status. `FindingStatus` is
    `Literal["open", "patched", "abandoned"]` and none of the three is true here -- the
    finding is real and unremediated, which is what `open` already says. Marking it
    `abandoned` would be the same corruption in the store rather than in the state.

    Reached from `prepare`, it writes no `migration_outcome` row. One row is one repair
    *attempt*, and tier -1 attempted nothing; a row at that grain would be a fabrication, by
    the same rule that already gives a run abandoned before any attempt no row at all. The
    consequence is a real gap rather than a tidy omission: the routing decision reaches
    `RunState` and stops there, so a tier -1 outcome is invisible to any benchmark computed
    off the corpus. Recording it needs a `strategy` value that does not exist --
    `PatchStrategy` is a two-value Literal and the column is `NOT NULL` -- which is a change
    to `sync.core` and `remediate.corpus`, not to this node.

    Reached on the halt branch it owes one, and that is why it holds a recorder. That run
    made an attempt, so this node is where the attempt ends, and a terminal that ends an
    attempt without recording it is a row the corpus can never recover. `"halted"` is its
    own terminal status: not `"abandoned"`, which would put it in `findings_abandoned` and
    claim Sync tried and could not finish, when it finished and had nowhere to deliver.
    """

    def report(state: RunState) -> RunState:
        change = state["change"]
        gap = state.get("verify_gap", "")
        if halt_reason and state.get("verify_ok"):
            if record is not None:
                record(state, terminal_status="halted")
            reason = (
                f"a verified patch for {change.kind} on {change.operation_id} was not "
                f"pushed: {halt_reason}"
            )
        elif gap and state.get("tier") != NO_PATCH:
            # The other reason a run knows not to try. It names the operation, because a
            # report saying only "this language cannot be verified" tells a reader nothing
            # about what is broken -- and the finding is the point.
            reason = (
                f"{change.kind} on {change.operation_id} is not repaired here: {gap}. "
                "The finding stands; the repair does not."
            )
        else:
            row = state.get("routing_row") or "unrouted"
            reason = (
                f"no patch is warranted for {change.kind} on {change.operation_id}: "
                f"routed to tier {NO_PATCH} by row '{row}'"
            )
        return {"outcome": "reported", "report_reason": reason, "pr_url": None}

    return report


def make_abandon(store, forge, record=None):
    def abandon(state: RunState) -> RunState:
        reason = state.get("diagnostics") or "unknown"
        finding_id = state["finding"].id
        if finding_id:
            store.set_finding_status(finding_id, "abandoned")

        # The abandoned attempt is the negative class, and a corpus of successes alone can
        # compute no precision and evaluate no future router. A run that abandoned before
        # any attempt writes nothing, which `corpus.record` decides -- zero attempts is
        # zero rows at this table's grain.
        if record is not None:
            record(state, terminal_status="abandoned", abandon_reason=reason)

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
