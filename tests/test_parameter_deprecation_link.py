"""A parameter-deprecation finding has to name the change it came from, or it dies at `locate`.

The detector built a `Finding` with no `vendor_change_id`. The field is optional, so nothing
objected at construction; `make_locate` then called `get_vendor_change(None)`, the `try` around
it set `fatal`, and the run abandoned before a remediator was ever asked. The detector worked,
its tests passed, and nothing it produced could be repaired.

The two halves were both built and never joined. `cli.py` turns parameter deprecations into
`VendorChange` rows and the cascade holds two remediators keyed on
`kind == "deprecation/parameter"`, and no finding pointed at a row.

So these tests drive the real `locate` node rather than inspecting a `Finding`. Asserting the
field is populated proves the field is populated; asserting `locate` returns a change proves the
defect is fixed. And the fixture carries two deprecations on purpose -- a join that always
returned the first row would pass with one and is visibly wrong with two.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import sync.cli as cli
from sync.cli import _parameter_changes, build_remediator
from sync.core import CallSite, Finding, RepoRef
from sync.detect.parameter_deprecation import LinkedDeprecation, ParameterDeprecationDetector
from sync.remediate.nodes import make_locate
from sync.signals.deprecations import ParameterDeprecation

TODAY = date(2027, 1, 1)

# Two rows, two parameters, two remedies. A detector that joined every finding to whichever
# change it happened to see first would pass a one-row fixture and fail here.
OMIT = ParameterDeprecation(
    vendor_id="anthropic", parameter="temperature",
    status="Deprecated (Claude Opus 4.7 and later)",
    behavior="Returns a 400 error when set to a non-default value.",
    applies_from="Claude Opus 4.7 and later",
)
RENAME = ParameterDeprecation(
    vendor_id="anthropic", parameter="budget_tokens", status="Deprecated",
    behavior="Returns a 400 error.", replacement="max_tokens",
)

SOURCE = """\
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

export async function summarise(text: string) {
  return client.messages.create({
    model: "claude-opus-5",
    max_tokens: 1024,
    temperature: 0.7,
    budget_tokens: 512,
  });
}
"""

TARGET = "src/summarise.ts"


def _site() -> CallSite:
    """One call site passing both deprecated parameters, so two findings come off one row."""
    return CallSite(
        id="cs-1", repo_id="r", path=TARGET, line=6, col=17, vendor_id="anthropic",
        operation_id="claude-opus-5", symbol="model",
        args_keys=["model", "max_tokens", "temperature", "budget_tokens"],
        sdk_version="0.70.0", content_hash="h",
    )


class _Store:
    """Ids the way the real store hands them back: assigned on upsert, looked up by id."""

    def __init__(self, site: CallSite) -> None:
        self._site = site
        self._changes: dict[str, object] = {}
        self._next = 0

    def upsert_vendor_change(self, change) -> str:
        self._next += 1
        change_id = f"vc-{self._next}"
        self._changes[change_id] = change
        return change_id

    def get_call_site(self, call_site_id: str) -> CallSite:
        if call_site_id != self._site.id:
            raise KeyError(f"no call site {call_site_id}")
        return self._site

    def get_vendor_change(self, change_id):
        if change_id not in self._changes:
            raise KeyError(f"no vendor change {change_id}")
        return self._changes[change_id]


def _linked(store: _Store, rows=(OMIT, RENAME)) -> list[LinkedDeprecation]:
    """The production pairing: `cli` converts, the store assigns the id, the detector is told."""
    return [
        LinkedDeprecation(deprecation=row, vendor_change_id=store.upsert_vendor_change(change))
        for row, change in _parameter_changes(list(rows), TODAY)
    ]


def _findings(store: _Store, site: CallSite, rows=(OMIT, RENAME)) -> list[Finding]:
    return list(ParameterDeprecationDetector(_linked(store, rows), [site]).scan())


@pytest.fixture()
def repo(tmp_path: Path) -> RepoRef:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "summarise.ts").write_text(SOURCE, encoding="utf-8")
    return RepoRef(
        repo_id="r", url="https://example.invalid/r",
        local_path=str(tmp_path), head_sha="s",
    )


def _locate(store: _Store, finding: Finding, repo: RepoRef) -> dict:
    return make_locate(store)({"finding": finding, "repo": repo})


# --- the defect ------------------------------------------------------------------


def test_a_parameter_finding_survives_locate(repo: RepoRef) -> None:
    """Driven through the node rather than by reading the `Finding`. Today `locate` calls
    `get_vendor_change(None)`, the `try` around it sets `fatal`, and the run abandons before a
    remediator is asked."""
    store = _Store(_site())
    finding = _findings(store, _site())[0]

    state = _locate(store, finding, repo)

    assert state.get("fatal") is False, state.get("diagnostics")
    assert state["change"].kind == "deprecation/parameter"


def test_each_finding_locates_its_own_change(repo: RepoRef) -> None:
    """The assertion a one-row fixture cannot make. A join that named a plausible row rather
    than the established one would send the rename remedy to the omit parameter, which is a
    confident patch against the wrong change."""
    store = _Store(_site())
    site = _site()
    located = {}
    for finding in _findings(store, site):
        state = _locate(store, finding, repo)
        located[state["change"].operation_id] = state["change"].raw["remedy"]

    assert located == {"temperature": "omit", "budget_tokens": "rename"}


def test_it_reaches_a_remediator_that_can_act(
    repo: RepoRef, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Surviving `locate` is worth nothing on its own. The cascade holds both parameter tiers,
    and this asserts one of them takes the work and edits the file.

    The agent tier is made to explode rather than left live: a cascade that fell through to it
    would otherwise spend a model call inside the suite, and the failure would look like
    slowness rather than like a codemod that declined.
    """
    from sync.remediate.agent_patch import AgentRemediator

    def _never(*args, **kwargs):
        raise AssertionError("the cascade fell through to the agent")

    monkeypatch.setattr(AgentRemediator, "propose", _never)

    store = _Store(_site())
    site = _site()
    finding = _findings(store, site)[0]
    state = _locate(store, finding, repo)

    patch = build_remediator().propose(finding, state["change"], site, repo)

    assert patch.strategy == "codemod"
    assert "temperature" not in (Path(repo.local_path) / TARGET).read_text(encoding="utf-8")


