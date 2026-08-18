"""The setup checklist: what the full loop needs, each item measured rather than assumed.

The loop is index -> detect -> remediate -> verify -> pull request, and each stage has a
prerequisite a fresh install may not hold: a staged vendor specification, an indexed codebase,
the `gh` CLI authenticated against the forge, the `claude` CLI for the agent tier, a git remote
to address, and a merge policy for what happens after the pull request opens.

Every item reports one of three states and never a figure over them:

- ``ready``   -- probed, and the prerequisite holds.
- ``missing`` -- probed, and it does not; ``fix`` names the command or screen that supplies it.
- ``unanswered`` -- the probe itself failed, which is a different fact from a missing
  prerequisite and is reported as its own state rather than collapsed into either.

**No composite.** A count of ready items over six would average "we could not check" onto the
same axis as "we checked and it is missing", which is the collapse this console refuses
everywhere else. The console renders the list; a reader sees what stands and what does not.

Probes shell out to the CLIs the loop itself shells out to, with the encoding discipline
`CLAUDE.md` binds: explicit UTF-8, ``errors="replace"``, and ``PYTHONIOENCODING`` in the child's
environment, because a probe that crashes on an accented username would report the wrong state
for the right credential.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from sync.graph.store import GraphStore


def _run(command: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _item(item_id: str, label: str, state: str, detail: str, fix: str | None = None) -> dict:
    return {"id": item_id, "label": label, "state": state, "detail": detail, "fix": fix}


def _forge_item() -> dict:
    gh = shutil.which("gh")
    if gh is None:
        return _item(
            "forge", "Forge access (gh CLI)", "missing",
            "The gh CLI is not on PATH. The loop reads vendor specifications, watches CI and "
            "opens pull requests through it.",
            "https://cli.github.com — install, then `gh auth login`",
        )
    probe = _run([gh, "auth", "status"])
    if probe is None:
        return _item(
            "forge", "Forge access (gh CLI)", "unanswered",
            "gh is installed but the auth probe did not return, so this screen cannot say "
            "whether a credential stands behind it.",
        )
    if probe.returncode != 0:
        return _item(
            "forge", "Forge access (gh CLI)", "missing",
            "gh is installed and not authenticated. Nothing can read CI or open a pull "
            "request until it is.",
            "gh auth login",
        )
    return _item(
        "forge", "Forge access (gh CLI)", "ready",
        "gh is installed and authenticated; the loop can read specifications, watch CI and "
        "open pull requests.",
    )


def _agent_item() -> dict:
    claude = shutil.which("claude")
    if claude is None:
        return _item(
            "agent", "Agent runtime (claude CLI)", "missing",
            "The claude CLI is not on PATH. The last tier of the remediation cascade runs it; "
            "a finding a codemod resolves never needs it, anything else abandons without it.",
            "https://claude.com/claude-code — install, then authenticate once",
        )
    return _item(
        "agent", "Agent runtime (claude CLI)", "ready",
        "The claude CLI is on PATH for the cascade's agent tier.",
    )


def _vendor_cache_item(cache_dir: Path) -> dict:
    if not cache_dir.is_dir():
        return _item(
            "vendor-cache", "Vendor specifications", "missing",
            f"No staged vendor cache at {cache_dir}. Detection joins call sites against a "
            "vendor's specification, so without one staged the detectors have nothing to diff.",
            "uv run python scripts/stage_symbol_map.py",
        )
    staged = []
    for vendor_dir in sorted(cache_dir.iterdir()):
        if not (vendor_dir / "symbols.json").is_file():
            continue
        provenance = vendor_dir / "provenance.json"
        tag = None
        if provenance.is_file():
            try:
                tag = json.loads(provenance.read_text(encoding="utf-8")).get("tag")
            except (ValueError, OSError):
                tag = None
        staged.append(f"{vendor_dir.name}" + (f" ({tag})" if tag else ""))
    if not staged:
        return _item(
            "vendor-cache", "Vendor specifications", "missing",
            f"{cache_dir} exists and holds no staged symbol map.",
            "uv run python scripts/stage_symbol_map.py",
        )
    return _item(
        "vendor-cache", "Vendor specifications", "ready",
        "Staged offline: " + ", ".join(staged) + ". A snapshot ages — findings derived from it "
        "reflect the vendor as of its tag, not today.",
    )


def _index_item(store: GraphStore, repo_id: str | None) -> dict:
    if repo_id is None:
        return _item(
            "index", "Codebase indexed", "missing",
            "No repository is in the graph yet. Indexing is what turns this console from a "
            "product that runs into your own call sites on screen.",
            "uv run sync index --repo .",
        )
    return _item(
        "index", "Codebase indexed", "ready",
        f"{repo_id} is in the graph; every screen is scoped to it.",
    )


def _remote_item(store: GraphStore, repo_id: str | None) -> dict:
    if repo_id is None:
        return _item(
            "remote", "Git remote", "missing",
            "A remote can be recorded once a codebase is indexed.",
            "Index first, then Settings → Setup",
        )
    remote = store.repo_settings(repo_id).remote_url
    if remote is None:
        return _item(
            "remote", "Git remote", "missing",
            "No remote recorded. `sync run` clones the remote and addresses the same "
            "repository through the forge to read CI and open the pull request — a local "
            "checkout carries no owner and name for that call.",
            "Settings → Setup: record the repository's https:// or git@ remote",
        )
    return _item(
        "remote", "Git remote", "ready",
        f"The loop addresses {remote}.",
    )


def _policy_item(store: GraphStore, repo_id: str | None) -> dict:
    if repo_id is None:
        return _item(
            "policy", "Merge policy", "missing",
            "Policy attaches to a repository; index one first.",
            "uv run sync index --repo .",
        )
    settings = store.repo_settings(repo_id)
    return _item(
        "policy", "Merge policy", "ready",
        f"{settings.merge_policy}, {settings.merge_method}, base {settings.base_branch}. "
        "Immediate merge stays refused: nothing reaches a pull request unverified.",
    )


def setup_checklist(store: GraphStore, *, repo_id: str | None, cache_dir: str = "vendor-cache") -> dict:
    """Every prerequisite of the full loop, probed now, for one repository's point of view."""
    return {
        "repo_id": repo_id,
        "items": [
            _index_item(store, repo_id),
            _vendor_cache_item(Path(cache_dir)),
            _forge_item(),
            _agent_item(),
            _remote_item(store, repo_id),
            _policy_item(store, repo_id),
        ],
    }
