from pathlib import Path

import pytest

from sync.index.tsc import run_tsc


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "tsconfig.json").write_text(
        '{"compilerOptions": {"strict": true, "noEmit": true, "target": "ES2022", "module": "ESNext",'
        ' "moduleResolution": "bundler", "skipLibCheck": true}, "include": ["src"]}',
        encoding="utf-8",
    )
    (tmp_path / "src").mkdir()
    return tmp_path


def test_clean_project_verifies_ok(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 1;\n", encoding="utf-8")
    result = run_tsc(project)
    assert result.ok is True
    assert result.diagnostics == ""


def test_type_error_fails_and_diagnostics_are_captured(project: Path):
    (project / "src" / "a.ts").write_text("export const n: number = 'not a number';\n", encoding="utf-8")
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2322" in result.diagnostics


def test_reading_a_property_that_does_not_exist_fails(project: Path):
    (project / "src" / "a.ts").write_text(
        "type Charge = { id: string };\n"
        "declare const c: Charge;\n"
        "export const s = c.status;\n",
        encoding="utf-8",
    )
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2339" in result.diagnostics


def test_non_ascii_identifier_does_not_crash_the_gate(project: Path):
    """A non-ASCII identifier anywhere in the project must not crash run_tsc.

    tsc emits UTF-8 diagnostics. Decoding subprocess output with the locale
    encoding (cp1252 on this machine) instead of UTF-8 raises UnicodeDecodeError
    on a byte like the second one in 'Á'.encode('utf-8'), which is undefined
    in cp1252 -- this must not turn a real type error into a crashed gate.
    """
    (project / "src" / "a.ts").write_text(
        "type Álias = { id: string };\n"
        "declare const c: Álias;\n"
        "export const s = c.status;\n",
        encoding="utf-8",
    )
    result = run_tsc(project)
    assert result.ok is False
    assert "TS2339" in result.diagnostics
