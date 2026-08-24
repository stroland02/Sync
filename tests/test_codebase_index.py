"""Tests for indexing arbitrary codebases with multiple languages and vendors."""

from __future__ import annotations

import logging
import tempfile
import json
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.index.codebase import CodebaseIndexReport, index_codebase
from sync.signals.generated.symbols_stripe_openapi import build_symbol_map

STRIPE_SPEC = {
    "paths": {
        "/v1/charges": {"post": {"operationId": "PostCharges"}},
        "/v1/payment_intents": {"post": {"operationId": "PostPaymentIntents"}},
        "/v1/elements": {"post": {"operationId": "PostElements"}},
    }
}


@pytest.fixture
def staged_cache(tmp_path):
    cache = tmp_path / "specs"
    cache.mkdir(parents=True, exist_ok=True)
    stripe_cache = cache / "stripe"
    stripe_cache.mkdir(parents=True, exist_ok=True)
    map_path = stripe_cache / "symbols.json"
    map_path.write_text(json.dumps(build_symbol_map(STRIPE_SPEC)), encoding="utf-8")
    return cache


def test_index_codebase_on_arbitrary_typescript_repo(tmp_path, staged_cache):
    repo_dir = tmp_path / "my_arbitrary_ts_app"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Manifest declaring stripe
    pkg_json = repo_dir / "package.json"
    pkg_json.write_text(
        json.dumps({
            "name": "my-arbitrary-app",
            "dependencies": {
                "stripe": "^14.0.0",
            },
        }),
        encoding="utf-8",
    )

    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    # 1. TypeScript file with stripe call
    (src_dir / "billing.ts").write_text(
        """\
import Stripe from 'stripe';
const stripe = new Stripe('sk_test');
export async function pay() {
    const charge = await stripe.charges.create({
        amount: 2000,
        currency: 'usd',
    });
    return charge.id;
}
""",
        encoding="utf-8",
    )

    # 2. TSX file with stripe call
    (src_dir / "Checkout.tsx").write_text(
        """\
import React from 'react';
import Stripe from 'stripe';
const stripe = new Stripe('sk_test');
export function CheckoutButton() {
    const handlePay = () => {
        stripe.paymentIntents.create({
            amount: 5000,
            currency: 'usd',
        });
    };
    return <button onClick={handlePay}>Pay</button>;
}
""",
        encoding="utf-8",
    )

    # 3. Wrapper file (unbound import)
    (src_dir / "stripe_wrapper.ts").write_text(
        """\
import Stripe from 'stripe';
export const stripeClient = new Stripe('sk_test');
""",
        encoding="utf-8",
    )

    report = index_codebase(repo_dir, cache_dir=staged_cache)

    assert isinstance(report, CodebaseIndexReport)
    assert report.repo.repo_id == "my-arbitrary-app"
    assert "stripe" in report.vendors
    assert len(report.call_sites) >= 2

    operations = {cs.operation_id for cs in report.call_sites}
    assert "PostCharges" in operations
    assert "PostPaymentIntents" in operations

    # Wrapper file is captured in unbound imports
    assert any("stripe_wrapper.ts" in p for p in report.unbound_import_paths)


def test_index_codebase_on_arbitrary_python_repo(tmp_path, staged_cache):
    repo_dir = tmp_path / "my_arbitrary_py_app"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # Manifest declaring stripe
    (repo_dir / "pyproject.toml").write_text(
        """\
[project]
name = "my-py-app"
version = "0.1.0"
dependencies = [
    "stripe>=7.0.0",
]
""",
        encoding="utf-8",
    )

    src_dir = repo_dir / "app"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "payments.py").write_text(
        """\
import stripe

def create_charge():
    return stripe.charges.create(
        amount=1000,
        currency="usd",
    )
""",
        encoding="utf-8",
    )

    report = index_codebase(repo_dir, cache_dir=staged_cache)

    assert isinstance(report, CodebaseIndexReport)
    assert report.repo.repo_id == "my_arbitrary_py_app"
    assert "stripe" in report.vendors
    assert len(report.call_sites) >= 1
    assert any(cs.operation_id == "PostCharges" for cs in report.call_sites)


