"""The merge webhook gets a caller, and the last two benchmark axes get a numerator.

`record_merge_outcome` verified a signature, distinguished a forgery from a malformed payload,
and updated the corpus -- and nothing handed it a delivery. The cost is measured rather than
theoretical: `2026-07-27-sync-benchmark-gates.md` calls merge rate "the direct test of the
product claim", and both it and cost per merged patch stay null until a real `pr_merged` arrives.

No server. `2026-07-27-sync-pipeline-discipline.md` refuses ingestion infrastructure, and the
OTLP wiring already set the shape: a command that takes bytes somebody else collected. So these
tests drive `sync.cli.merge_outcome` rather than calling `record_merge_outcome`, because calling
it directly re-creates exactly the situation this task fixes, and one of them asserts no socket
is opened at all.

The secret is a credential and nothing here commits one. Every signature below is computed at
test time over a throwaway secret generated in the test, which is also the only way the
signature can be right: the HMAC covers the exact bytes of the delivery, so it cannot be
precomputed and stored beside a fixture that anyone might reformat.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import socket
from pathlib import Path

import pytest

import sync.cli as cli
from sync.benchmark import compute_axes
from sync.cli import merge_outcome
from sync.core import MigrationOutcome
from sync.graph.store import GraphStore

DSN = os.environ.get("SYNC_DSN", "postgresql://sync:sync@localhost:5433/sync")
FIXTURES = Path(__file__).parent / "fixtures" / "webhook"

MERGED_PR = 41
UNMERGED_PR = 42


@pytest.fixture()
def secret() -> bytes:
    """A throwaway secret, generated here and never written beside a fixture.

    Committing one -- even a fake -- teaches the pattern that a shared secret has a value this
    repository knows, which is the pattern that puts a real one in a diff six months later.

    Printable, and the key is its bytes rather than a decoding of them. GitHub's secret is a
    string somebody types into a settings page and the HMAC key is that string's bytes; any
    encoding step here would be a Sync-specific rule an operator pasting their own secret would
    get wrong, and would fail as a signature mismatch that looks like forgery.
    """
    return secrets.token_hex(32).encode("ascii")


@pytest.fixture()
def store() -> GraphStore:
    """A store holding only this test's rows, truncated rather than assumed empty."""
    store = GraphStore(DSN)
    store.apply_schema()
    with store.transaction():
        store.truncate_all()
    return store


def _outcome(**overrides) -> MigrationOutcome:
    """One corpus row at the grain the corpus uses: an attempt, not a finding."""
    fields = dict(
        finding_id="f-1", attempt_index=1,
        vendor_id="stripe", from_version="v2320", to_version="v2330",
        change_kind="request-property-removed", change_severity="breaking",
        language="typescript", symbol_shape="stripe.paymentIntents.*", arg_arity=3,
        response_fields_touched_count=1,
        strategy="codemod", tier=0, routing_row="unrouted", wall_ms=1200,
        input_tokens=0, output_tokens=0,
        static_verify_passed=True, terminal_status="pr_opened",
    )
    fields.update(overrides)
    return MigrationOutcome(**fields)


def _opened(store: GraphStore, pr_number: int, finding_id: str) -> None:
    """A row for a pull request Sync opened, which is what a delivery has to match.

    `pr_number` is written here rather than by the pipeline, and that is a real gap rather than
    a test convenience: nothing in `src/` sets it when the pull request opens, so
    `_attempt_for` can match no delivery in production. Reported rather than papered over --
    the receiver and the command are correct and the link one step upstream is missing.
    """
    store.record_migration_outcome(_outcome(finding_id=finding_id, pr_number=pr_number))


def _sign(body: bytes, secret: bytes) -> str:
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def _delivery(tmp_path: Path, fixture: str) -> tuple[Path, bytes]:
    """The delivery on disk and its exact bytes.

    Copied byte for byte rather than re-serialised. The HMAC covers what was received, so a
    payload decoded and re-encoded on the way past would fail verification for a reason that
    looks exactly like forgery.
    """
    body = (FIXTURES / fixture).read_bytes()
    path = tmp_path / fixture
    path.write_bytes(body)
    return path, body


def _args(payload: Path, signature: str, **overrides) -> argparse.Namespace:
    fields = dict(
        payload=str(payload), signature=signature, secret_file=None,
        commits=None, dsn=DSN,
    )
    fields.update(overrides)
    return argparse.Namespace(**fields)


