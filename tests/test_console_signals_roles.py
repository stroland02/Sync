"""The Telemetry page keeps never-attached apart from quiet, now that the role catalogue is gone.

This file used to hold the Signals level to the M5 three-role roster — the vendor, signal-source
and human-surface cards, their relationship sentences read from `roles.ts`, and the attached/
unattached split. **The owner retired that subject on 2026-08-19**: this page is the Observe
stage's live instrument, the vendor roster lives on the Vendors page and the delivery surface in
Settings, so the cards and `roles.ts` were deleted rather than deprecated. The M5 table in the
specification is untouched — the level stopped being its catalogue, not its authority.

What the old guard protected that still matters is the distinction B157 names: an empty page
under attached telemetry is a measured nought, and the same empty page with no attachment is
nobody having looked. That coverage survives here (M14-W273's precedent: a test whose subject
retires may go, but not the coverage it carried), held the same way the old file held it — by
reading the TypeScript from Python, since the payload-side half already lives in
`tests/test_graph_views.py`.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNALS_DIR = REPO_ROOT / "web" / "src" / "features" / "signals"
KPIS_PATH = SIGNALS_DIR / "signals-kpis.tsx"
PAGE_PATH = SIGNALS_DIR / "signals-page.tsx"


def test_the_kpi_strip_branches_on_attachment_rather_than_rendering_counts_bare() -> None:
    """Every tile must read `telemetry_attached_at` — a count rendered without the branch would
    draw never-attached as a measured zero, the substitution B157 exists to refuse."""
    source = KPIS_PATH.read_text(encoding="utf-8")
    assert "telemetry_attached_at" in source
    assert "Absent" in source
    # The never-attached sentence stays on screen in words, not merely as an absent dash.
    assert "never watching" in source


def test_the_page_states_its_poll_rather_than_wearing_a_live_badge() -> None:
    """The page re-asks on an interval and stamps when it last asked. A 'live' label or a pulse
    would claim a push this transport does not have — refused on the record (web/CLAUDE.md)."""
    source = PAGE_PATH.read_text(encoding="utf-8")
    assert "refetchIntervalMs" in source
    assert "dataUpdatedAt" in source


def test_the_role_catalogue_stayed_deleted_rather_than_deprecated() -> None:
    """`roles.ts` and the catalogue components were deleted on the owner's ruling. A file that
    reappears is a drift back toward the retired layout — this page is live signals only."""
    for name in ("roles.ts", "subject-catalogue.tsx", "not-attached-state.tsx"):
        assert not (SIGNALS_DIR / name).exists(), f"{name} was retired on 2026-08-19"
