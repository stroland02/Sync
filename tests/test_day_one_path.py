"""The documented first run, checked against the code it documents.

Documentation is prose until something reads it. These tests read the block a new user types
verbatim -- the first-run region of `docs/developing.md` -- and hold it against the argparse
surface, the two entry points that resolve a graph, and the value `--repo` refuses. None of
them needs the network, Docker or a model call; the two that need Postgres reach only
`information_schema`.

**They read `docs/developing.md` rather than `README.md` as of `CI-W442`**, because `CI-W435`
made the README the install page for a visitor and moved the developer first run out. The
subject never changed -- what somebody performs on a fresh checkout -- so the tests followed
the content rather than the filename.

The failure they exist to stop is drift rather than a bug. An audit on 2026-08-16 walked the
Quick start as a new user would and found three of its eight commands unable to work and two
prerequisites undocumented; every one of those claims had been true when it was written.
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
from pathlib import Path

import pytest

from conftest import dsn_for
from sync.api import __main__ as api_main
from sync.cli import DEFAULT_DSN, build_parser, remote_url
from sync.graph.store import GraphStore

README = Path(__file__).resolve().parents[1] / "README.md"

# The developer first run moved here when `CI-W435` turned the README into the install page.
# These tests follow the content rather than the filename: what they check is the run somebody
# performs on a fresh checkout, and that is a different document from the one a visitor reads.
FIRST_RUN = Path(__file__).resolve().parents[1] / "docs" / "developing.md"

# The database this run was given, which is not the default: `conftest` builds one per process.
DSN = os.environ.get("SYNC_DSN", DEFAULT_DSN)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _fenced_bash_blocks(markdown: str) -> list[str]:
    return re.findall(r"^```bash\n(.*?)^```", markdown, flags=re.MULTILINE | re.DOTALL)


def _first_run_doc() -> str:
    return FIRST_RUN.read_text(encoding="utf-8")


def _quick_start(markdown: str) -> str:
    """The section a new user performs, from the prerequisites to the end of the console block.

    A region rather than one heading, because the documented first run is four consecutive
    sections -- what you need, install, run, console -- and checking only one of them would let
    a prerequisite drift out of the other three unnoticed.

    **This raised `ValueError` for three tests when the section moved**, which reads as a crash
    rather than as the rename it was. Missing markers now fail with a sentence saying which
    document was searched and for what.
    """
    opening = "\n### What you need before the first command\n"
    closing = "\n## Quality gates"
    if opening not in markdown:
        raise AssertionError(
            f"{FIRST_RUN.name} no longer opens the documented first run with {opening.strip()!r}"
            " -- if that section moved again, point this at where it went rather than deleting"
            " the check"
        )
    start = markdown.index(opening)
    end = markdown.index(closing, start) if closing in markdown[start:] else len(markdown)
    return markdown[start:end]

def _sync_invocations(block: str) -> list[list[str]]:
    """Every `uv run sync ...` in a shell block, as argv the parser can be handed.

    Backslash continuations are joined first: the Quick start writes `sync run` across four
    lines, and a line-at-a-time reader would see four commands, three of them bare flags.
    """
    joined = block.replace("\\\n", " ")
    invocations = []
    for line in joined.splitlines():
        stripped = line.split("#", 1)[0].strip()
        if not stripped:
            continue
        tokens = shlex.split(stripped)
        if tokens[:3] == ["uv", "run", "sync"]:
            invocations.append(tokens[3:])
    return invocations


def _subparsers(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def _option_strings(parser: argparse.ArgumentParser) -> set[str]:
    return {option for action in parser._actions for option in action.option_strings}


def _resolve(argv: list[str]) -> tuple[argparse.ArgumentParser, list[str]]:
    """Walk `argv` down the subcommand tree, returning the parser it lands on."""
    parser = build_parser()
    remaining = list(argv)
    while remaining and not remaining[0].startswith("-"):
        children = _subparsers(parser)
        if remaining[0] not in children:
            raise AssertionError(
                f"`sync {' '.join(argv)}`: no subcommand named {remaining[0]!r}; "
                f"the CLI offers {sorted(children)}"
            )
        parser = children[remaining.pop(0)]
    return parser, remaining


def test_every_command_in_the_quick_start_is_a_command_the_cli_has():
    """Every flag spelled in full, never relying on argparse's prefix matching.

    `parse_args` accepts `--from` for `--from-version` because abbreviation is on by default,
    so a README written that way runs today and breaks the day any other option on that
    subcommand starts with `from`. The documented spelling has to be the real one.
    """
    invocations = [
        argv
        for block in _fenced_bash_blocks(_quick_start(_first_run_doc()))
        for argv in _sync_invocations(block)
    ]
    assert invocations, "the Quick start block invokes no `uv run sync` command at all"

    for argv in invocations:
        parser, remaining = _resolve(argv)
        declared = _option_strings(parser)
        for token in remaining:
            if token.startswith("--"):
                flag = token.split("=", 1)[0]
                assert flag in declared, (
                    f"`sync {' '.join(argv)}` passes {flag}, which "
                    f"`{parser.prog}` does not declare; it declares {sorted(declared)}"
                )
        parser.parse_args(remaining)


def test_every_sync_command_the_readme_names_in_prose_exists():
    """The entry-point table and the sentences around it, not only the fenced blocks."""
    named = set(re.findall(r"`sync ([a-z][a-z0-9-]*)[^`]*`", _readme()))
    offered = set(_subparsers(build_parser()))

    assert named <= offered, f"README names {sorted(named - offered)}, which the CLI does not"


def test_the_readme_names_every_authenticated_tool_the_first_run_shells_out_to():
    """`gh` and `claude` are prerequisites of a run, not of a pull request.

    `sync.signals.stripe.adapter.fetch_spec` shells out to `gh api` for the specification, so
    an unauthenticated `gh` fails the first run at its first step rather than at the end; and
    the cascade's last tier is the Claude Agent SDK, which runs the `claude` binary. Both were
    undocumented, and the second was named nowhere in the repository's front matter.
    """
    quick_start = _quick_start(_first_run_doc())

    for tool in ("gh", "claude", "npm"):
        assert re.search(rf"`{tool}`", quick_start), (
            f"the Quick start does not name `{tool}`, which the documented first run needs"
        )


def test_the_console_block_installs_and_seeds_before_it_starts_anything():
    """Two orderings, both of which the block had wrong.

    `npm run dev` appeared with no `npm install` anywhere in `README.md`, `CONTRIBUTING.md` or
    `ARCHITECTURE.md`, so a fresh checkout met a missing `vite`. And the API was started ahead
    of the seed, which is the order that leaves it reading a database with no schema.
    """
    console = next(
        block for block in _fenced_bash_blocks(_quick_start(_first_run_doc()))
        if "npm run dev" in block
    )

    assert console.index("npm install") < console.index("npm run dev")
    assert console.index("seed_console.py") < console.index("sync.api")


class _RecordingStore:
    built: list[str] = []

    def __init__(self, dsn: str) -> None:
        _RecordingStore.built.append(dsn)

    def missing_tables(self) -> list[str]:
        return []

    def call_site_source(self, call_site_id: str):
        # The app factory binds this method as the snippet reader; the fake only needs the
        # attribute to exist for the wiring under test, which is DSN resolution.
        return None


def test_the_api_and_the_cli_resolve_the_same_default_graph(monkeypatch):
    """Two entry points, one fact. `python -m sync.api` used to raise a bare KeyError here
    while every CLI subcommand defaulted to the docker-compose database."""
    monkeypatch.delenv("SYNC_GRAPH_DSN", raising=False)
    monkeypatch.delenv("SYNC_CHECKPOINTER_DSN", raising=False)
    monkeypatch.setattr(_RecordingStore, "built", [])
    monkeypatch.setattr(api_main, "GraphStore", _RecordingStore)

    api_main.app_factory()

    cli_default = build_parser().parse_args(["benchmark"]).dsn
    assert _RecordingStore.built == [cli_default]
    assert cli_default == DEFAULT_DSN


def test_a_database_with_no_schema_is_reported_as_missing_every_table():
    """Against the server's own `postgres` database, which no run has ever applied a schema to.

    Read-only: `missing_tables` asks `information_schema` and writes nothing. Using a database
    that exists and is empty is what makes this a real red rather than a mocked one.
    """
    empty = GraphStore(dsn_for("postgres", DSN))

    missing = empty.missing_tables()

    assert "call_site" in missing and "finding" in missing


def test_a_database_with_the_schema_applied_is_reported_as_missing_nothing():
    store = GraphStore(DSN)
    store.apply_schema()

    assert store.missing_tables() == []


class _EmptyStore:
    def missing_tables(self) -> list[str]:
        return ["call_site", "finding"]


def test_the_api_refuses_an_empty_database_and_names_the_command_that_fills_it():
    """The console API is read-only, so it applies no schema; a refusal that does not say
    which command does would leave a reader with a 500 on every route and no next step."""
    with pytest.raises(SystemExit) as refusal:
        api_main.require_schema(_EmptyStore(), DEFAULT_DSN)

    message = str(refusal.value)
    assert "scripts/seed_console.py" in message
    assert "sync run" in message
    assert "call_site" in message


def test_the_refusal_carries_no_password():
    with pytest.raises(SystemExit) as refusal:
        api_main.require_schema(_EmptyStore(), "postgresql://sync:hunter2@localhost:5433/sync")

    assert "hunter2" not in str(refusal.value)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/stroland02/stripe-connect-furever-demo",
        "https://github.com/an-org/a-repo.git",
        "git@github.com:an-org/a-repo.git",
        "ssh://git@github.com/an-org/a-repo",
    ],
)
def test_a_remote_url_is_accepted(url):
    assert remote_url(url) == url


@pytest.mark.parametrize(
    "value",
    [
        "/path/to/your/checkout",
        "./checkout",
        "../sibling",
        "checkout",
        "C:/Users/someone/checkout",
        "C:\\Users\\someone\\checkout",
        "file:///c/Users/someone/checkout",
    ],
)
def test_a_filesystem_path_is_refused_with_what_to_pass_instead(value):
    with pytest.raises(argparse.ArgumentTypeError) as refusal:
        remote_url(value)

    message = str(refusal.value)
    assert value in message
    assert "https://github.com/" in message


def test_the_parser_refuses_a_local_path_before_the_run_starts(tmp_path, capsys):
    """Refused while argv is being read, which is ahead of every cost the run would pay.

    Reached later it is worth little: the run has already cloned, indexed, detected and -- on
    the path this was reported from -- paid for an agent turn before the first `gh api` 404s.
    The parser is also the right altitude rather than merely the earliest one. `push_branch`
    genuinely serves a local origin, and `test_cli.py` drives the whole pipeline that way with
    the two `gh`-backed steps replaced; only a value a person typed reaches the real forge.
    """
    checkout = tmp_path / "checkout"
    checkout.mkdir()

    with pytest.raises(SystemExit) as refusal:
        build_parser().parse_args([
            "run", "--from-version", "v2320", "--to-version", "v2330", "--repo", str(checkout),
        ])

    assert refusal.value.code == 2
    assert "git remote URL" in capsys.readouterr().err
