"""Writing one `migration_outcome` row per repair attempt.

`bf675b6` built the table, the model and the store methods, and nothing called them. The
corpus cannot be backfilled -- the objects a row reduces from live for the length of one
run -- so every run that finished without writing is a row that can never be recovered.
This is the wiring that stops that.

**The grain is one attempt, not one finding.** A finding retried three times writes three
rows and `attempt_index` says which is which. `static_attempts` carries it: it increments
once per `make_patch` call, and `route_after_ci` already treats it as the bound on total
patch attempts for the whole run. `ci_attempts` counts CI polls, and a run can spend its
whole budget without ever reaching CI.

**A recording failure never fails a run.** Losing one row is bad; losing the pull request
because bookkeeping failed is worse. Every path out of `record` is caught and logged, and
the caller gets no exception and no way to accidentally depend on one.

**Three cases deliberately write nothing**, and each is a case where a row would be a
fabrication rather than a measurement:

- A run abandoned before any attempt -- at `locate` or `prepare`. Zero attempts is zero
  rows. The finding's status and `abandon_reason` already record that it was abandoned,
  and conflating "abandoned before attempting" with "attempted and failed" makes every
  rate computed off this table wrong.
- No tier applying at all. `strategy` is `NOT NULL` and the column is what the corpus
  splits merge rate by, so an attempt with no strategy to name is not a row -- and "no
  tier ran" is a different fact from "the agent tier ran and failed", which
  `tiered.TierFailed` keeps separate.
- No configured salt. See `corpus_salt`.
"""

from __future__ import annotations

import logging
import os
import re
import time

from sync.core import MigrationOutcome, Patch
from sync.route import AGENT, CODEMOD

log = logging.getLogger(__name__)

SALT_VARIABLE = "SYNC_CORPUS_SALT"

# `PatchStrategy` is a two-value Literal in `sync.core`, and `tier` is the axis the corpus
# index is built on. Deriving one from the other is not a guess: which tier ran *is* which
# remediator produced the patch. `sync.route.matrix.route()` decides the tier a finding
# should take, which is a different question and is not wired into this pipeline.
_TIERS = {"codemod": CODEMOD, "agent": AGENT}

# tsc writes `error TS2339: ...`. The code alone classifies the failure without carrying a
# message that quotes the customer's own identifiers.
_TS_ERROR = re.compile(r"\bTS(\d+)\b")


class MissingCorpusSalt(RuntimeError):
    """Raised when `SYNC_CORPUS_SALT` is unset at the point a row would be built."""


def now() -> float:
    """Epoch seconds, as one seam so a test can control the clock.

    Wall clock rather than `time.monotonic()`: an attempt survives a worker restart --
    that is what the checkpointer exists for -- and a monotonic reading taken in one
    process cannot be subtracted from one taken in another. A resumed attempt's `wall_ms`
    therefore includes the outage, which is honest: the attempt genuinely was in flight,
    and the multi-minute CI wait it was parked in is the dominant term either way.
    """
    return time.time()


def corpus_salt() -> str:
    """The per-deployment salt for `hash_arg_keys`, or a failure that says what to set.

    There is deliberately no fallback. This project is open core, so a constant in the
    source is a published constant, and a digest salted with a published constant is
    reversible by anyone who can read the repository -- `hash_arg_keys` exists precisely
    because an unsalted digest of `amount` is `amount` to anyone willing to hash a
    wordlist. A default here would be a privacy hole with a comment beside it explaining
    why it was fine.

    A caller that has a human present should invoke this at configuration load, where the
    message can be acted on. `record_attempt` calls it far from one, so there it omits the
    row and logs: a missing row is recoverable, a reversible hash published in a public
    repository is not.
    """
    salt = os.environ.get(SALT_VARIABLE)
    if not salt:
        raise MissingCorpusSalt(
            f"{SALT_VARIABLE} is not set, so argument keys cannot be salted; set it to a "
            f"stable per-deployment secret (a random one per run would make rows from "
            f"different runs incomparable)"
        )
    return salt


