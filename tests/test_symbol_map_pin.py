"""The corpus's second frozen input, which it did not pin.

`repositories.yaml` pins every checkout by commit and validates each against a `tree_digest`, and
the fetcher refuses on mismatch. The symbol map is the other input the score depends on and it
was a cached artifact in gitignored space that nothing recorded, nothing validated, and any
`sync run` could overwrite -- a different head specification, or `sdk_spec` present rather than
absent, changes what resolves and therefore what the binder can find.

`2026-07-27-sync-benchmark-gates.md` is what makes that matter: an unfrozen benchmark measures
the benchmark. A score could move, or fail to move when it should have, with no commit and no
digest mismatch to explain it -- and `gate_corpus.py` now gates on those numbers.

What is asserted here is the pin, in the same three parts the checkout pin has: what the digest
covers, that a reserialisation does not move it, and that a real change does.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import symbol_map_pin
from scripts.symbol_map_pin import (
    PIN,
    SymbolMapMismatch,
    SymbolMapRewritten,
    read_pin,
    symbol_map_digest,
    verify_staged_map,
)

MAP = {
    "stripe.charges.create": {
        "operation_id": "PostCharges", "http_method": "post", "path": "/v1/charges",
    },
    "stripe.customers.list": {
        "operation_id": "GetCustomers", "http_method": "get", "path": "/v1/customers",
    },
}


def _staged(tmp_path: Path, mapping: dict, **dumps) -> Path:
    path = tmp_path / "symbols.json"
    path.write_text(json.dumps(mapping, **dumps), encoding="utf-8")
    return path


# --- what the digest covers -------------------------------------------------------------


def test_the_digest_survives_a_reserialisation_that_changes_every_byte():
    """The reason it is over the content and not over the file.

    `tree_digest` hashes bytes because a checkout *is* its bytes -- an indexer reads the file it
    was given. A symbol map is a mapping, and its meaning is which symbol resolves to which
    operation. Indentation, key order and separators are how a serialiser felt on the day, and a
    digest that moved on them would report a corpus change every time the file was rewritten by a
    different writer, which is the "fires constantly and gets disabled" failure one input over.
    """
    compact = json.dumps(MAP, separators=(",", ":"), sort_keys=True)
    sprawling = json.dumps(dict(reversed(list(MAP.items()))), indent=4)

    assert compact.encode() != sprawling.encode()
    assert symbol_map_digest(json.loads(compact)) == symbol_map_digest(json.loads(sprawling))


def test_a_symbol_that_resolves_somewhere_else_moves_the_digest():
    """The property the pin exists for. B39 took the map from 179 symbols to 272 and the corpus
    could not see it."""
    moved = json.loads(json.dumps(MAP))
    moved["stripe.charges.create"]["operation_id"] = "PostChargesSomethingElse"

    assert symbol_map_digest(moved) != symbol_map_digest(MAP)


def test_a_symbol_appearing_or_disappearing_moves_the_digest():
    added = {**MAP, "stripe.refunds.create": {
        "operation_id": "PostRefunds", "http_method": "post", "path": "/v1/refunds",
    }}
    removed = {k: v for k, v in MAP.items() if k != "stripe.customers.list"}

    assert symbol_map_digest(added) != symbol_map_digest(MAP)
    assert symbol_map_digest(removed) != symbol_map_digest(MAP)


def test_the_method_and_path_are_covered_as_well_as_the_operation():
    """A symbol pointing at the same operation by a different route is a different mapping. The
    indexer records `path` on every call site it emits, so a change here reaches the score."""
    for field, value in (("http_method", "put"), ("path", "/v1/charges/{charge}")):
        moved = json.loads(json.dumps(MAP))
        moved["stripe.charges.create"][field] = value
        assert symbol_map_digest(moved) != symbol_map_digest(MAP), field


def test_a_key_the_map_does_not_carry_is_not_silently_ignored():
    """Digesting a hand-picked triple would go blind the day the builder emits a fourth field.
    Every key of every entry is covered, so a new one moves the digest and is noticed rather than
    dropped."""
    widened = json.loads(json.dumps(MAP))
    widened["stripe.charges.create"]["deprecated"] = True

    assert symbol_map_digest(widened) != symbol_map_digest(MAP)


# --- the pin, and what it refuses ---------------------------------------------------------


def test_the_staged_map_matches_the_pin_this_corpus_records():
    """The corpus's own state, asserted from the committed pin against the artifact on disk.

    Through `verify_staged_map` rather than around it, which is a change of two kinds. It is the
    check the scorer actually makes, so this test now fails when the scorer would refuse instead of
    when a locally rewritten pair of assertions would. And it reads the artifact once: the previous
    form read it for the digest and read it again for the count, which in gitignored per-worktree
    space is two reads of a file another process may have replaced in between -- it could refuse
    over a map that was never on disk in that state.

    The skip on absence stays. An absent artifact is a tree where the documented fetch has not run,
    which is a fact about the checkout rather than about the pin. A skip on *mismatch* would retire
    this check, so a mismatch stays a failure whatever produced it -- and `SymbolMapRewritten` is
    how a reader tells the two apart.
    """
    pin = read_pin(PIN)
    staged = Path(pin["staged_at"])
    if not staged.exists():
        pytest.skip(f"no staged symbol map at {staged}; run the documented fetch first")

    assert verify_staged_map(staged, pin) == pin["digest"]


def test_a_staged_map_that_does_not_match_the_pin_is_refused_by_name(tmp_path):
    """Loudly, and naming both digests. A mismatched map must not produce a number that looks
    ordinary -- the score would be a real number over a resolution nobody recorded."""
    moved = json.loads(json.dumps(MAP))
    moved["stripe.charges.create"]["operation_id"] = "PostSomethingElse"
    path = _staged(tmp_path, moved)

    with pytest.raises(SymbolMapMismatch, match="symbol map"):
        verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 2})


def test_a_missing_staged_map_is_refused_rather_than_treated_as_empty(tmp_path):
    """Deleting it is how this was found: `scripts/score_corpus.py` died with `FileNotFoundError`
    from inside the Stripe adapter, which is a stack trace rather than an explanation."""
    with pytest.raises(SymbolMapMismatch, match="no symbol map"):
        verify_staged_map(tmp_path / "absent.json", {"digest": "x", "symbols": 2})


def test_a_matching_map_verifies_and_returns_its_digest(tmp_path):
    path = _staged(tmp_path, MAP, indent=2)

    assert verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 2}) == \
        symbol_map_digest(MAP)


def test_the_symbol_count_is_checked_as_well_as_the_digest(tmp_path):
    """Redundant by construction and kept anyway: the count is what a human reads in a diff and
    what the report of a change quotes, so a pin whose two halves disagree is a pin somebody
    edited without re-deriving."""
    path = _staged(tmp_path, MAP)

    with pytest.raises(SymbolMapMismatch, match="2 symbol"):
        verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 99})


# --- which of the two things a refusal is about ---------------------------------------------


def _rewritten_while_digesting(monkeypatch, path: Path, mapping: dict) -> None:
    """Make the staged file change *after* `verify_staged_map` has read it.

    A concurrent rewrite is another process writing the artifact between the read and the
    comparison, and the digest is what sits between them. Patching it to rewrite the file and then
    delegate reproduces that ordering exactly, in one process and with no sleep and no thread. The
    ordering it depends on is stated in `verify_staged_map`: the digest is taken before any
    refusal is raised, precisely so every refusal is classified by the same re-read.
    """
    real = symbol_map_pin.symbol_map_digest

    def digest_then_rewrite(staged):
        digest = real(staged)
        path.write_text(json.dumps(mapping), encoding="utf-8")
        return digest

    monkeypatch.setattr(symbol_map_pin, "symbol_map_digest", digest_then_rewrite)


def test_a_refusal_raised_while_the_file_was_being_rewritten_says_so(monkeypatch, tmp_path):
    """The noise case, made self-identifying.

    `.cache/` is gitignored, `staged_at` is relative, and every process in the worktree can write
    the artifact -- which is how this check once went red in a fourth consecutive suite after three
    clean ones. "The pin is wrong" and "somebody regenerated the map" deserve different answers and
    produced the same bare assertion failure. A reader who cannot tell them apart eventually
    silences the check, and this one guards a frozen corpus input.
    """
    moved = json.loads(json.dumps(MAP))
    moved["stripe.charges.create"]["operation_id"] = "PostSomethingElse"
    path = _staged(tmp_path, moved)
    _rewritten_while_digesting(monkeypatch, path, {"stripe.refunds.create": {}})

    with pytest.raises(SymbolMapRewritten, match="changed while this ran") as refusal:
        verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 2})

    # The classification is added to the refusal, never substituted for it. A reader who decides
    # this was noise and re-runs in a quiet tree needs the digests to still be there if it was not.
    assert symbol_map_digest(moved) in str(refusal.value)
    assert symbol_map_digest(MAP) in str(refusal.value)


def test_a_mismatch_nothing_rewrote_is_not_reported_as_a_rewrite(tmp_path):
    """The control, and the one that matters: everything else here could have softened this.

    A staged map that genuinely is not the pinned one must refuse as a mismatch and name both
    sides. If a classifier ever calls this a rewrite, the reader is told nothing was established
    when in fact something was -- the corpus's frozen input is not the map it records.
    """
    moved = json.loads(json.dumps(MAP))
    moved["stripe.charges.create"]["operation_id"] = "PostSomethingElse"
    path = _staged(tmp_path, moved)

    with pytest.raises(SymbolMapMismatch) as refusal:
        verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 2})

    assert not isinstance(refusal.value, SymbolMapRewritten)
    assert "changed while this ran" not in str(refusal.value)
    assert symbol_map_digest(moved) in str(refusal.value)
    assert symbol_map_digest(MAP) in str(refusal.value)


def test_a_rewrite_landing_after_the_read_does_not_manufacture_a_refusal(monkeypatch, tmp_path):
    """The window this closes rather than narrows.

    The verification is over the bytes it read. A map that matched the pin when it was read
    verifies, and another process replacing the file a microsecond later is the next revision of an
    artifact this call has already finished with -- not a reason to refuse. An implementation that
    re-read the file to compare would refuse here, which is the shape of the failure that put this
    on the backlog.
    """
    path = _staged(tmp_path, MAP, indent=2)
    _rewritten_while_digesting(monkeypatch, path, {"stripe.refunds.create": {}})

    assert verify_staged_map(path, {"digest": symbol_map_digest(MAP), "symbols": 2}) == \
        symbol_map_digest(MAP)


def test_a_file_that_is_not_json_is_refused_by_name_rather_than_by_stack_trace(tmp_path):
    """Half-written JSON is what a rewrite in progress looks like from the reader's side.

    `json.JSONDecodeError` escaping from here reaches `score_corpus.py` as an `Unexpected`
    traceback -- it catches `SymbolMapMismatch`, `OSError` and `ValueError`, and a decode error is
    a `ValueError`, so the scorer says "refused: Expecting value: line 1 column 12" and names
    neither the file nor what to do about it.
    """
    path = tmp_path / "symbols.json"
    path.write_text('{"stripe.charges.create": {"operation', encoding="utf-8")

    with pytest.raises(SymbolMapMismatch, match="does not hold a symbol map"):
        verify_staged_map(path, {"digest": "x" * 64, "symbols": 2})


# --- the pin file itself --------------------------------------------------------------------


def test_the_pin_records_where_the_map_came_from_and_not_only_what_it_is():
    """A digest says which map; provenance says how to get that map back. Without it a mismatch
    is a refusal nobody can act on."""
    pin = read_pin(PIN)

    assert set(pin) >= {"digest", "symbols", "staged_at", "built_from"}
    assert len(pin["digest"]) == 64
    assert pin["symbols"] > 0


def test_a_pin_missing_a_field_is_refused_rather_than_defaulted(tmp_path):
    partial = tmp_path / "symbol_map.yaml"
    partial.write_text("digest: abc\n", encoding="utf-8")

    with pytest.raises(ValueError, match="symbols"):
        read_pin(partial)
