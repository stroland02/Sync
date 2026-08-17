"""State carried through the remediation graph and checkpointed at every node."""

from __future__ import annotations

from typing import Literal, TypedDict

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange

# `reported` is not a kind of abandonment and the two must stay apart. Abandonment means
# Sync tried and could not finish; `reported` means the decision table found there was
# correctly nothing to try. `abandon_reason` is where routing learns which change kinds are
# not mechanically safe, and "this kind never needed a patch" written there would corrupt
# exactly that signal. `external_cause` records external vendor conditions (e.g. outage),
# and `parked` suspends a run for human review.
Outcome = Literal["running", "opened", "abandoned", "reported", "external_cause"]

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
    # What replay established, and what it could not. `replay_outcome` is the whole answer and
    # `replay_ok` is shorthand for one value of it, kept beside it for the same reason
    # `verify_ok` exists: a router must branch on a boolean a node set deliberately rather
    # than infer a verdict from the shape of a string.
    #
    # The distinction that has to survive is `declined` and `not-attempted` against `passed`.
    # Replay cannot always run -- no resolvable export, a language it cannot execute, a file
    # the index has outlived -- and none of those is a verdict on the patch. They must never
    # read as "the patched path was executed", because that sentence goes in front of a
    # reviewer. `route_after_replay` lets them through to the push path, so replay is an
    # additional tier rather than a precondition, and the run carries the fact that it was
    # not replay-verified.
    replay_outcome: str
    replay_reason: str
    replay_ok: bool
    # The sentence a pull request body can carry. Here rather than on `Evidence`, which lives
    # in `sync.core` and is not this package's to widen; a caller that renders the body reads
    # it from the finished run until that field exists.
    replay_evidence: str
    # `source='replay'` rows the run offers and does not write. Plain dicts rather than
    # `ObservedShape`, because `serde.CHECKPOINTED_TYPES` is the allowlist a checkpoint
    # reconstructs models from and adding to it means editing a module this task does not own.
    #
    # Not written at all, and that is a decision rather than an omission: they describe the
    # mock the code was exercised against, not traffic a vendor sent. Filed in the store
    # beside real observations they would leave the drift detector comparing reality against a
    # mock Sync itself built, which is worse than an empty baseline.
    replay_shapes: list[dict]
    # Everything replay needs that neither the finding nor the clone supplies: the new
    # operation's response schema, the export that encloses the patched call, the vendor's
    # package name, and the arguments to call it with. Seeded by whoever starts the run.
    #
    # Absent means replay cannot run, which is recorded rather than treated as a pass. Nothing
    # in `src/` seeds it yet -- `sync.cli` is where the specification and the adapter are both
    # in hand -- so every run today records `not-attempted`.
    replay_plan: dict
    # Set only when prepare or static_verify raises rather than returning a
    # normal result -- an environment fault (broken registry, lockfile out of
    # sync with package.json), not something a different patch could fix.
    # Routes straight to abandon, bypassing the static-attempt retry budget.
    prepare_ok: bool
    # Whether this repository's language adapter can verify a patch at all, set by `prepare`
    # from the adapter it already holds. Python cannot -- `static_verify` fails closed and
    # always will -- so a finding there is reported rather than attempted.
    #
    # A boolean is what routes and the string beside it is what the report says, which is the
    # same split `verify_ok` and `diagnostics` already make. Branching on whether the string is
    # empty would be routing on the incidental shape of an output, which is the discipline
    # `route_after_static` exists to model.
    #
    # Decided before the branch out of `prepare` rather than caught inside `patch`: catching it
    # there would leave `patch` in the executed node sequence and record an attempt that should
    # never have started, which is the defect the tier -1 work fixed for lifecycle changes.
    verifiable: bool
    verify_gap: str
    static_fatal: bool
    # The same rule for the nodes whose failures are neither an adapter's nor a
    # remediator's: a store lookup that raised, a rejected push, a CI poll that
    # never produced a verdict, a pull request that could not be opened. One key
    # rather than one per node because the treatment is identical and every
    # writer routes on it immediately, so no two of them are ever in flight at
    # once. `patch` is deliberately not among them -- patch generation can
    # succeed on a second attempt, so it retries rather than setting this.
    fatal: bool
    # What the decision table assigned, and the row that assigned it. Written once, by
    # `locate`, from the only two inputs the table reads -- so the branch out of `prepare`
    # reads a value a node set deliberately rather than recomputing the route, which is the
    # discipline `route_after_static` already models with `verify_ok`.
    #
    # `None` is not a tier. It means the table had no jurisdiction: no catalogue was
    # supplied, or the change's kind is not an oasdiff rule id. A deprecation's kind is
    # `deprecation/model-retired`, which no catalogue carries, and treating that as tier -1
    # would switch off the one signal that costs no tokens.
    #
    # These are also the whole of what a tier -1 outcome leaves behind. `migration_outcome`
    # cannot hold one: `strategy` is `PatchStrategy`, a two-value Literal, and `NOT NULL`,
    # so no value expresses "no patch was warranted" -- see the report node. Until that is
    # widened, reading the routing decision out of a finished run means reading it here.
    tier: int | None
    routing_row: str | None
    # One line for an operator on a run that produced no pull request and was not a
    # failure. Deliberately not `diagnostics`: that one becomes `abandon_reason`.
    report_reason: str
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
    # The number GitHub gave the pull request, from the forge that created it rather than
    # parsed back out of the URL. `migration_outcome` is joined to a merge delivery by this
    # and nothing else durable: the row carries no branch and the delivery carries no
    # finding. Set only by `open_pr`, so a run that opened none leaves it unset.
    pr_number: int | None
    outcome: Outcome
    abandon_reason: str
    findings_report: dict | None
    external_cause_report: dict | None
    human_question: dict | None
    outcome_confidence: int | None
    outcome_citations: list[str] | None
