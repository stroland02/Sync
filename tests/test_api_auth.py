"""Tests for API authentication, shared-credential middleware, and bind security (B166)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from sync.api.auth import (
    AuthenticationMiddleware,
    configured_api_password,
    constant_time_match,
    extract_credential,
    validate_bind_security,
)
from sync.mcp.tools import GraphSurface
from tests.test_api_routes import FakeGraph, _build_app

FETCHED = datetime(2026, 7, 28, 7, 0, tzinfo=timezone.utc)


def test_constant_time_match():
    assert constant_time_match("correct-secret", "correct-secret") is True
    assert constant_time_match("wrong-secret", "correct-secret") is False
    assert constant_time_match("", "correct-secret") is False
    assert constant_time_match("correct-secret", "") is False
    assert constant_time_match("", "") is False


def test_extract_credential_bearer():
    assert extract_credential("Bearer my-secret-token") == "my-secret-token"
    assert extract_credential("bearer   token-with-spaces  ") == "token-with-spaces"
    assert extract_credential("Bearer") is None
    assert extract_credential(None) is None


def test_extract_credential_basic():
    # user:password
    encoded = base64.b64encode(b"admin:my-secret-password").decode("utf-8")
    assert extract_credential(f"Basic {encoded}") == "my-secret-password"

    # password only (:password)
    encoded_nopass = base64.b64encode(b":my-secret-password").decode("utf-8")
    assert extract_credential(f"Basic {encoded_nopass}") == "my-secret-password"

    # invalid base64
    assert extract_credential("Basic not_valid_base64!!!") is None


def test_validate_bind_security(monkeypatch):
    # Loopback bindings are always allowed even without a password
    validate_bind_security("127.0.0.1", None)
    validate_bind_security("localhost", None)
    validate_bind_security("::1", None)

    # Non-loopback binding with password configured is allowed
    validate_bind_security("0.0.0.0", "my-secret-password")
    validate_bind_security("192.168.1.100", "my-secret-password")

    # Non-loopback binding without password raises ValueError
    monkeypatch.delenv("SYNC_API_INSECURE", raising=False)
    with pytest.raises(ValueError, match="Refusing to bind 0.0.0.0 without authentication"):
        validate_bind_security("0.0.0.0", None)

    with pytest.raises(ValueError, match="Refusing to bind 192.168.1.100 without authentication"):
        validate_bind_security("192.168.1.100", "")

    # Insecure override allows non-loopback without password
    monkeypatch.setenv("SYNC_API_INSECURE", "i-understand")
    validate_bind_security("0.0.0.0", None)


def test_api_routes_require_auth_when_configured():
    secret = "test-cluster-secret-1234"
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    app = _build_app(surface=surface, api_password=secret)
    client = TestClient(app)

    # Unauthenticated GET /api/overview
    r = client.get("/api/overview")
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}
    assert "Basic realm" in r.headers.get("WWW-Authenticate", "")

    # Unauthenticated POST /api/repos/r/context
    r = client.post("/api/repos/r/context", json={"body": "test"})
    assert r.status_code == 401
    assert r.json() == {"error": "unauthorized"}

    # Invalid credential
    r = client.get("/api/overview", headers={"Authorization": "Bearer wrong-pass"})
    assert r.status_code == 401

    # Valid Bearer credential
    r = client.get("/api/overview", headers={"Authorization": f"Bearer {secret}"})
    assert r.status_code == 200

    # Valid Basic credential
    basic_header = base64.b64encode(f":{secret}".encode("utf-8")).decode("utf-8")
    r = client.get("/api/overview", headers={"Authorization": f"Basic {basic_header}"})
    assert r.status_code == 200

    # Valid POST with auth
    r = client.post(
        "/api/repos/r/context",
        json={"body": "valid context"},
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert r.status_code == 200


def test_api_routes_permit_unauthenticated_when_not_configured():
    surface = GraphSurface(FakeGraph(), feed_fetched_at=FETCHED)
    app = _build_app(surface=surface, api_password=None)
    client = TestClient(app)

    r = client.get("/api/overview")
    assert r.status_code == 200