def test_index_codebase_persists_to_store(tmp_path, staged_cache):
    from sync.graph.store import GraphStore

    # Mock store or in-memory store check
    repo_dir = tmp_path / "app_with_store"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text(
        json.dumps({"name": "app-store-test", "dependencies": {"stripe": "14.0.0"}}),
        encoding="utf-8",
    )
    (repo_dir / "index.ts").write_text(
        """\
import Stripe from 'stripe';
const s = new Stripe('k');
s.charges.create({ amount: 100, currency: 'usd' });
""",
        encoding="utf-8",
    )

    class FakeStore:
        def __init__(self):
            self.replaced = {}

        def replace_call_sites(self, repo_id, sites):
            self.replaced[repo_id] = list(sites)
            return [f"cs-{i}" for i in range(len(sites))]


        # The scan opens and closes an `index_run` row around the pass; a double that
        # indexes has to accept both, or the store surface it stands in for is a
        # narrower thing than the one the CLI actually calls.
        def start_index_run(self, repo_id, *, started_at):
            return None

        def finish_index_run(self, repo_id, *, started_at, finished_at, call_sites):
            return None
    fake_store = FakeStore()
    report = index_codebase(repo_dir, store=fake_store, cache_dir=staged_cache)

    assert "app-store-test" in fake_store.replaced
    assert len(fake_store.replaced["app-store-test"]) == len(report.call_sites)


def test_index_codebase_multi_vendor_with_model_literals(tmp_path, staged_cache):
    repo_dir = tmp_path / "multi_vendor_app"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text(
        json.dumps({
            "name": "multi-vendor-app",
            "dependencies": {
                "stripe": "14.0.0",
                "@anthropic-ai/sdk": "^0.20.0",
            },
        }),
        encoding="utf-8",
    )
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "payments.ts").write_text(
        """\
import Stripe from 'stripe';
const stripe = new Stripe('sk');
stripe.charges.create({ amount: 500, currency: 'usd' });
""",
        encoding="utf-8",
    )

    (src_dir / "ai.ts").write_text(
        """\
export const config = {
    model: "claude-3-5-sonnet-20241022",
    max_tokens: 1024,
};
""",
        encoding="utf-8",
    )

    report = index_codebase(repo_dir, cache_dir=staged_cache)
    assert report.repo.repo_id == "multi-vendor-app"
    assert "stripe" in report.vendors

    ops = {cs.operation_id for cs in report.call_sites}
    assert "PostCharges" in ops
    assert "claude-3-5-sonnet-20241022" in ops


def test_index_codebase_unreadable_file_recorded_in_report(tmp_path, staged_cache):
    repo_dir = tmp_path / "app_with_binary"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text(
        json.dumps({"name": "app-binary-test", "dependencies": {"stripe": "14.0.0"}}),
        encoding="utf-8",
    )
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)

    (src_dir / "good.ts").write_text(
        "import Stripe from 'stripe'; const s = new Stripe('k'); s.charges.create({ amount: 10, currency: 'usd' });",
        encoding="utf-8",
    )
    # Write invalid UTF-8 bytes to a .ts file
    (src_dir / "bad_binary.ts").write_bytes(b"\xff\xfe\x00\x00\x12\x34")

    report = index_codebase(str(repo_dir), cache_dir=staged_cache)
    assert len(report.call_sites) >= 1
    assert any("bad_binary.ts" in p for p in report.unread_paths)


def test_index_codebase_unindexed_language_repo(tmp_path):
    """An unindexed language (Go/Rust) repo produces a clean empty report with zero tracebacks."""
    repo_dir = tmp_path / "go_rust_repo"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "go.mod").write_text("module example.com/mygo\n\ngo 1.21\n", encoding="utf-8")
    (repo_dir / "main.go").write_text(
        'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Hello")\n}\n',
        encoding="utf-8",
    )
    (repo_dir / "Cargo.toml").write_text(
        '[package]\nname = "myrust"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    report = index_codebase(repo_dir)
    assert isinstance(report, CodebaseIndexReport)
    assert report.repo.repo_id == "go_rust_repo"
    assert report.vendors == ()
    assert report.call_sites == ()
    assert report.unbound_import_paths == ()
    assert report.unread_paths == ()


def test_index_codebase_zero_call_sites_repo(tmp_path, staged_cache):
    """A repo with declared dependencies but 0 call sites returns a clean report."""
    repo_dir = tmp_path / "zero_call_sites_app"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text(
        json.dumps({"name": "zero-calls", "dependencies": {"stripe": "14.0.0", "lodash": "^4.17.0"}}),
        encoding="utf-8",
    )
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "utils.ts").write_text("export function add(a: number, b: number) { return a + b; }", encoding="utf-8")

    report = index_codebase(repo_dir, cache_dir=staged_cache)
    assert report.repo.repo_id == "zero-calls"
    assert "stripe" in report.vendors
    assert report.call_sites == ()
    assert report.unbound_import_paths == ()


