"""The symbol map the corpus is scored against has to be reproducible by a command.

`benchmark/corpus/symbol_map.yaml` pins the map and says in prose how to rebuild it. Prose is
not executable, and the consequence was measurable: CI fetched the corpus, reached
`score_corpus.py`, and was refused with `no symbol map at .cache/specs/symbols.json` -- the
gate has never once run on a runner, because no step could stage what it verifies.

The refusal is the part worth testing. A map that does not match the pin must not reach the
path the scorer reads, or the next run scores a resolution nobody recorded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.stage_symbol_map import stage_symbol_map
from scripts.symbol_map_pin import SymbolMapMismatch, symbol_map_digest, verify_staged_map
from sync.signals.stripe.symbols import build_symbol_map

# One path with one operation, which is all the builder needs to produce a map. The specification
# the corpus really uses is 7.8 MB and gitignored; what is under test here is the pin check
# around the builder, not the builder.
SPEC = {
    "paths": {
        "/v1/payment_intents": {
            "post": {"operationId": "PostPaymentIntents"},
        },
    },
}


@pytest.fixture()
def spec(tmp_path: Path) -> Path:
    path = tmp_path / "v2330.json"
    path.write_text(json.dumps(SPEC), encoding="utf-8")
    return path


def _pin(mapping: dict) -> dict:
    return {
        "digest": symbol_map_digest(mapping),
        "symbols": len(mapping),
        "staged_at": ".cache/specs/symbols.json",
        "built_from": "this test",
    }


def test_a_matching_map_is_staged_where_the_scorer_reads_it(spec, tmp_path):
    """The whole point: after this runs, `verify_staged_map` accepts what is on disk."""
    pin = _pin(build_symbol_map(json.loads(spec.read_text(encoding="utf-8")), None))
    into = tmp_path / "specs" / "symbols.json"

    digest = stage_symbol_map(spec, into, pin)

    assert digest == pin["digest"]
    assert verify_staged_map(into, pin) == pin["digest"]


def test_a_map_that_does_not_match_the_pin_never_reaches_the_disk(spec, tmp_path):
    """Refused before the write, not after it.

    Writing first and checking second leaves the wrong map staged for whatever runs next, and
    the scorer's own refusal is the only thing standing between that and a scored number over a
    resolution nobody recorded.
    """
    pin = _pin(build_symbol_map(json.loads(spec.read_text(encoding="utf-8")), None))
    pin["digest"] = "0" * 64
    into = tmp_path / "specs" / "symbols.json"

    with pytest.raises(SymbolMapMismatch):
        stage_symbol_map(spec, into, pin)

    assert not into.exists()


def test_a_stale_map_already_on_disk_is_left_alone_when_the_new_one_is_refused(spec, tmp_path):
    """A refusal must not be a deletion either.

    The staged path is shared -- `.cache/` is per-worktree and several workers run here at once
    -- so a refused rebuild that truncated the file would break a run that was scoring fine.
    """
    pin = _pin(build_symbol_map(json.loads(spec.read_text(encoding="utf-8")), None))
    into = tmp_path / "specs" / "symbols.json"
    into.parent.mkdir(parents=True)
    into.write_text('{"already": {"here": "1"}}', encoding="utf-8")

    with pytest.raises(SymbolMapMismatch):
        stage_symbol_map(spec, into, {**pin, "digest": "0" * 64})

    assert json.loads(into.read_text(encoding="utf-8")) == {"already": {"here": "1"}}
