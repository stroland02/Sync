"""B97's forward proxy: the component that lets a `network`-isolated container reach
Anthropic without ever holding the credential that authenticates it there.

`docs/superpowers/specs/2026-08-17-sync-b97-forward-proxy-design.md` is the design this
implements, and the reasoning for its shape lives there rather than here. In short: the
container is pointed at this process via `ANTHROPIC_BASE_URL`, not a `HTTPS_PROXY`-style
`CONNECT` tunnel, so this proxy is the request's real destination and can read it in plain
text rather than blindly relaying an opaque TLS stream. That is what makes credential
injection possible at all -- a tunnel relay never sees inside what it forwards.

This module is the pure request transform only. A caller reads the incoming request off a
real socket, calls `build_forward_request`, and sends the result upstream with its own TLS
client; nothing here opens a socket, and nothing here is Docker-specific. The server that
wires this to a real port, and the container-side network topology that makes this the only
thing a sandboxed container can reach, are later units -- `sandbox.py`'s own `ephemeral_container`
and `probe_connect` are what prove the network half once this exists to be reached.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyConfig:
    """What one running proxy is configured with.

    `credential_value` is deliberately never included in this dataclass's use anywhere a log
    or an error message might render it -- see `DisallowedTarget` below, which is refused
    before the credential is ever attached, and never after.
    """

    upstream: str
    credential_header: str
    credential_value: str


@dataclass(frozen=True)
class ForwardRequest:
    """What this proxy actually sends upstream, in the shape an HTTP client wants it."""

    url: str
    headers: dict[str, str]


class DisallowedTarget(RuntimeError):
    """The request named a destination other than the configured upstream."""


def build_forward_request(
    method: str,
    raw_target: str,
    headers: dict[str, str],
    config: ProxyConfig,
) -> ForwardRequest:
    """The request this proxy sends upstream for one incoming request.

    `raw_target` is the request line's target as the container's HTTP client sent it. A
    relative path reaches `config.upstream` and nothing else -- this proxy has exactly one
    forward destination, by construction, never a per-request choice. An absolute-URI target
    (`http://` or `https://` naming a different host) is refused outright: accepting one would
    make this an ordinary forward proxy the container could point anywhere, which is precisely
    the boundary `ANTHROPIC_BASE_URL` and this whole design exist to remove rather than merely
    narrow.

    `config.credential_value` replaces whatever the incoming request already carried under
    `config.credential_header`, case-insensitively, rather than trusting it. The container
    never gets to assert its own value for this header, even if some other layer let a
    request carrying one reach this far.
    """
    if raw_target.startswith(("http://", "https://")):
        raise DisallowedTarget(
            f"absolute-URI target refused ({method} {raw_target!r}): this proxy forwards to "
            f"one configured upstream only, never to a destination a request names"
        )
    url = config.upstream.rstrip("/") + "/" + raw_target.lstrip("/")
    forwarded_headers = {
        name: value
        for name, value in headers.items()
        if name.lower() != config.credential_header.lower()
    }
    forwarded_headers[config.credential_header] = config.credential_value
    return ForwardRequest(url=url, headers=forwarded_headers)
