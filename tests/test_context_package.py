from pathlib import Path

from sync.context import SEED_RELATIVE_PATH, read_seed, render_section


def _seed(root: Path, contents: bytes) -> None:
    target = root / SEED_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(contents)


def test_no_file_is_none(tmp_path):
    assert read_seed(tmp_path) is None


def test_a_file_is_its_stripped_contents(tmp_path):
    _seed(tmp_path, b"\n  Package manager is pnpm.\n\n")
    assert read_seed(tmp_path) == "Package manager is pnpm."


def test_an_empty_file_is_none(tmp_path):
    _seed(tmp_path, b"")
    assert read_seed(tmp_path) is None


def test_a_whitespace_only_file_is_none(tmp_path):
    """Absence and emptiness must not reach a prompt as two states."""
    _seed(tmp_path, b"   \n\t\n  ")
    assert read_seed(tmp_path) is None


def test_a_file_over_the_cap_is_none_rather_than_truncated(tmp_path):
    _seed(tmp_path, b"x" * 8001)
    assert read_seed(tmp_path) is None


def test_a_file_exactly_at_the_cap_is_read(tmp_path):
    _seed(tmp_path, b"x" * 8000)
    assert read_seed(tmp_path) == "x" * 8000


def test_the_cap_counts_characters_rather_than_bytes(tmp_path):
    """8000 accented characters is 16000 bytes in UTF-8 and is still under the cap.

    Counting bytes would make a body of French or Polish prose silently half the length of an
    English one, which is a limit nobody was told about.
    """
    _seed(tmp_path, ("é" * 8000).encode("utf-8"))
    assert read_seed(tmp_path) == "é" * 8000


def test_bytes_that_are_not_utf_8_are_none_rather_than_raising(tmp_path):
    """A customer's optional file being malformed must never abandon a run.

    0xFF is not a valid UTF-8 start byte. Under the locale codepage on Windows it decodes to
    'ÿ' instead of raising, which is exactly why `encoding="utf-8"` is passed explicitly and
    why this test uses real bytes rather than an ASCII fixture.
    """
    _seed(tmp_path, b"valid text \xff more text")
    assert read_seed(tmp_path) is None


def test_a_directory_where_the_file_should_be_is_none(tmp_path):
    (tmp_path / SEED_RELATIVE_PATH).mkdir(parents=True)
    assert read_seed(tmp_path) is None


def test_a_rendered_section_names_the_repository_and_carries_the_body():
    rendered = render_section("Package manager is pnpm.")
    assert "What is true of this repository:" in rendered
    assert "Package manager is pnpm." in rendered


def test_an_empty_body_renders_nothing_at_all(tmp_path):
    """Not an empty heading -- nothing.

    A prompt built for a repository with no context must be byte-identical to the prompt built
    before this feature existed, which is what makes the change provably additive.
    """
    assert render_section("") == ""
    assert render_section("   \n  ") == ""
