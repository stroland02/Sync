"""The four tools as declared data, and the dispatcher that binds them to the surface.

An agent composes against a schema, not against a docstring. The spec freezes the tool set on
first publish -- new tools and new optional parameters may be added, nothing may be removed or
renamed -- and `tests/golden/tool_schemas.json` is the executable form of that rule. A product
whose whole claim is catching breaking changes cannot ship one of its own.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from sync.core import CallSite, Finding, VendorChange
from sync.mcp.registry import TOOL_NAMES, TOOLS, dispatch, schemas_as_data
from sync.mcp.tools import GraphSurface

GOLDEN = Path(__file__).parent / "golden" / "tool_schemas.json"
INDEXED = datetime(2026, 7, 28, 6, 0, tzinfo=timezone.utc)


class FakeGraph:
    def open_findings(self) -> list[Finding]:
        return [
            Finding(
                id="f-1", detector="vendor_change", claim="response-field",
                call_site_id="site-1",
                vendor_change_id="chg-1", severity="breaking", rationale="why",
            )
        ]

    def get_call_site(self, call_site_id: str) -> CallSite:
        return CallSite(
            id="site-1", repo_id="r", path="src/pay.ts", line=12, col=4, vendor_id="stripe",
            operation_id="PostCharges", symbol="stripe.charges.create",
            args_keys=["amount"], response_fields_read=["status"],
            sdk_version="18.0.0", content_hash="h", indexed_at=INDEXED,
        )

    def get_vendor_change(self, change_id: str) -> VendorChange:
        return self.all_vendor_changes("stripe")[0]

    def all_vendor_changes(self, vendor_id: str) -> list[VendorChange]:
        if vendor_id != "stripe":
            return []
        return [
            VendorChange(
                id="chg-1", vendor_id="stripe", from_version="v1", to_version="v2",
                kind="response-property-removed", operation_id="PostCharges",
                path_ptr="/v1/charges", severity="breaking", source="oasdiff", raw={},
            )
        ]


@pytest.fixture()
def surface() -> GraphSurface:
    return GraphSurface(FakeGraph())


def test_the_frozen_four_are_declared_and_nothing_else():
    """The tool set may grow. It may not shrink, and a name may never be reused."""
    assert TOOL_NAMES == (
        "sync_whats_at_risk",
        "sync_explain_call_site",
        "sync_whats_changed",
        "sync_propose_patch",
    )
    assert [tool.name for tool in TOOLS] == list(TOOL_NAMES)


def test_every_tool_declares_a_description_and_an_object_schema():
    for tool in TOOLS:
        assert tool.description.strip()
        assert tool.input_schema["type"] == "object"
        assert isinstance(tool.input_schema["properties"], dict)


def test_every_declared_argument_has_a_type_so_an_agent_can_compose_against_it():
    for tool in TOOLS:
        for name, prop in tool.input_schema["properties"].items():
            assert "type" in prop, f"{tool.name}.{name} declares no type"
            assert prop.get("description", "").strip(), f"{tool.name}.{name} is undescribed"


def test_the_required_arguments_are_the_ones_the_surface_cannot_answer_without():
    required = {tool.name: set(tool.input_schema.get("required", [])) for tool in TOOLS}
    assert required["sync_whats_at_risk"] == set()
    assert required["sync_explain_call_site"] == {"file", "line"}
    assert required["sync_whats_changed"] == {"vendor"}
    assert required["sync_propose_patch"] == {"finding_id"}


def test_every_list_returning_tool_declares_pagination_arguments():
    """The spec's third response rule, enforced at the schema rather than in prose.

    A paginating implementation whose schema hides `limit` and `offset` is unpaginated as
    far as an agent is concerned -- it cannot ask for the second page.
    """
    for name in ("sync_whats_at_risk", "sync_whats_changed"):
        properties = next(t for t in TOOLS if t.name == name).input_schema["properties"]
        assert "limit" in properties
        assert "offset" in properties


def test_the_schemas_match_the_golden_file():
    """Adding a tool or an optional parameter is allowed -- update the golden file.

    Removing or renaming one is the breaking change the spec forbids, and this is what
    turns that rule from a sentence into a failing build.
    """
    assert schemas_as_data() == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_dispatch_reaches_the_surface_method_behind_each_read_tool(surface):
    at_risk = dispatch(surface, "sync_whats_at_risk", {})
    assert at_risk["items"][0]["file"] == "src/pay.ts"

    explained = dispatch(surface, "sync_explain_call_site", {"file": "src/pay.ts", "line": 12})
    assert explained["symbol"] == "stripe.charges.create"

    changed = dispatch(surface, "sync_whats_changed", {"vendor": "stripe"})
    assert changed["items"][0]["operation"] == "PostCharges"


def test_dispatch_passes_declared_arguments_through_by_name(surface):
    """A dispatcher that dropped an argument would silently answer a different question."""
    page = dispatch(surface, "sync_whats_at_risk", {"limit": 1, "offset": 1})
    assert page["items"] == []
    assert page["total"] == 1


def test_an_unknown_tool_is_refused_by_name(surface):
    with pytest.raises(KeyError) as excinfo:
        dispatch(surface, "sync_delete_everything", {})
    assert "sync_delete_everything" in str(excinfo.value)


def test_an_unknown_argument_is_refused_rather_than_silently_dropped(surface):
    """An agent that misspells an argument has asked a different question than it thinks.

    Answering anyway returns a plausible result for the wrong query, which is worse than
    an error the agent can correct.
    """
    with pytest.raises(TypeError):
        dispatch(surface, "sync_whats_changed", {"vendor": "stripe", "sinse": "2026-01-01"})
