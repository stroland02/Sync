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
import zipfile
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


def test_the_two_licence_copies_cannot_drift_apart():
    """`src/LICENSE` is a second copy of the repository's, and this is what makes it safe.

    It has to be a copy: PEP 639 forbids `..` in a `license-files` glob, so the text must sit
    under `src/`, which is the core distribution's project root. Generating it at build time was
    measured and is worse -- `src` is a workspace member, so an absent file fails `uv run` and a
    fresh clone could not run this suite at all.

    What makes two copies of a licence dangerous is that they diverge and the wheel ships a
    stale one, which looks correct and is not. Byte equality asserted on every run closes that:
    a divergence cannot survive one `pytest`, and this costs no build.
    """
    root = (REPO_ROOT / "LICENSE").read_bytes()
    packaged = (REPO_ROOT / "src" / "LICENSE").read_bytes()

    assert packaged == root, (
        "src/LICENSE has drifted from the repository's LICENSE; the core wheel would ship the "
        "stale one"
    )
    assert b"Apache License" in root


def test_the_built_core_wheel_carries_the_licence_and_a_description(tmp_path):
    """What a published `sync-core` asserts, and what it would actually deliver.

    Apache-2.0 section 4(a) requires a recipient to receive a copy of the License, and the wheel
    named the licence in its metadata while carrying none of its text -- so every adapter author
    CONTRIBUTING.md sends here would have received a package asserting a licence they were never
    given. That is a legal question rather than an engineering one, which is why it is asserted
    on the built artifact rather than on the configuration that is supposed to produce it.

    The description is the second half and a different kind of defect: a blank PyPI page is the
    same adoption failure the split was done to avoid, one step later.

    This reuses the wheel the test above already builds rather than building a second one. The
    suite is large and already pays for one core build; it must not pay for two.
    """
    uv = shutil.which("uv")
    assert uv is not None, "uv not found on PATH"

    built = _run(
        [uv, "build", "--package", "sync-core", "--wheel", "--out-dir", str(tmp_path)],
        cwd=REPO_ROOT,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    (wheel,) = tmp_path.glob("sync_core-*.whl")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        # Not the `licenses/` directory entry, which is in the list too and reads as empty --
        # matching it would assert the licence is present against a zero-byte string.
        licences = [name for name in names if "/licenses/" in name and not name.endswith("/")]
        assert licences, f"the wheel ships no licence text: {names}"
        assert b"Apache License" in archive.read(licences[0])

        metadata = archive.read("sync_core-0.1.0.dist-info/METADATA").decode("utf-8")

    # A metadata file is headers, one blank line, then the long description -- the same framing
    # as an email, which is what `Metadata-Version` inherits.
    headers, _, body = metadata.partition("\n\n")

    # Named in the metadata as well as present in the archive: a file nothing points at is a
    # file an installer will not surface, and `pip show -f` is where a recipient looks.
    assert "License-File: LICENSE" in headers
    assert "License-Expression: Apache-2.0" in headers

    # A body PyPI can render. Without the content type the page shows the raw source, which is
    # not much better than blank.
    assert "Description-Content-Type: text/markdown" in headers
    assert body.strip(), "the wheel carries no long description, so its page would be blank"

    # What the page has to tell somebody who arrived at it. Asserted on substance rather than on
    # length, because a description that says nothing renders as well as one that does.
    assert "CONTRIBUTING.md" in body, "the page does not say where the authoring guide is"
    assert "check_vendor_adapter" in body, "the page does not name the conformance kit"


def test_the_runtime_wheel_still_excludes_the_core_package():
    """The two distributions must not own the same files, or uninstalling either takes core out
    from under the other.

    Asserted on the configuration rather than on a built artifact, deliberately. Building the
    runtime wheel is the expensive one and this suite already pays for a core build; the release
    command in `docs/releasing-sync-core.md` builds both and checks the artifact itself, which
    is where a check that costs a build belongs.
    """
    import tomllib

    manifest = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert manifest["tool"]["uv"]["build-backend"]["wheel-exclude"] == ["core/**"]