def test_index_codebase_missing_lockfile_and_unknown_framework(tmp_path, staged_cache):
    """A project with an unknown framework (e.g. Astro/Svelte) and no lockfile indexes without error."""
    repo_dir = tmp_path / "astro_framework_app"
    repo_dir.mkdir(parents=True, exist_ok=True)
    # Manifest has no lockfile (no package-lock.json, no yarn.lock, no pnpm-lock)
    (repo_dir / "package.json").write_text(
        json.dumps({
            "name": "astro-app",
            "dependencies": {
                "astro": "^4.0.0",
                "stripe": "^14.0.0",
            },
        }),
        encoding="utf-8",
    )
    src_dir = repo_dir / "src" / "pages"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "api.ts").write_text(
        """\
import Stripe from 'stripe';
const stripe = new Stripe('key');
export async function GET() {
    return stripe.charges.create({ amount: 100, currency: 'usd' });
}
""",
        encoding="utf-8",
    )

    report = index_codebase(repo_dir, cache_dir=staged_cache)
    assert report.repo.repo_id == "astro-app"
    assert "stripe" in report.vendors
    assert len(report.call_sites) == 1
    assert report.call_sites[0].operation_id == "PostCharges"




def test_an_unresolvable_vendor_yields_no_adapter_rather_than_a_fabricated_one():
    """The third of the coordinator's three, and the one that actually removes the defect class.

    A total load failure used to return `_FallbackIndexingAdapter`, which answered
    `operation_for_symbol` by inventing an operation id out of the symbol's own words --
    `CreateCharges` where the specification says `PostCharges`. That is worse than a crash: a
    finding built on it names an operation no vendor has, and a pull request would be opened
    against it. Making the invented name *correct* would have been the same move as making the
    field optional; the answer is not to answer.

    `index_codebase` already skips a vendor whose adapter is `None`, so the honest outcome was
    one line away the whole time: no adapter, no call sites for that vendor, and the report says
    which vendor it could not resolve.
    """
    import sync.index.codebase as codebase
    from sync.index.codebase import _load_or_create_vendor_adapter

    def _no_network(*args, **kwargs):
        raise RuntimeError("network refused")

    original = codebase.prepare_vendor
    codebase.prepare_vendor = _no_network
    try:
        adapter = _load_or_create_vendor_adapter("stripe", Path(tempfile.mkdtemp()))
    finally:
        codebase.prepare_vendor = original

    assert adapter is None


def test_no_fabricating_adapter_remains_in_the_module():
    """Deleted rather than left unused. A dead path still typechecks, still gets read, and still
    gets maintained by somebody who cannot tell it is dead -- and this one answered questions it
    was never qualified to answer."""
    import sync.index.codebase as codebase

    assert not hasattr(codebase, "_FallbackIndexingAdapter")


def test_an_explicitly_staged_per_vendor_cache_is_found(tmp_path, staged_cache):
    """The real adapter must load from a cache staged the way this repository stages one.

    `_load_or_create_vendor_adapter` looked only at the directory it was handed, while
    `_load_stripe` reads `<cache_dir>/symbols.json` and every caller stages
    `<cache_dir>/<vendor>/symbols.json` -- which is the layout the function's own discovery branch
    already expects when no directory is given. So the staged map was never found, `load_vendor`
    raised `FileNotFoundError`, and the code fell through to `prepare_vendor`, which **fetches the
    specification over the network**. On a runner with no network that times out and the silent
    fallback takes over, returning invented operation ids; on a fast connection it succeeds and
    the tests pass. That is the whole of the local-versus-CI difference.
    """
    import sync.index.codebase as codebase
    from sync.index.codebase import _load_or_create_vendor_adapter

    # The network is the escape hatch that hid this: with it available `prepare_vendor` fetches
    # the specification and the test passes for the wrong reason. Closed here, so the only route
    # to a real adapter is the staged cache -- which is the thing under test.
    def _no_network(*args, **kwargs):
        raise AssertionError("the indexer reached the network to resolve a vendor")

    original = codebase.prepare_vendor
    codebase.prepare_vendor = _no_network
    try:
        adapter = _load_or_create_vendor_adapter("stripe", staged_cache)
    finally:
        codebase.prepare_vendor = original

    assert adapter is not None, "the staged cache was not found, so no adapter loaded at all"


