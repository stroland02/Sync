"""Tests for indexing arbitrary codebases with multiple languages and vendors."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sync.core import CallSite, RepoRef
from sync.index.codebase import CodebaseIndexReport, index_codebase
from sync.signals.stripe.symbols import build_symbol_map

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


