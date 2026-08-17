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

**The store's contract is checked once, at construction.** That swallowing is why. A store
missing the write used to be a soft `getattr` and a warning, which is the one failure this
module cannot survive: the write is the single call the whole benchmark depends on, and a
warning about it scrolls past in a log nobody reads while every axis keeps reporting null with
a sample size of zero. Null-because-nothing-ran then reads exactly like
null-because-the-writer-vanished.

Raising from `record` would not fix it, because `record` is where the swallowing lives -- the
exception would be caught by the same handler that exists to protect the run, logged, and lost.
And moving the check to the write is the one place it must not be: three of the four call sites
are inside terminal nodes, and one of those runs *after* `forge.open_pull_request` has already
opened a pull request. So the contract is stated at `make_recorder`, which `build_graph` calls
before any node runs. A store that cannot record fails while there is still no run to lose.

**Two cases deliberately write nothing**, and both are cases where a row would be a
fabrication rather than a measurement. Neither is a schema problem; both are the grain:

- A run abandoned before any attempt -- at `locate` or `prepare`. Zero attempts is zero
  rows. The finding's status and `abandon_reason` already record that it was abandoned,
  and conflating "abandoned before attempting" with "attempted and failed" makes every
  rate computed off this table wrong.
- No tier applying at all. If no remediator could handle the change then no repair was
  attempted; what happened is a routing failure, which is a different grain and would be a
  different table. It stays queryable through the run's own `abandon_reason`. That is a
  different fact from "the agent tier ran and failed", which `tiered.TierFailed` carries a
  strategy for and which does write a row.

An unconfigured salt is deliberately **not** on that list -- see `corpus_salt`.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

from sync.core import MigrationOutcome, Patch
from sync.route import AGENT, CODEMOD

log = logging.getLogger(__name__)

SALT_VARIABLE = "SYNC_CORPUS_SALT"
# Gitignored, and that is the point: a salt committed to git is a public salt. Kept at the
# repository root rather than under `.cache/` so it is visible to anyone wondering what
# Sync wrote, and so deleting the caches does not silently orphan every row already stored.
SALT_FILE = Path(__file__).resolve().parents[3] / ".sync-corpus-salt"

# The salt used when the file cannot be written. Held for the life of the process rather
# than generated per call: two attempts on one finding that disagreed about the digest of
# `amount` would be unjoinable to each other as well as to every other run.
_fallback: str | None = None

# `PatchStrategy` is a two-value Literal in `sync.core`, and `tier` is the axis the corpus
# index is built on. Deriving one from the other is not a guess: which tier ran *is* which
# remediator produced the patch. `sync.route.matrix.route()` decides the tier a finding
# should take, which is a different question and is not wired into this pipeline.
_TIERS = {"codemod": CODEMOD, "agent": AGENT}

# tsc writes `error TS2339: ...`. The code alone classifies the failure without carrying a
# message that quotes the customer's own identifiers.
_TS_ERROR = re.compile(r"\bTS(\d+)\b")


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
    """The per-deployment salt for `hash_arg_keys`.

    Three constraints have to hold together, and only one arrangement satisfies all three.
    The salt must be **stable across runs**, or two runs hash `amount` differently and the
    corpus cannot be joined to itself. It must be **unique per deployment**, or it is a
    dictionary lookup -- an unsalted digest of `amount` is `amount` to anyone willing to
    hash a wordlist, which is the whole reason `hash_arg_keys` takes one. And it must
    **never fail a run**.

    A constant in the source satisfies the first and third and fails the second, which is
    the failure that matters: this project is open core, so a constant that ships is a
    published constant, and every deployment that had not set the variable would silently
    be storing plaintext.

    So: an operator's `SYNC_CORPUS_SALT` wins if set; otherwise one is generated once and
    kept in a gitignored file beside the repository. `secrets`, not `random`: this is a
    value whose guessability is the entire question.
    """
    configured = os.environ.get(SALT_VARIABLE)
    if configured:
        return configured
    return _persisted_salt()


def _persisted_salt() -> str:
    """The generated salt, read from disk or written there on first use.

    A file that cannot be read or written falls back to a salt held for the life of the
    process. That trades cross-run comparability -- these rows join to each other and to
    nothing else -- for still having the rows at all, which is the right way round:
    recording must never fail a run, and a row nobody can join is still a row somebody can
    count.
    """
    global _fallback
    if _fallback is not None:
        return _fallback

    try:
        if SALT_FILE.exists():
            existing = SALT_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        generated = secrets.token_hex(32)
        SALT_FILE.write_text(f"{generated}\n", encoding="utf-8")
        log.info("generated a corpus salt and stored it at %s", SALT_FILE)
        return generated
    except OSError as exc:
        _fallback = secrets.token_hex(32)
        log.warning(
            "could not read or write %s (%s), so this process is using a salt of its own: "
            "its migration_outcome rows are comparable with each other and with no other "
            "run's",
            SALT_FILE, exc,
        )
        return _fallback


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


class CorpusWriterMissing(TypeError):
    """A store handed to `make_recorder` cannot write the corpus.

    A `TypeError` because that is what it is: the object does not satisfy the one method this
    module needs. Raised at construction rather than at the write, for the reason the module
    docstring gives -- the write is wrapped in a handler that must not be removed.
    """


@runtime_checkable
class CorpusWriter(Protocol):
    """The whole contract a store owes this module.

    One method. Stated as a protocol so the requirement has a name a reader can find, rather
    than living in an attribute lookup that only fails at runtime.
    """

    def record_migration_outcome(self, outcome: MigrationOutcome) -> None: ...