def _run(
    tmp_path: Path, fixture: str, secret: bytes, *, sign_with: bytes | None = None, **overrides
) -> int:
    payload, body = _delivery(tmp_path, fixture)
    signature = _sign(body, sign_with if sign_with is not None else secret)
    return merge_outcome(_args(payload, signature, **overrides))


@pytest.fixture()
def env_secret(monkeypatch: pytest.MonkeyPatch, secret: bytes) -> bytes:
    monkeypatch.setenv(cli.WEBHOOK_SECRET_ENV, secret.decode("ascii"))
    return secret


def _row(store: GraphStore, finding_id: str = "f-1") -> MigrationOutcome:
    return next(r for r in store.migration_outcomes() if r.finding_id == finding_id)


# --- the delivery that matters ----------------------------------------------------


def test_a_signed_merge_delivery_populates_pr_merged(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """Driven through the command. Calling `record_merge_outcome` here would assert the
    receiver works, which was never in doubt -- what was missing is anything that calls it."""
    _opened(store, MERGED_PR, "f-1")

    assert _run(tmp_path, "pull_request_merged.json", env_secret) == 0
    assert _row(store).pr_merged is True


def test_a_closed_delivery_that_did_not_merge_is_recorded_as_not_merged(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """False and null are different facts and the benchmark divides by one of them: a null
    `pr_merged` is a webhook that has not arrived, and recording a rejection as absent would
    make the merge rate improve on its own with nothing in the pipeline having changed."""
    _opened(store, UNMERGED_PR, "f-2")

    assert _run(tmp_path, "pull_request_closed_unmerged.json", env_secret) == 0

    row = _row(store, "f-2")
    assert row.pr_merged is False
    assert row.pr_merged is not None


def test_an_action_that_decides_nothing_writes_nothing(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """GitHub fires `pull_request` on a dozen actions. A merge recorded on `opened` is a merge
    that has not happened, and it is not an error either -- so the command succeeds and the
    column stays null."""
    _opened(store, MERGED_PR, "f-1")

    assert _run(tmp_path, "pull_request_opened.json", env_secret) == 0
    assert _row(store).pr_merged is None


def test_human_edits_are_counted_only_when_the_caller_fetched_them(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """Absent commits leave the column null rather than zero. Zero is a measurement and it
    reads as "no human touched this patch", which is the exact claim the benchmark rests on."""
    _opened(store, MERGED_PR, "f-1")
    commits = tmp_path / "commits.json"
    commits.write_bytes((FIXTURES / "commits.json").read_bytes())

    assert _run(tmp_path, "pull_request_merged.json", env_secret, commits=str(commits)) == 0
    assert _row(store).human_edits_before_merge == 1


# --- the credential ---------------------------------------------------------------


def test_a_forged_signature_changes_nothing_in_the_store(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """Asserted on the row rather than on an exception. A command that raised after writing
    would satisfy any test that only checked for the raise, and the corpus is the table every
    future routing decision is measured against."""
    _opened(store, MERGED_PR, "f-1")

    exit_code = _run(
        tmp_path, "pull_request_merged.json", env_secret, sign_with=b"not-the-secret",
    )

    assert exit_code != 0
    assert _row(store).pr_merged is None


def test_a_missing_secret_refuses_to_run(
    tmp_path: Path, store: GraphStore, secret: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It must never fall through to processing an unverified payload. Absent a secret there
    is no question to ask of the bytes, so there is nothing to do but refuse."""
    monkeypatch.delenv(cli.WEBHOOK_SECRET_ENV, raising=False)
    _opened(store, MERGED_PR, "f-1")

    exit_code = _run(tmp_path, "pull_request_merged.json", secret)

    assert exit_code != 0
    assert _row(store).pr_merged is None


def test_an_empty_secret_is_a_missing_secret(
    tmp_path: Path, store: GraphStore, secret: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exported-but-empty variable is the ordinary way a secret goes missing in a shell, and
    reading it as a secret would verify every delivery against the empty string."""
    monkeypatch.setenv(cli.WEBHOOK_SECRET_ENV, "")
    _opened(store, MERGED_PR, "f-1")

    assert _run(tmp_path, "pull_request_merged.json", secret) != 0
    assert _row(store).pr_merged is None


def test_a_secret_file_is_read_as_bytes_without_its_trailing_newline(
    tmp_path: Path, store: GraphStore, secret: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other supported source. A file written by `echo` carries a newline the shared secret
    does not, and an HMAC over the wrong key fails in a way indistinguishable from forgery."""
    monkeypatch.delenv(cli.WEBHOOK_SECRET_ENV, raising=False)
    _opened(store, MERGED_PR, "f-1")
    secret_file = tmp_path / "webhook.secret"
    secret_file.write_bytes(secret + b"\n")

    assert _run(
        tmp_path, "pull_request_merged.json", secret, secret_file=str(secret_file)
    ) == 0
    assert _row(store).pr_merged is True


def test_the_secret_never_reaches_the_output(
    tmp_path: Path, store: GraphStore, env_secret: bytes, capsys: pytest.CaptureFixture
) -> None:
    """Not the value and not a prefix of it. An operator pastes this output into an issue."""
    _opened(store, MERGED_PR, "f-1")
    _run(tmp_path, "pull_request_merged.json", env_secret)

    captured = capsys.readouterr()
    hexed = env_secret.decode("ascii")
    assert hexed not in captured.out + captured.err
    assert hexed[:8] not in captured.out + captured.err


# --- no server --------------------------------------------------------------------


def test_no_port_is_bound_and_no_listener_starts(
    tmp_path: Path, store: GraphStore, env_secret: bytes, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal `2026-07-27-sync-pipeline-discipline.md` records, asserted rather than
    documented. This command reads bytes somebody else collected; the moment it opens a socket
    it needs a port, a supervisor and an authentication story, none of which makes a delivery
    mean more once it lands."""
    def _no_sockets(*args, **kwargs):
        raise AssertionError("the merge-outcome command opened a socket")

    monkeypatch.setattr(socket.socket, "bind", _no_sockets)
    monkeypatch.setattr(socket.socket, "listen", _no_sockets)
    monkeypatch.setattr(socket.socket, "connect", _no_sockets)

    _opened(store, MERGED_PR, "f-1")

    assert _run(tmp_path, "pull_request_merged.json", env_secret) == 0


# --- the axes this exists to unblock ----------------------------------------------


def test_merge_rate_is_computable_after_the_command_runs(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """The point of the task.

    Before a delivery lands, `pr_merged` is null on every row and the axis reports unmeasured
    over zero samples -- which is the honest answer and is not a measurement. After one, the
    rate is a number with a sample size beside it, which is what the spec means by recorded
    rather than gated. No threshold is asserted here, deliberately: a test that pinned one
    would be the gate the spec forbids arriving by the back door.
    """
    _opened(store, MERGED_PR, "f-1")
    _opened(store, UNMERGED_PR, "f-2")

    before = compute_axes(store.migration_outcomes())
    assert before.merge_rate_by_change_kind == {}
    assert before.counts.pull_requests_merged == 0

    _run(tmp_path, "pull_request_merged.json", env_secret)
    _run(tmp_path, "pull_request_closed_unmerged.json", env_secret)

    after = compute_axes(store.migration_outcomes())
    rate = after.merge_rate_by_change_kind["request-property-removed"]

    assert rate.value == 0.5
    assert rate.n == 2
    assert after.counts.pull_requests_merged == 1


def test_cost_per_merged_patch_becomes_measurable_too(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """The second axis the same null was blocking. It divides by merged pull requests, so it
    reports unmeasured until one exists and a real number afterwards."""
    store.record_migration_outcome(
        _outcome(finding_id="f-1", pr_number=MERGED_PR, wall_ms=1500,
                 input_tokens=100, output_tokens=40)
    )

    assert compute_axes(store.migration_outcomes()).tokens_per_merged_patch.value is None

    _run(tmp_path, "pull_request_merged.json", env_secret)

    axes = compute_axes(store.migration_outcomes())
    assert axes.tokens_per_merged_patch.value == 140
    assert axes.wall_ms_per_merged_patch.n == 1


def test_a_delivery_matching_no_row_is_not_an_error(
    tmp_path: Path, store: GraphStore, env_secret: bytes
) -> None:
    """Humans and other automation open pull requests in the same repository and every one of
    them delivers here. Raising on somebody else's merge would turn it into an operator's
    incident."""
    assert _run(tmp_path, "pull_request_merged.json", env_secret) == 0
    assert store.migration_outcomes() == []
