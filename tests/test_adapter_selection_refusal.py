"""What adapter selection says when no indexer claims a repository.

`sync.signals.intake` answers the neighbouring question -- which of a repository's dependencies
Sync can watch -- and gives every one of them a reason, keeping a manifest that would not parse
in a channel of its own because "declares nothing" and "could not be read" are the same value
and different facts.

Selection answered every decline with one sentence naming the languages it tried, so five
situations arrived identical: a vendor whose adapter declares no SDK package, a manifest that
does not parse, one that does not decode, one that is absent, and one that was read and does not
declare the package. The sentence said the repository declares no SDK, which for the first of
those is false -- the repository declares one and nothing in this deployment says which package
to look for.

The undecodable `package.json` is worse than uninformative. `_declared_dependencies` caught
`json.JSONDecodeError` only, so a UTF-16 manifest raised out of `matches` and took the run down
at selection -- the failure B45 closed for `requirements.txt`, still live one language over.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync import cli
from sync.cli import select_language_adapter
from sync.core import RepoRef


class _Bound:
    """A vendor whose adapter declares its SDK package in both languages."""

    vendor_id = "stripe"
    sdk_bindings = {
        "typescript": {"package": "stripe"},
        "python": {"distribution": "stripe", "module": "stripe"},
    }

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        return None

    def fetch_changes(self, from_version: str, to_version: str):
        return []


class _Unbound:
    """A vendor whose adapter declares no package at all.

    Every vendor served by `GeneratedSpecAdapter` and every watched MCP server is in this
    position today -- four of the six registered vendors among them. Their specifications are
    diffable and their call sites cannot be bound, which is a gap in this deployment's
    configuration and not a fact about anybody's repository.
    """

    vendor_id = "anthropic"

    def operation_for_symbol(self, symbol: str, *, language: str | None = None):
        return None

    def fetch_changes(self, from_version: str, to_version: str):
        return []


def _repo(root: Path) -> RepoRef:
    return RepoRef(
        repo_id="r1", url="https://example.invalid/r",
        local_path=str(root), head_sha="0" * 40,
    )


def _refusal(root: Path, vendor: object) -> str:
    with pytest.raises(LookupError) as raised:
        select_language_adapter(_repo(root), vendor)
    return str(raised.value)


def test_a_vendor_declaring_no_package_is_named_rather_than_the_repository(
    tmp_path: Path,
) -> None:
    """The repository here does declare an SDK, and the missing configuration is ours.

    Told that it "declares no SDK any indexer recognises", a customer goes looking at their own
    manifest for a fault that is in `sdk_bindings`. `registry.vendor_sdk_bindings` already says
    this gap is reported rather than hidden; selection was the surface still hiding it.
    """
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"@anthropic-ai/sdk": "0.30.1"}}', encoding="utf-8"
    )

    message = _refusal(tmp_path, _Unbound())

    assert "anthropic" in message
    assert message.count("sdk_bindings") == 2, message


@pytest.mark.parametrize(
    "manifest, content",
    [
        ("package.json", b'{"dependencies": {"stripe": "17.0.0",}'),
        ("pyproject.toml", b"[project\ndependencies = "),
        ("requirements.txt", "stripe>=12.0\n".encode("utf-16")),
        ("package.json", '{"dependencies": {"stripe": "17.0.0"}}'.encode("utf-16")),
    ],
)
def test_a_manifest_that_cannot_be_read_says_so_rather_than_declaring_nothing(
    tmp_path: Path, manifest: str, content: bytes
) -> None:
    """An unreadable manifest is not a repository with no dependencies.

    Each of these declares the vendor's package and reads as a repository that does not use it.
    B45 accepted that cost on the reading side -- one undecodable byte declares nothing -- on the
    grounds that a missing binding is recoverable. Recoverable by whom is the question this
    answers: the refusal has to name the file, or nobody can act on it.
    """
    (tmp_path / manifest).write_bytes(content)

    message = _refusal(tmp_path, _Bound())

    assert manifest in message
    assert "could not be read" in message, message


def test_an_absent_manifest_names_the_files_that_were_looked_for(tmp_path: Path) -> None:
    """Nothing to read is a different fact from something read and found wanting."""
    (tmp_path / "README.md").write_text("no manifest of any kind", encoding="utf-8")

    message = _refusal(tmp_path, _Bound())

    assert "package.json" in message
    assert "pyproject.toml" in message and "requirements.txt" in message


def test_a_manifest_that_was_read_names_the_package_that_was_missing(tmp_path: Path) -> None:
    """The honest decline, and the only one of the five that is about the repository.

    It has to name the package, because "does not depend on this vendor" is a claim the customer
    can only check against the string that was actually looked for.
    """
    (tmp_path / "package.json").write_text(
        '{"dependencies": {"express": "4.19.2"}}', encoding="utf-8"
    )

    message = _refusal(tmp_path, _Bound())

    assert "stripe" in message
    assert "express" not in message


def test_an_indexer_that_explains_nothing_still_appears_in_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`decline_reason` is optional, the way `unverifiable_reason` is.

    `LanguageAdapter` is a protocol this deployment does not own, so a third party's adapter that
    has never heard of the method must still be listed -- and listed as having said nothing,
    which is a fact about that adapter rather than a blank in the message.
    """

    class _Silent:
        language_id = "cobol"

        def __init__(self, vendor_adapter: object) -> None:
            pass

        def matches(self, repo: RepoRef) -> bool:
            return False

    monkeypatch.setattr(cli, "language_adapters", lambda: (_Silent,))

    message = _refusal(tmp_path, _Bound())

    assert "cobol" in message
    assert "without saying why" in message, message


def test_an_indexer_whose_explanation_raises_does_not_replace_the_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hazard the old `getattr` was written against, moved to the new method.

    This runs while the run is already stopping, and it is the only place the other indexers'
    accounts are assembled -- so a third party's `decline_reason` raising would trade every one of
    them for a traceback about the refusal rather than the refusal. A `LanguageAdapter` comes from
    outside this deployment, which makes this a boundary rather than internal code.
    """

    class _Broken:
        language_id = "fortran"

        def __init__(self, vendor_adapter: object) -> None:
            pass

        def matches(self, repo: RepoRef) -> bool:
            return False

        def decline_reason(self, repo: RepoRef) -> str:
            raise RuntimeError("manifest parser is not installed")

    monkeypatch.setattr(cli, "language_adapters", lambda: (_Broken,))

    message = _refusal(tmp_path, _Bound())

    assert "fortran" in message
    assert "manifest parser is not installed" in message, message
