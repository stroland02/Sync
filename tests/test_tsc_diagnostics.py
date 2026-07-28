from sync.index.tsc import Diagnostic, introduced_diagnostics, parse_diagnostics

# Copied from a real `tsc --noEmit` run rather than paraphrased: the format is
# the contract this parser is written against, and a hand-written approximation
# of it would pass while the real thing failed.
REAL_OUTPUT = (
    "src/a.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.\n"
    "src/a.ts(2,15): error TS2307: Cannot find module '@/nope.png' or its corresponding type declarations.\n"
    "src/a.ts(4,14): error TS2322: Type 'number' is not assignable to type 'string'.\n"
)


def test_a_diagnostic_line_parses_into_its_parts():
    first = parse_diagnostics(REAL_OUTPUT)[0]

    assert first.file == "src/a.ts"
    assert first.line == 1
    assert first.column == 14
    assert first.code == "TS2322"
    assert first.message == "Type 'string' is not assignable to type 'number'."


def test_every_diagnostic_in_the_output_is_found():
    assert len(parse_diagnostics(REAL_OUTPUT)) == 3


def test_a_diagnostic_with_no_file_still_parses():
    """`tsc` reports a handful of configuration errors with no position at all,
    and one of them standing alone is still a real failure to account for."""
    found = parse_diagnostics("error TS18003: No inputs were found in config file.\n")

    assert len(found) == 1
    assert found[0].file == ""
    assert found[0].code == "TS18003"


def test_output_that_is_not_a_diagnostic_yields_nothing():
    """A timeout, a crashed compiler and a failed npx download all reach the
    gate as a non-zero exit with prose on stderr. Reading those as "no
    diagnostics" would make an uninterpretable run indistinguishable from a
    clean one, which is why the caller checks for emptiness rather than
    trusting it."""
    assert parse_diagnostics("typecheck timed out after 300s") == []
    assert parse_diagnostics("") == []


def test_a_baseline_that_the_patch_reproduces_exactly_introduces_nothing():
    baseline = parse_diagnostics(REAL_OUTPUT)

    assert introduced_diagnostics(baseline, list(baseline)) == []


def test_a_diagnostic_absent_from_the_baseline_is_introduced():
    baseline = parse_diagnostics(REAL_OUTPUT)
    patched = parse_diagnostics(
        REAL_OUTPUT + "src/b.ts(9,3): error TS2339: Property 'status' does not exist on type 'Charge'.\n"
    )

    introduced = introduced_diagnostics(baseline, patched)

    assert [d.code for d in introduced] == ["TS2339"]
    assert introduced[0].line == 9


def test_a_pre_existing_diagnostic_that_moved_down_the_file_is_not_introduced():
    """The reason line and column are not part of the identity.

    A patch that adds two lines near the top of a file moves every diagnostic
    below it. Keyed on position, all of them read as introduced and their
    originals read as fixed, and the gate rejects a patch for errors it did not
    write.
    """
    baseline = parse_diagnostics(
        "src/a.ts(5,25): error TS2307: Cannot find module '@/logo.png' or its corresponding type declarations.\n"
    )
    patched = parse_diagnostics(
        "src/a.ts(7,25): error TS2307: Cannot find module '@/logo.png' or its corresponding type declarations.\n"
    )

    assert introduced_diagnostics(baseline, patched) == []


def test_one_more_copy_of_a_pre_existing_diagnostic_is_introduced():
    """The cost of dropping position from the identity, and why the comparison
    counts rather than sets. Two call sites in one file can fail identically, so
    a patch that adds a third has added one the baseline does not cover."""
    line = "src/a.ts(5,25): error TS2307: Cannot find module '@/logo.png' or its corresponding type declarations.\n"
    baseline = parse_diagnostics(line * 2)
    patched = parse_diagnostics(line * 3)

    assert len(introduced_diagnostics(baseline, patched)) == 1


def test_a_baseline_diagnostic_the_patch_fixed_does_not_excuse_a_different_one():
    """Subtraction is per identity, not by count of errors. A patch that clears
    one pre-existing error has not earned the right to add an unrelated one."""
    baseline = parse_diagnostics(REAL_OUTPUT)
    patched = parse_diagnostics(
        "src/a.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        "src/a.ts(2,15): error TS2307: Cannot find module '@/nope.png' or its corresponding type declarations.\n"
        "src/b.ts(9,3): error TS2339: Property 'status' does not exist on type 'Charge'.\n"
    )

    assert [d.code for d in introduced_diagnostics(baseline, patched)] == ["TS2339"]


def test_a_diagnostic_renders_back_to_the_line_the_compiler_printed():
    """What the gate reports is fed to the next patch attempt, so it has to
    carry the position the compiler gave even though the comparison ignored it."""
    rendered = Diagnostic(
        file="src/a.ts", line=5, column=25, code="TS2307", message="Cannot find module '@/logo.png'."
    ).render()

    assert rendered == "src/a.ts(5,25): error TS2307: Cannot find module '@/logo.png'."
