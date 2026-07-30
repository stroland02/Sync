"""A frozen corpus must materialise the same bytes on every machine.

The manifest's tree digests were pinned from trees this machine materialised, and this machine
converts: global `core.autocrlf` turns the LF bytes git stores into CRLF on checkout. A Linux
runner performs no conversion, so every digest mismatched there -- all five at once, which is
what said "procedure" rather than "drift". The indexer reads these trees too, so this was never
cosmetic: a corpus that differs by platform scores differently by platform.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.fetch_corpus_repositories import fetch_commit


def _git(args: list[str], cwd: Path, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_a_checkout_materialises_lf_even_where_autocrlf_would_convert(tmp_path, monkeypatch):
    """The premise reproduced locally, then the fix asserted.

    A fixture repository whose stored blob is LF, fetched by `fetch_commit` under an
    environment that forces `autocrlf=true` the way this machine's global config does. Without
    `-c core.autocrlf=false` on the checkout, the materialised file carries CRLF and the digest
    depends on who ran the fetch.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(["init", "-q", "-b", "main"], origin)
    (origin / "a.ts").write_bytes(b"const n = 1;\nconst m = 2;\n")
    _git(["add", "."], origin)
    _git(["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false",
          "commit", "-qm", "lf"], origin)
    commit = _git(["rev-parse", "HEAD"], origin)

    # Force conversion-on-checkout for every git this test spawns, the way a Windows global
    # config does. GIT_CONFIG_* injects it without touching the real global config.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.autocrlf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")

    into = tmp_path / "materialised"
    fetch_commit(origin.as_uri(), commit, into)

    materialised = (into / "a.ts").read_bytes()
    assert b"\r" not in materialised, (
        "the checkout converted line endings, so the digest depends on which machine ran it"
    )


def test_a_gitattributes_text_rule_cannot_reintroduce_the_conversion(tmp_path, monkeypatch):
    """`autocrlf=false` is not enough. Four of the five corpus repositories carry a
    `.gitattributes` with a `text` rule, and attribute-driven conversion follows `core.eol`
    regardless of autocrlf -- `native` means CRLF on Windows, so those four still materialised
    differently per platform while the attribute-free fifth matched everywhere.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(["init", "-q", "-b", "main"], origin)
    (origin / ".gitattributes").write_bytes(b"* text=auto\n")
    (origin / "a.ts").write_bytes(b"const n = 1;\nconst m = 2;\n")
    _git(["add", "."], origin)
    _git(["-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false",
          "commit", "-qm", "lf"], origin)
    commit = _git(["rev-parse", "HEAD"], origin)

    # The Windows default, injected explicitly so the test reproduces it on any platform.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.eol")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "crlf")

    into = tmp_path / "materialised"
    fetch_commit(origin.as_uri(), commit, into)

    assert b"\r" not in (into / "a.ts").read_bytes(), (
        "the text attribute converted on checkout; core.eol must be forced to lf"
    )


def test_the_tree_walk_orders_by_codepoint_not_by_platform_path_rules(tmp_path):
    """Same files, different sequence, different digest.

    `sorted(rglob())` compares Path objects, and Windows compares paths case-insensitively:
    `B.ts` sorts before `a.ts` by codepoint on Linux and after it here. Four of the five corpus
    repositories carry a case-mixed pair somewhere, so their digests differed across platforms
    with every byte identical -- and the fifth, which does not, matched everywhere and made the
    line-ending fix look complete.
    """
    from sync.benchmark.checkout import tree_files

    (tmp_path / "a.ts").write_bytes(b"a\n")
    (tmp_path / "B.ts").write_bytes(b"b\n")

    names = [p.name for p in tree_files(tmp_path)]
    assert names == ["B.ts", "a.ts"], (
        f"walk order {names} is platform ordering, not codepoint ordering"
    )


def test_the_digest_is_taken_in_the_same_order_as_the_walk(tmp_path):
    """`tree_digest` sorts on its own rather than reusing the walk, so the two can disagree
    about order even after the walk is fixed. Pin them to the same rule via the digest value."""
    from scripts.fetch_corpus_repositories import tree_digest

    (tmp_path / "a.ts").write_bytes(b"a\n")
    (tmp_path / "B.ts").write_bytes(b"b\n")

    import hashlib

    expected = hashlib.sha256()
    for name, body in (("B.ts", b"b\n"), ("a.ts", b"a\n")):
        expected.update(name.encode("utf-8"))
        expected.update(b"\0")
        expected.update(hashlib.sha256(body).hexdigest().encode("ascii"))
        expected.update(b"\n")

    assert tree_digest(tmp_path) == expected.hexdigest()
