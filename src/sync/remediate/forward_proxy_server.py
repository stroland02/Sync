"""The socket wiring around `forward_proxy.build_forward_request`.

`ANTHROPIC_BASE_URL` points a sandboxed container's `claude` CLI at this server, so it is the
request's real destination -- not a `HTTPS_PROXY`-style tunnel relay -- and terminates the
connection itself rather than blindly forwarding an opaque TLS stream. That is what makes
reading `self.path` as the raw request-target meaningful: an ASGI server (this project's usual
`starlette`/`uvicorn` stack) normalises a request's target before an application ever sees it,
which would quietly discard the one signal `build_forward_request` needs to catch a client that
tries to use this as an ordinary forward proxy -- an absolute-URI request line naming a different
host. `http.server.BaseHTTPRequestHandler` hands over the request line exactly as the client sent
it, which is the property this module needs and the reason it does not use this project's usual
web stack.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator

import httpx

from sync.remediate.forward_proxy import DisallowedTarget, ProxyConfig, build_forward_request

# Headers that describe the hop between two specific parties rather than the message itself --
# forwarding them verbatim would either lie about this hop's own framing (content-length,
# transfer-encoding, connection) or leak nothing useful (host, the incoming request's own).
_HOP_BY_HOP = frozenset({"content-length", "transfer-encoding", "connection", "host"})


def _make_handler(config: ProxyConfig) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        # BaseHTTPRequestHandler defaults to advertising HTTP/1.0, which disables persistent
        # connections regardless of what a client sends -- one TCP handshake per request for
        # the length of a patch attempt's whole model turn. HTTP/1.1 is what the class actually
        # implements either way; this only changes which version it claims.
        protocol_version = "HTTP/1.1"

        def _handle(self) -> None:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length) if length else b""
            incoming_headers = {
                name: value
                for name, value in self.headers.items()
                if name.lower() not in _HOP_BY_HOP
            }
            try:
                forwarded = build_forward_request(self.command, self.path, incoming_headers, config)
            except DisallowedTarget:
                # The refusal's own message is never sent back over the wire: this server's
                # response reaches the container it is refusing, and DisallowedTarget's whole
                # point is not to hand the credential-adjacent details of a refusal to the one
                # side that should not be trusted with them.
                self.send_response(403)
                self.send_header("content-length", "0")
                self.end_headers()
                return

            upstream_response = httpx.request(
                self.command, forwarded.url, headers=forwarded.headers, content=body, timeout=60.0,
            )
            self.send_response(upstream_response.status_code)
            for name, value in upstream_response.headers.items():
                if name.lower() in _HOP_BY_HOP:
                    continue
                self.send_header(name, value)
            self.send_header("content-length", str(len(upstream_response.content)))
            self.end_headers()
            self.wfile.write(upstream_response.content)

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

        def do_PUT(self) -> None:
            self._handle()

        def do_DELETE(self) -> None:
            self._handle()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            pass  # BaseHTTPRequestHandler logs every request to stderr by default; silence it.

    return _Handler


@contextmanager
def running_proxy(
    config: ProxyConfig, host: str = "127.0.0.1", port: int = 0,
) -> Iterator[str]:
    """Starts the proxy on a background thread, yields its base URL, and guarantees shutdown.

    `port=0` (the default) asks the OS for a free port, the same reason `ephemeral_container`
    generates its own container name rather than taking one from a caller -- a fixed port is one
    concurrent test or one concurrent patch attempt away from colliding with another. Bound to
    `127.0.0.1` by default: this process is meant to be reached from inside the isolated network
    a sandboxed container shares with nothing else, not from the wider host network, and a caller
    that genuinely needs the container-reachable address names it explicitly.
    """
    server = ThreadingHTTPServer((host, port), _make_handler(config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        bound_host, bound_port = server.server_address[:2]
        yield f"http://{bound_host}:{bound_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