class CorpusRecorder:
    """A callable recorder with queryable attempt and error metrics.

    B130: a recording failure must never crash a run, but swallowing errors silently makes
    systematic failures invisible. Tracking attempt counts and error messages on the recorder
    makes failed writes queryable without raising.
    """

    def __init__(self, store: CorpusWriter, *, is_rehearsal: bool = False) -> None:
        self._store = store
        self._is_rehearsal = is_rehearsal
        self.attempt_count: int = 0
        self.success_count: int = 0
        self.failure_count: int = 0
        self.errors: list[str] = []

    def __call__(
        self,
        state,
        *,
        terminal_status: str,
        abandon_reason: str | None = None,
        abandon_reason_code: str | None = None,
        pr_number: int | None = None,
    ) -> bool:
        """`pr_number` is passed by the one node that opened a pull request, and by nothing else.

        That is what holds the grain. One row is one attempt and a run can make several, but
        only the attempt that opened the pull request has a number; a retried attempt keeps a
        null because no call site gives it one, rather than because two writes happened to run
        in a helpful order. A merge recorded against every row of a run would inflate the
        numerator of the merge rate silently, which is worse than being wrong loudly.

        `abandon_reason_code` is passed only by `make_abandon`, same as `abandon_reason` beside
        it (B128): the closed vocabulary declared in `sync.remediate.state`, not a second
        classification done here.
        """
        self.attempt_count += 1
        try:
            ok = _record(
                self._store,
                state,
                terminal_status,
                abandon_reason,
                pr_number,
                abandon_reason_code=abandon_reason_code,
                is_rehearsal=self._is_rehearsal,
            )
            if ok:
                self.success_count += 1
            return ok
        except Exception as exc:
            self.failure_count += 1
            finding_id = getattr(state.get("finding"), "id", None)
            attempt = state.get("static_attempts")
            err_msg = f"finding {finding_id} attempt {attempt}: {exc}"
            self.errors.append(err_msg)
            # Never propagates. The pull request is the product; the row is bookkeeping,
            # and bookkeeping that can fail a run is worse than bookkeeping that is missing.
            log.warning(
                "could not record a migration_outcome row for finding %s attempt %s",
                finding_id,
                attempt,
                exc_info=True,
            )
            return False


def make_recorder(store: CorpusWriter, *, is_rehearsal: bool = False) -> CorpusRecorder:
    """The callable closed over `store` that every terminal and retried node records through.

    `is_rehearsal` is bound once at construction rather than threaded through every caller.
    The graph's nodes record with `record(state, terminal_status=...)` and know nothing about
    whether the run is rehearsal or production -- `make_locate` and `make_abandon` need no
    new argument and no run can be configured with the recording silently absent.

    `is_rehearsal` is not read off `store` or derived from whether a forge is present --
    `sync.rehearse.driver` is the only caller of `build_graph` that means a rehearsal, and this
    module's own test suite calls `build_graph(forge=None, ...)` for reasons that have nothing
    to do with `sync rehearse`, so folding rehearsal-ness into forge presence would mislabel
    every one of those runs in the corpus. It is threaded through explicitly instead, and
    defaults to `False` because every existing caller means a production run.

    Raises `CorpusWriterMissing` if the store cannot write. Callability is checked rather than
    presence, because `hasattr` is satisfied by anything bound to that name -- a column, a
    `None`, a leftover attribute -- and the contract is a method. The message names both the
    method and the type that lacks it, so a reader does not have to diff two versions of the
    store to see why recording stopped.
    """
    write = getattr(store, "record_migration_outcome", None)
    if not callable(write):
        raise CorpusWriterMissing(
            f"{type(store).__name__} cannot write the migration corpus: it needs a callable "
            f"record_migration_outcome(outcome), which is the single write every benchmark "
            f"axis reads from"
        )

    return CorpusRecorder(store, is_rehearsal=is_rehearsal)


def _record(
    store, state, terminal_status: str, abandon_reason: str | None,
    pr_number: int | None = None, *,
    abandon_reason_code: str | None = None, is_rehearsal: bool = False,
) -> bool:
    # No lookup guard here: `make_recorder` established that this store can write before any
    # node ran. Re-checking per write would be a check that cannot be loud, since the caller
    # swallows everything this raises.
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

    started = state.get("attempt_started_at")
    wall_ms = max(0, round((now() - started) * 1000)) if started else 0

    static_passed = state.get("attempt_static_passed")
    store.record_migration_outcome(
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
            # `_decide_tier` put this on the state at `locate`. Read from there rather than
            # through `on_route`, which has no caller: the recorder already holds the state
            # the row lives on, so a second delivery path would be one more thing to keep in
            # agreement with this one. `"unrouted"` when the table had no jurisdiction, which
            # `nodes.py` already calls by that name in the report reason.
            routing_row=state.get("routing_row") or "unrouted",
            wall_ms=wall_ms,
            salt=corpus_salt(),
            static_verify_passed=static_passed,
            static_verify_error_class=(
                static_error_class(state.get("diagnostics")) if static_passed is False else None
            ),
            ci_result=state.get("attempt_ci_result"),
            terminal_status=terminal_status,
            abandon_reason=abandon_reason,
            abandon_reason_code=abandon_reason_code,
            # The join a merge delivery arrives on. Null on every attempt but the one that
            # opened the pull request, which is the grain this table declares.
            pr_number=pr_number,
            is_rehearsal=is_rehearsal,
        )
    )
    return True
