"""`docker/patch-sandbox/run_proxy.py`, the proxy container's own entrypoint.

Loaded the same way `tests/test_docker_driver.py` loads `driver.py`: from its file path, with
`forward_proxy.py`/`forward_proxy_server.py` found via `sys.path` pointed at their one real
location in `src/sync/remediate/`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REMEDIATE = _REPO_ROOT / "src" / "sync" / "remediate"
_RUN_PROXY_PATH = _REPO_ROOT / "docker" / "patch-sandbox" / "run_proxy.py"

if str(_REMEDIATE) not in sys.path:
    sys.path.insert(0, str(_REMEDIATE))


def _load_run_proxy():
    spec = importlib.util.spec_from_file_location("run_proxy", _RUN_PROXY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_proxy = _load_run_proxy()


def test_refuses_to_start_with_no_credential(monkeypatch, capsys):
    monkeypatch.delenv("SYNC_PROXY_CREDENTIAL", raising=False)

    exit_code = run_proxy.main()

    assert exit_code == 1
    assert "SYNC_PROXY_CREDENTIAL" in capsys.readouterr().err


def test_serve_until_runs_a_real_listening_proxy_and_stops_on_command():
    """A real listening server, not a mock -- the same discipline `test_forward_proxy_server.py`
    already holds `running_proxy` to. Stopped through `should_stop` rather than an OS signal:
    `main()`'s own SIGTERM wiring is for the real Linux container this runs in, and is not
    portably testable on this Windows dev host, which does not deliver `SIGTERM` to a same-
    process handler the way Linux does.
    """
    from sync.remediate.forward_proxy import ProxyConfig

    config = ProxyConfig(upstream="https://example.invalid", credential_header="x-api-key", credential_value="k")
    calls = {"n": 0}

    def should_stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 2

    run_proxy.serve_until(config, should_stop, host="127.0.0.1", port=0)

    assert calls["n"] > 2
