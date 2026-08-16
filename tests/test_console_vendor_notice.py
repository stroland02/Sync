"""Every vendored Supabase file is attributed, and the attribution is complete.

Grain: one NOTICE entry per file under web/src/vendor/supabase/.
"""
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
VENDOR = WEB / "src" / "vendor" / "supabase"
NOTICE = WEB / "NOTICE"


def vendored_files() -> list[Path]:
    return [p for p in VENDOR.rglob("*") if p.suffix in {".ts", ".tsx"}]


def test_vendor_directory_exists_and_is_nonempty():
    assert VENDOR.is_dir(), "web/src/vendor/supabase/ missing"
    assert vendored_files(), "vendor directory holds no TypeScript"


def test_notice_names_every_vendored_file():
    notice = NOTICE.read_text(encoding="utf-8")
    assert "Apache License" in notice and "supabase/supabase" in notice
    missing = [
        str(rel)
        for p in vendored_files()
        if (rel := p.relative_to(WEB).as_posix()) not in notice
    ]
    assert not missing, f"vendored but not in NOTICE: {missing}"


def test_notice_pins_the_source_commit():
    import re
    notice = NOTICE.read_text(encoding="utf-8")
    assert re.search(r"pinned at commit [0-9a-f]{7,40}", notice), "NOTICE names no pinned SHA"
