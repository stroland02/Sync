"""B97's forward proxy, first slice: the pure request transform.

Per `docs/superpowers/specs/2026-08-17-sync-b97-forward-proxy-design.md`, the container is
pointed at this proxy via `ANTHROPIC_BASE_URL` rather than a `HTTPS_PROXY`-style CONNECT
tunnel -- so the proxy is the request's real destination and can read it in plain text, and it
always forwards to the one configured upstream regardless of what the container's request
claims. That is the property this file proves: a relative target reaches the configured
upstream, an absolute-URI target (the classic "use me as a general proxy" trick) is refused
outright, and whatever credential-shaped header the container's own request carried is replaced
by the real one rather than trusted -- the container never gets to assert its own.

No socket, no server, no Docker. This is the transform a server built on top of it would call
per request; the server itself is a separate, later unit.
"""

from __future__ import annotations

import pytest

from sync.remediate.forward_proxy import DisallowedTarget, ProxyConfig, build_forward_request

CONFIG = ProxyConfig(
    upstream="https://api.anthropic.com",
    credential_header="x-api-key",
    credential_value="sk-real-proxy-held-credential",
)


def test_a_relative_target_reaches_the_configured_upstream():
    forwarded = build_forward_request("POST", "/v1/messages", {}, CONFIG)
    assert forwarded.url == "https://api.anthropic.com/v1/messages"


def test_a_relative_target_with_no_leading_slash_still_joins_cleanly():
    forwarded = build_forward_request("POST", "v1/messages", {}, CONFIG)
    assert forwarded.url == "https://api.anthropic.com/v1/messages"


def test_an_absolute_uri_target_is_refused():
    """The trick a general-purpose forward proxy would honour: a client puts the destination
    in the request line itself rather than relying on the proxy's own configured upstream.
    Accepting it would make this proxy reachable-anywhere, which is exactly the boundary
    `ANTHROPIC_BASE_URL` and this design exist to remove.
    """
    for absolute in ("http://attacker.example/collect", "https://attacker.example/collect"):
        with pytest.raises(DisallowedTarget):
            build_forward_request("POST", absolute, {}, CONFIG)


def test_the_refusal_does_not_quote_the_credential():
    """Same discipline as `UntrustedTextRefused` in `sync.remediate.untrusted`: an error
    message is data that can end up somewhere it should not, so it never carries a secret.
    """
    try:
        build_forward_request("POST", "http://attacker.example/", {}, CONFIG)
    except DisallowedTarget as exc:
        assert CONFIG.credential_value not in str(exc)
    else:
        pytest.fail("expected DisallowedTarget")


def test_the_containers_own_credential_header_is_replaced_not_trusted():
    """Defense in depth. Nothing in this design should ever let the container assert its own
    credential value, but if some other layer let a request through carrying one anyway, the
    proxy overwrites it rather than forwarding whatever the container claimed.
    """
    forwarded = build_forward_request(
        "POST", "/v1/messages", {"x-api-key": "sk-forged-by-the-container"}, CONFIG,
    )
    assert forwarded.headers["x-api-key"] == CONFIG.credential_value


def test_the_credential_header_match_is_case_insensitive():
    forwarded = build_forward_request(
        "POST", "/v1/messages", {"X-API-Key": "sk-forged-by-the-container"}, CONFIG,
    )
    values = [v for k, v in forwarded.headers.items() if k.lower() == "x-api-key"]
    assert values == [CONFIG.credential_value]


def test_other_headers_pass_through_unchanged():
    forwarded = build_forward_request(
        "POST", "/v1/messages", {"content-type": "application/json"}, CONFIG,
    )
    assert forwarded.headers["content-type"] == "application/json"


def test_the_forwarded_headers_are_a_new_dict_not_the_callers_own():
    """A caller reusing its own headers dict for the next request must not find it mutated by
    this call -- and a caller building a real server per request cannot audit that by hand.
    """
    original = {"content-type": "application/json"}
    build_forward_request("POST", "/v1/messages", original, CONFIG)
    assert original == {"content-type": "application/json"}