def tier_for(strategy: str | None) -> int | None:
    """The tier a strategy belongs to, or `None` for a strategy the corpus cannot place.

    `TieredRemediator.strategy` is `"tiered"`, which is composition over the protocol
    rather than a strategy anyone chose. It answers `None` and the row is omitted, because
    stamping it would put a label in the column the corpus splits on that no query could
    interpret.
    """
    if strategy is None:
        return None
    return _TIERS.get(strategy)


def static_error_class(diagnostics: str | None) -> str | None:
    """The tsc error code a failed verification reported, if it named one."""
    if not diagnostics:
        return None
    found = _TS_ERROR.search(diagnostics)
    return f"TS{found.group(1)}" if found else None


def make_recorder(store):
    """A `record(state, terminal_status, ...)` bound to one store.

    Built in `build_graph` from the store it already receives, so no caller has to learn a
    new argument and no run can be configured with the recording silently absent.
    """

    def record(state, *, terminal_status: str, abandon_reason: str | None = None) -> bool:
        try:
            return _record(store, state, terminal_status, abandon_reason)
        except Exception:
            # Never propagates. The pull request is the product; the row is bookkeeping,
            # and bookkeeping that can fail a run is worse than bookkeeping that is missing.
            log.warning(
                "could not record a migration_outcome row for finding %s attempt %s",
                getattr(state.get("finding"), "id", None),
                state.get("static_attempts"),
                exc_info=True,
            )
            return False

    return record


def _record(store, state, terminal_status: str, abandon_reason: str | None) -> bool:
    write = getattr(store, "record_migration_outcome", None)
    if write is None:
        log.warning("store has no record_migration_outcome; migration_outcome row omitted")
        return False

    finding = state.get("finding")
    site = state.get("site")
    change = state.get("change")
    attempt_index = state.get("static_attempts", 0)
    if finding is None or finding.id is None or site is None or change is None:
        return False
    if attempt_index < 1:
        # Abandoned at `locate` or `prepare`: no attempt was made, so there is nothing at
        # this table's grain to describe. Said separately from "no tier applied" below,
        # because an operator reading logs needs to tell a run that never tried from one
        # that tried and found no tier -- and at debug, since a prepare failure is an
        # ordinary outcome rather than a recording fault.
        log.debug(
            "finding %s abandoned before any attempt, so migration_outcome has no row to "
            "write for it", finding.id,
        )
        return False

    strategy = state.get("attempt_strategy")
    tier = tier_for(strategy)
    if tier is None:
        log.warning(
            "no tier ran for finding %s attempt %s, so migration_outcome has no strategy "
            "to record and the row is omitted",
            finding.id, attempt_index,
        )
        return False

    try:
        salt = corpus_salt()
    except MissingCorpusSalt as exc:
        log.warning("migration_outcome row omitted: %s", exc)
        return False

    started = state.get("attempt_started_at")
    wall_ms = max(0, round((now() - started) * 1000)) if started else 0

    static_passed = state.get("attempt_static_passed")
    write(
        MigrationOutcome.from_attempt(
            finding_id=finding.id,
            attempt_index=attempt_index,
            site=site,
            change=change,
            # Only `strategy` is read off the patch, and an attempt that produced no patch
            # still ran a tier that owns one. The diff is never stored, so a stand-in here
            # cannot leak anything a real patch would not.
            patch=Patch(diff="", strategy=strategy, rationale=""),
            tier=tier,
            wall_ms=wall_ms,
            salt=salt,
            static_verify_passed=static_passed,
            static_verify_error_class=(
                static_error_class(state.get("diagnostics")) if static_passed is False else None
            ),
            ci_result=state.get("attempt_ci_result"),
            terminal_status=terminal_status,
            abandon_reason=abandon_reason,
        )
    )
    return True
