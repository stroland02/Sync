"""tsc's output format is a contract between the compiler and the parser.

`parse_diagnostics` matches `file(line,column): error TSxxxx: message`, which is what tsc
prints with `--pretty false`. Left to itself tsc prints the pretty form -- `file:line:col -
error TSxxxx:` wrapped in ANSI colour -- and the parser matches none of it.

The consequence is not a parse warning. `typescript.py` treats a non-zero exit that parses to
zero diagnostics as "the compiler could not run", so a project with real, ordinary type errors
was reported as a broken toolchain and the whole verification gate raised.
"""

from __future__ import annotations

from sync.index.tsc import parse_diagnostics


PRETTY = (
    "\x1b[96msrc/asset0.ts\x1b[0m:\x1b[93m1\x1b[0m:\x1b[93m18\x1b[0m - "
    "\x1b[91merror\x1b[0m\x1b[90m TS2307: \x1b[0mCannot find module '@/public/logo0.png'.\n"
)

PLAIN = "src/asset0.ts(1,18): error TS2307: Cannot find module '@/public/logo0.png'.\n"


def test_the_format_the_parser_is_written_for_parses():
    found = parse_diagnostics(PLAIN)

    assert len(found) == 1
    assert found[0].code == "TS2307"
    assert found[0].file == "src/asset0.ts"
    assert found[0].line == 1


def test_the_pretty_format_does_not_parse_which_is_why_it_must_not_be_produced():
    """Pinning the failure rather than teaching the parser both formats.

    Two formats means two things to keep working, and the pretty one carries colour that
    varies with whether a TTY is attached -- a parser that depends on that is a test that
    passes locally and fails in CI, or the reverse.
    """
    assert parse_diagnostics(PRETTY) == []


def test_the_command_disables_pretty_output():
    """The actual fix, asserted where it can regress.

    `run_tsc` builds its argv two ways -- a local `node_modules/.bin/tsc` and an `npx`
    fallback -- and a flag added to one and forgotten on the other fails only on machines
    taking the other path.
    """
    import inspect

    from sync.index import tsc

    source = inspect.getsource(tsc.run_tsc)
    local_branch, npx_branch = source.split("else:", 1)

    assert '"--pretty"' in local_branch and '"false"' in local_branch, (
        "the local tsc branch does not disable pretty output"
    )
    assert '"--pretty"' in npx_branch and '"false"' in npx_branch, (
        "the npx branch does not disable pretty output"
    )