# --- what happens when the link cannot be established -----------------------------


def test_a_deprecation_with_no_established_change_emits_no_finding() -> None:
    """The same rule the module already applies to `call_site_id`: a finding naming a row
    nothing established is worse than no finding, because it resolves to something plausible
    and produces a patch against the wrong change."""
    unlinked = LinkedDeprecation(deprecation=OMIT, vendor_change_id="")

    detector = ParameterDeprecationDetector([unlinked], [_site()])

    assert list(detector.scan()) == []


def test_the_dropped_deprecation_is_observable() -> None:
    """A row the pipeline silently discards is the defect this whole milestone keeps finding.
    The skip is counted, so a run that dropped work can say so."""
    detector = ParameterDeprecationDetector(
        [LinkedDeprecation(deprecation=OMIT, vendor_change_id="")], [_site()]
    )
    list(detector.scan())

    assert len(detector.declined) == 1
    assert "temperature" in detector.declined[0]


def test_an_established_link_is_not_reported_as_dropped() -> None:
    """So the counter above cannot be satisfied by one that always reports."""
    store = _Store(_site())
    detector = ParameterDeprecationDetector(_linked(store), [_site()])
    list(detector.scan())

    assert detector.declined == []


def test_the_drop_counter_resets_rather_than_accumulating_across_scans() -> None:
    """The reset, asserted against a scan that actually drops something.

    `test_scanning_twice_gives_the_same_answer` reads as though it held this and does not: its
    deprecation is linked, so the counter is empty either way and deleting the reset leaves it
    green. A mutation removing `self.declined = []` survived until this existed.
    """
    detector = ParameterDeprecationDetector(
        [LinkedDeprecation(deprecation=OMIT, vendor_change_id="")], [_site()]
    )

    list(detector.scan())
    list(detector.scan())

    assert len(detector.declined) == 1


# --- the pairing itself -----------------------------------------------------------


def test_each_change_is_built_from_exactly_one_deprecation() -> None:
    """What makes the join established rather than inferred.

    Each row is converted alone, so the change in a pair came from that row and from nothing
    else. Zipping two lists would be an assumption about ordering that holds today and is not
    stated anywhere, and the failure mode of a wrong assumption here is a patch against the
    wrong change.
    """
    pairs = _parameter_changes([OMIT, RENAME], TODAY)

    assert [(row.parameter, change.operation_id) for row, change in pairs] == [
        ("temperature", "temperature"),
        ("budget_tokens", "budget_tokens"),
    ]
