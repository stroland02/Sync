"""Baking a vendor cache into the repository, so a first run resolves a vendor offline.

Beta item 2. `M14-W443` shipped `sync index --repo` and running it proved the gap: a plain
checkout indexes to **0 call sites**, because no vendor cache is staged and `prepare_vendor`
needs `gh` and a credential a first-run user does not have.

**The artifact is committed rather than fetched at image build.** `_load_stripe` needs only
`<cache>/symbols.json` -- measured, not assumed -- and the pinned map is 272 symbols across four
tags at one digest. Committing it makes the image build offline as well as the runtime, so no
step of the install path needs a network or a token. The cost is that the pin becomes a
maintained thing, which the assessment asked be named rather than left as folklore, and the
provenance file is where it is named.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.bake_vendor_cache import bake, read_provenance


def _spec() -> dict:
    return {
        "paths": {
            "/v1/charges": {
                "post": {"operationId": "PostCharges", "x-stripeOperations": [
                    {"method_name": "create", "method_on": "service", "operation": "post",
                     "path": "/v1/charges", "object": "charge"}
                ]},
            }
        }
    }


def test_baking_writes_the_symbol_map_where_the_loader_looks(tmp_path):
    """`_load_stripe` reads `<cache_dir>/symbols.json`, and `_cache_candidates` offers the
    per-vendor directory first, so the map goes in `<into>/stripe/`."""
    bake(_spec(), into=tmp_path, vendor_id="stripe", tag="v2330", expect_digest=None)

    assert (tmp_path / "stripe" / "symbols.json").is_file()


def test_baking_records_which_tag_it_came_from_and_when(tmp_path):
    """**The snapshot ages**, and the assessment requires the image state which version it holds
    and when it was pinned -- so a reader is never guessing whether a finding reflects today's
    Stripe. A cache with no provenance is a claim about a vendor with no date on it."""
    bake(_spec(), into=tmp_path, vendor_id="stripe", tag="v2330", expect_digest=None)

    provenance = read_provenance(tmp_path / "stripe")

    assert provenance["tag"] == "v2330"
    assert provenance["vendor_id"] == "stripe"
    assert provenance["symbols"] >= 1
    # An ISO instant, so staleness is computed against a real timestamp rather than guessed.
    assert provenance["baked_at"].endswith("+00:00")


def test_baking_refuses_a_map_that_does_not_match_the_pin(tmp_path):
    """The pin exists so a specification that silently changes what resolves cannot be baked in
    without somebody deciding to. Refusing writes nothing, rather than leaving half a cache."""
    with pytest.raises(ValueError) as raised:
        bake(_spec(), into=tmp_path, vendor_id="stripe", tag="v2330",
             expect_digest="0" * 64)

    assert "digest" in str(raised.value)
    assert not (tmp_path / "stripe" / "symbols.json").exists(), "refused, but wrote anyway"


def test_a_baked_cache_loads_without_touching_the_network(tmp_path):
    """The whole point. The loader must resolve the vendor from the baked directory alone."""
    from sync.index.codebase import _load_or_create_vendor_adapter
    import sync.index.codebase as codebase

    bake(_spec(), into=tmp_path, vendor_id="stripe", tag="v2330", expect_digest=None)

    def _no_network(*a, **k):
        pytest.fail("resolving a baked vendor reached the network")

    original = codebase.prepare_vendor
    codebase.prepare_vendor = _no_network
    try:
        adapter = _load_or_create_vendor_adapter("stripe", tmp_path)
    finally:
        codebase.prepare_vendor = original

    assert adapter is not None


def test_the_baked_cache_is_the_default_so_a_first_run_needs_no_flags():
    """The claim item 2 actually makes: a stranger runs `sync index --repo .` and gets their own
    code bound to a REAL vendor operation, with no network, no `gh` and no credential.

    A default of `.cache/specs` would be a cache nothing has staged on a fresh machine, so the
    vendor half would be silently empty -- call sites with no operation behind them, which is the
    half-answer this whole line of work exists to remove.
    """
    from sync.cli import build_parser

    args = build_parser().parse_args(["index", "--repo", "."])

    assert args.cache == "vendor-cache"


def test_the_repository_ships_a_baked_stripe_cache_that_matches_its_pin():
    """The artifact is committed, so this asserts the committed bytes rather than a rebuild.

    If it drifts from the corpus pin, the map that resolves symbols at first run is not the map
    the corpus was scored against, and two parts of the system would disagree about what a symbol
    means with nothing saying so.
    """
    import yaml

    from scripts.symbol_map_pin import symbol_map_digest

    baked = Path("vendor-cache/stripe")
    mapping = json.loads((baked / "symbols.json").read_text(encoding="utf-8"))
    pin = yaml.safe_load(Path("benchmark/corpus/symbol_map.yaml").read_text(encoding="utf-8"))

    assert symbol_map_digest(mapping) == pin["digest"]
    assert len(mapping) == pin["symbols"]
    assert read_provenance(baked)["tag"], "a baked cache with no tag cannot be aged"