def test_the_real_adapter_answers_with_the_operation_the_spec_names(tmp_path, staged_cache):
    """And the reason the fallback must never stand in silently: it invents ids.

    The staged spec names `PostCharges`; the fallback would answer `CreateCharges`, which is an
    operation no vendor has. A finding built on it would open a pull request against an operation
    that does not exist -- worse than the crash it replaced, because it looks like an answer.
    """
    import sync.index.codebase as codebase
    from sync.index.codebase import _load_or_create_vendor_adapter

    def _no_network(*args, **kwargs):
        raise AssertionError("the indexer reached the network to resolve a vendor")

    original = codebase.prepare_vendor
    codebase.prepare_vendor = _no_network
    try:
        adapter = _load_or_create_vendor_adapter("stripe", staged_cache)
    finally:
        codebase.prepare_vendor = original
    ref = adapter.operation_for_symbol("stripe.charges.create")

    assert ref is not None
    assert ref.operation_id == "PostCharges"


def test_falling_back_says_why_rather_than_swallowing_the_reason(tmp_path, caplog):
    """Two nested bare `except Exception: pass` turned every load failure into a silent
    substitution, which is why no reason was ever reported and why this took a night to find.

    The fallback fabricates operation ids, so choosing it is a decision worth a line in the log
    naming both causes -- the load failure and the prepare failure. Loud first; then one run
    names the real problem instead of a week of bisecting.
    """
    import sync.index.codebase as codebase
    from sync.index.codebase import _load_or_create_vendor_adapter

    empty = tmp_path / "empty-cache"
    empty.mkdir()

    def _no_network(*args, **kwargs):
        raise RuntimeError("network refused")

    original = codebase.prepare_vendor
    codebase.prepare_vendor = _no_network
    try:
        with caplog.at_level(logging.WARNING):
            adapter = _load_or_create_vendor_adapter("stripe", empty)
    finally:
        codebase.prepare_vendor = original

    assert adapter is None
    text = caplog.text
    assert "stripe" in text
    # Both causes, because either alone leaves the reader guessing which half failed.
    assert "network refused" in text
    # And it says what follows from the failure, rather than only that one happened.
    assert "skipped" in text.lower()


def test_a_relative_cache_path_is_resolved_rather_than_left_to_the_working_directory(tmp_path):
    """`.cache/specs` resolves against the process's current directory, so which adapter loads
    depended on where the process happened to stand -- the order-dependence that made this look
    environmental. The candidates are absolute now, so the answer does not move with the CWD."""
    from sync.index.codebase import _cache_candidates

    candidates = _cache_candidates("stripe", None)

    assert candidates, "discovery must offer somewhere to look"
    assert all(c.is_absolute() for c in candidates), [str(c) for c in candidates]


def test_index_codebase_captures_a_bounded_snippet(tmp_path, staged_cache):
    """The pass that writes a call site captures the window around it -- the graph stores no
    path back to the checkout, so index time is the only moment the source is in hand."""
    repo_dir = tmp_path / "snippet_app"
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "package.json").write_text(
        json.dumps({"name": "snippet-app", "dependencies": {"stripe": "^14.0.0"}}),
        encoding="utf-8",
    )
    src_dir = repo_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "billing.ts").write_text(
        """import Stripe from 'stripe';
const stripe = new Stripe('sk_test');
export async function pay() {
    const charge = await stripe.charges.create({
        amount: 2000,
        currency: 'usd',
    });
    return charge.id;
}
""",
        encoding="utf-8",
    )

    report = index_codebase(repo_dir, cache_dir=staged_cache)

    site = next(cs for cs in report.call_sites if cs.operation_id == "PostCharges")
    assert site.snippet is not None
    assert site.snippet_start_line == max(1, site.line - 4)
    window = site.snippet.splitlines()
    # Bounded: at most the call line plus four each side.
    assert len(window) <= 9
    # The call line itself is inside the window, at the offset the start line implies.
    assert "charges.create" in window[site.line - site.snippet_start_line]
