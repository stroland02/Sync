"""Starts the forward proxy inside its own container. B97 Decision 1, the proxy's half.

Copied beside this script at attempt-start time, the same way `driver.py`'s docstring
describes for the sandboxed container's three files: `forward_proxy.py` and
`forward_proxy_server.py` from `src/sync/remediate/`, one source, never a duplicate.

Reads its configuration from environment variables the host sets on this container alone --
never from a file, and never from the sandboxed container's own environment, which is the whole
point of the proxy existing. `SYNC_PROXY_CREDENTIAL` is the real Anthropic credential; it is set
here and nowhere the agent's own container can read it.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from typing import Callable

from forward_proxy import ProxyConfig
from forward_proxy_server import running_proxy


def serve_until(config: ProxyConfig, should_stop: Callable[[], bool], *, host: str, port: int) -> None:
    """Runs the proxy until `should_stop()` says to, checked on a short poll -- separated from
    `main()` so a test can stop this deterministically without depending on OS signal delivery,
    which Windows (this repository's dev host) does not honour the same way the sandbox's real
    Linux container does.
    """
    with running_proxy(config, host=host, port=port) as base_url:
        print(f"proxy listening at {base_url}, forwarding to {config.upstream}", flush=True)
        while not should_stop():
            time.sleep(0.1)


def main() -> int:
    # Read here, not at module level: a container entrypoint only ever runs `main()` once with
    # its real environment already set, but reading at import time would bind these before a
    # test's `monkeypatch.setenv` had a chance to run, silently testing the defaults instead of
    # what was configured.
    upstream = os.environ.get("SYNC_PROXY_UPSTREAM", "https://api.anthropic.com")
    credential_header = os.environ.get("SYNC_PROXY_CREDENTIAL_HEADER", "x-api-key")
    port = int(os.environ.get("SYNC_PROXY_PORT", "8080"))

    credential = os.environ.get("SYNC_PROXY_CREDENTIAL")
    if not credential:
        print("SYNC_PROXY_CREDENTIAL is not set; refusing to start with no credential to inject", file=sys.stderr)
        return 1

    config = ProxyConfig(
        upstream=upstream, credential_header=credential_header, credential_value=credential,
    )

    stop = False

    def handle_term(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, handle_term)

    serve_until(config, lambda: stop, host="0.0.0.0", port=port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
