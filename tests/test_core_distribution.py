"""`sync.core` has to be installable without the runtime, not merely separable from it.

`test_import_boundary.py` pins the two facts this rests on: core reaches no sibling package, and
it imports one third-party distribution. Neither of those makes core *installable* on its own --
that is a packaging property, and the only honest way to check it is to build the distribution,
install it into an environment that holds nothing else, and use it there.

So this test does that rather than asserting it. What it proves is the sentence CONTRIBUTING.md
makes to adapter authors: an adapter "does not inherit Postgres, LangGraph, or anything else in
this repository's dependency tree".
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The runtime dependencies an adapter author must not inherit, by import name rather than by
# distribution name -- `psycopg[binary]` installs as `psycopg`, and an author hits the import.
RUNTIME_ONLY_MODULES = [
    "ast_grep_py",
    "claude_agent_sdk",
    "cryptography",
    "langgraph",
    "langgraph.checkpoint",
    "mcp",
    "psycopg",
    "tree_sitter",
    "tree_sitter_python",
    "tree_sitter_typescript",
    "yaml",
]

# The runtime's own packages. Absent for a different reason -- not a dependency that failed to
# arrive, but code the core wheel must not be shipping in the first place.
SIBLING_PACKAGES = [
    "sync.cli",
    "sync.detect",
    "sync.forge",
    "sync.graph",
    "sync.index",
    "sync.remediate",
    "sync.route",
    "sync.signals",
    "sync.telemetry",
]

# Runs inside the isolated environment, so it may import nothing this repository provides beyond
# the core distribution itself. It reports rather than asserts: a failure here should name what
# the environment actually contained.
PROBE = '''
import importlib.metadata
import importlib.util
import json

import sync.core
from sync.core import Detector, LanguageAdapter, Remediator, RequestCorrelator, VendorAdapter
from sync.core.conformance import ConformanceFailure, check_vendor_adapter
from sync.core.models import OperationRef

RUNTIME_ONLY_MODULES = {runtime_only!r}
SIBLING_PACKAGES = {siblings!r}


class _Adapter:
    """The smallest thing CONTRIBUTING.md tells an author to write."""

    vendor_id = "probe"

    def operation_for_symbol(self, symbol, *, language=None):
        if symbol == "probe.things.create":
            return OperationRef(
                operation_id="createThing", http_method="POST", path="/v1/things"
            )
        return None

    def fetch_changes(self, since, until):
        return []


class _BrokenAdapter(_Adapter):
    vendor_id = ""


try:
    check_vendor_adapter(_Adapter(), known_symbol="probe.things.create")
except ConformanceFailure as exc:
    accepted_a_conforming_adapter = False
    rule_it_broke_on = str(exc)
else:
    accepted_a_conforming_adapter = True
    rule_it_broke_on = ""

try:
    check_vendor_adapter(_BrokenAdapter(), known_symbol="probe.things.create")
except ConformanceFailure:
    refused_a_broken_adapter = True
else:
    refused_a_broken_adapter = False


def _absent(module):
    try:
        return importlib.util.find_spec(module) is None
    except ModuleNotFoundError:
        return True


print(json.dumps({{
    "protocols": sorted(
        protocol.__name__
        for protocol in (
            Detector, LanguageAdapter, Remediator, RequestCorrelator, VendorAdapter
        )
    ),
    "accepted_a_conforming_adapter": accepted_a_conforming_adapter,
    "rule_it_broke_on": rule_it_broke_on,
    "refused_a_broken_adapter": refused_a_broken_adapter,
    "distributions": sorted(
        dist.metadata["Name"] for dist in importlib.metadata.distributions()
    ),
    "present_runtime_modules": [m for m in RUNTIME_ONLY_MODULES if not _absent(m)],
    "present_sibling_packages": [m for m in SIBLING_PACKAGES if not _absent(m)],
}}))
'''


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_the_core_distribution_installs_and_works_without_the_runtime(tmp_path):
    uv = shutil.which("uv")
    assert uv is not None, "uv not found on PATH"

    built = _run(
        [uv, "build", "--package", "sync-core", "--wheel", "--out-dir", str(tmp_path)],
        cwd=REPO_ROOT,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheels = list(tmp_path.glob("sync_core-*.whl"))
    assert len(wheels) == 1, f"expected one core wheel, got {[w.name for w in wheels]}"

    venv = tmp_path / "venv"
    created = _run([uv, "venv", str(venv), "--python", "3.12"], cwd=tmp_path)
    assert created.returncode == 0, created.stdout + created.stderr
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")

    installed = _run([uv, "pip", "install", "--python", str(python), str(wheels[0])], cwd=tmp_path)
    assert installed.returncode == 0, installed.stdout + installed.stderr

    probe = tmp_path / "probe.py"
    probe.write_text(
        PROBE.format(runtime_only=RUNTIME_ONLY_MODULES, siblings=SIBLING_PACKAGES),
        encoding="utf-8",
    )
    result = _run([str(python), str(probe)], cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)

    assert report["protocols"] == [
        "Detector", "LanguageAdapter", "Remediator", "RequestCorrelator", "VendorAdapter"
    ]
    # Both directions, because a kit that certifies everything is indistinguishable from a kit
    # that ran, and this environment is the one place nobody would notice.
    assert report["accepted_a_conforming_adapter"], report["rule_it_broke_on"]
    assert report["refused_a_broken_adapter"], "the kit certified an adapter with no vendor_id"

    assert report["present_runtime_modules"] == [], (
        "the core distribution dragged in the runtime: "
        + ", ".join(report["present_runtime_modules"])
    )
    assert report["present_sibling_packages"] == [], (
        "the core wheel ships the runtime's own code: "
        + ", ".join(report["present_sibling_packages"])
    )
    assert "sync" not in report["distributions"], (
        "installing sync-core installed the whole product: " + ", ".join(report["distributions"])
    )
