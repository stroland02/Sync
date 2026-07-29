"""Resolving a watched MCP server through the registry.

`McpServerAdapter` was complete, tested and constructed nowhere, and the reason was a shape
mismatch rather than an oversight: `_BUILDERS` maps one vendor id to one builder, which suits a
vendor that publishes one API. MCP is a protocol, and every server watched is a separate
catalogue -- so an entry keyed `mcp` would have had to name one particular server, which is the
vendor knowledge `registry.py` exists to keep out.

The resolution is the shape `generated-vendors.yaml` already uses: a deployment declares its
servers in configuration, one entry each, and the registry learns a file format rather than a
server. The property that whole design turns on is the two-server case below -- a single-server
test cannot tell a working design from one that hardcoded the only server it was shown.

Nothing here contacts a server. The captures are committed, which is the same rule every other
vendor's fixtures follow.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sync.signals import registry
from sync.signals.mcp_server.adapter import McpServerAdapter

FIXTURES = Path(__file__).parent / "fixtures" / "mcp_servers"
SERVERS = FIXTURES / "servers.yaml"

DOCS = "mcp:example-docs"
SEARCH = "mcp:example-search"

BEFORE, AFTER = "2026-06-01", "2026-07-01"


@pytest.fixture()
def configured(monkeypatch, tmp_path):
    """Point the registry at the committed two-server file, the way a deployment would."""
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(SERVERS))
    return registry.VendorContext(cache_dir=tmp_path, from_version=BEFORE, to_version=AFTER)


# --- a configured server resolves -------------------------------------------------


def test_a_configured_server_resolves_to_the_mcp_adapter(configured):
    """Through the registry rather than by construction here. Constructing one in the test
    would prove the adapter works, which was never in doubt -- what was missing is any path
    from a vendor id to it."""
    assert isinstance(registry.load_vendor(DOCS, configured), McpServerAdapter)


def test_preparing_a_server_reaches_no_network_and_stages_nothing(configured):
    """There is nothing to stage. A REST vendor's preparation downloads a specification; a
    watched server's captures were taken by something else and are the input rather than the
    output, so `documents` is empty and no fetch happens."""
    prepared = registry.prepare_vendor(DOCS, configured)

    assert isinstance(prepared.adapter, McpServerAdapter)
    assert prepared.documents == ()


def test_a_configured_server_produces_its_own_changes(configured):
    """End to end through the registry: the `docs` captures drop a tool between them, and the
    adapter the registry built reports it."""
    changes = list(registry.load_vendor(DOCS, configured).fetch_changes(BEFORE, AFTER))

    assert [change.operation_id for change in changes] == ["list_spaces"]
    assert changes[0].vendor_id == DOCS


# --- two servers, which is the property the design turns on -----------------------


def test_two_configured_servers_resolve_to_distinct_adapters(configured):
    """The case a single-server design passes and a correct one has to. Two catalogues under
    one protocol, and neither is "the" MCP vendor."""
    docs = registry.load_vendor(DOCS, configured)
    search = registry.load_vendor(SEARCH, configured)

    assert docs is not search
    assert docs.vendor_id != search.vendor_id
    assert {docs.vendor_id, search.vendor_id} == {DOCS, SEARCH}


def test_two_servers_rows_do_not_collide(configured):
    """Every row in the graph is keyed by `vendor_id`, so two servers sharing one id would
    merge two unrelated catalogues into a single history. They report different failures here
    -- a removed tool against a newly required argument -- so a test cannot pass by reading
    one server's captures twice.
    """
    docs = list(registry.load_vendor(DOCS, configured).fetch_changes(BEFORE, AFTER))
    search = list(registry.load_vendor(SEARCH, configured).fetch_changes(BEFORE, AFTER))

    assert {change.vendor_id for change in docs} == {DOCS}
    assert {change.vendor_id for change in search} == {SEARCH}
    assert {change.operation_id for change in docs}.isdisjoint(
        {change.operation_id for change in search}
    )


def test_servers_without_a_declared_directory_still_get_one_each(tmp_path, monkeypatch):
    """The default location, which is per server id for a reason worth pinning: a capture is
    named `tools_list_<capture>.json` with nothing in the filename identifying the server, so
    one shared directory would have two servers overwriting each other's history and each
    reading the other's tools.

    Both entries omit `snapshot_dir`, which is the path the fixture file never exercises.
    """
    captures = tmp_path / registry.MCP_SNAPSHOT_DIRNAME
    for server, tools in (("alpha", ["kept", "dropped"]), ("beta", ["kept"])):
        (captures / server).mkdir(parents=True)
        for version, names in ((BEFORE, tools), (AFTER, ["kept"])):
            (captures / server / f"tools_list_{version}.json").write_text(
                json.dumps({"result": {"tools": [
                    {"name": name, "description": "d",
                     "inputSchema": {"type": "object", "properties": {}}}
                    for name in names
                ]}}),
                encoding="utf-8",
            )

    config = tmp_path / "defaults.yaml"
    config.write_text("- server_id: alpha\n- server_id: beta\n", encoding="utf-8")
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(config))
    context = registry.VendorContext(cache_dir=tmp_path, from_version=BEFORE, to_version=AFTER)

    alpha = list(registry.load_vendor("mcp:alpha", context).fetch_changes(BEFORE, AFTER))
    beta = list(registry.load_vendor("mcp:beta", context).fetch_changes(BEFORE, AFTER))

    assert [change.operation_id for change in alpha] == ["dropped"]
    assert beta == []


def test_a_watched_server_is_listed_among_the_available_vendors(configured):
    """A configured vendor the command line refuses is registered and unreachable, which is the
    shape of defect this path exists to close -- `available_vendors` already includes configured
    generated vendors for the same reason."""
    available = registry.available_vendors()

    assert DOCS in available and SEARCH in available


# --- identity ---------------------------------------------------------------------


def test_the_vendor_id_is_declared_rather_than_derived(configured, tmp_path, monkeypatch):
    """What makes the id survive a server moving. It is the operator's own `server_id`, never
    the endpoint, the host, or anything the server advertises about itself -- so a server that
    changes URL keeps its history, and nothing about the captures can rename it.

    Asserted by pointing a second entry at the *same* captures under a different id: identical
    content, two identities, which is only possible if the id comes from the declaration.
    """
    config = tmp_path / "moved.yaml"
    config.write_text(
        "- server_id: example-docs\n"
        f"  snapshot_dir: {(FIXTURES / 'docs').as_posix()}\n"
        "- server_id: docs-behind-a-new-url\n"
        f"  snapshot_dir: {(FIXTURES / 'docs').as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(config))

    original = registry.load_vendor(DOCS, configured)
    moved = registry.load_vendor("mcp:docs-behind-a-new-url", configured)

    assert original.vendor_id != moved.vendor_id
    # Same captures, so the same substance -- and two identities over it. The rows themselves
    # are not equal precisely because each is keyed by its own vendor id, which is the property
    # under test rather than a difference to look past.
    assert [(c.kind, c.operation_id) for c in original.fetch_changes(BEFORE, AFTER)] == [
        (c.kind, c.operation_id) for c in moved.fetch_changes(BEFORE, AFTER)
    ]


def test_two_entries_sharing_an_id_are_refused(tmp_path, monkeypatch):
    """A duplicate id is two catalogues writing one history, and the later entry silently
    winning is the worst of the three possible outcomes."""
    config = tmp_path / "duplicate.yaml"
    config.write_text(
        "- server_id: twice\n  snapshot_dir: a\n- server_id: twice\n  snapshot_dir: b\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(config))

    with pytest.raises(ValueError, match="twice"):
        registry.available_vendors()


def test_an_entry_missing_a_field_is_refused_naming_the_file(tmp_path, monkeypatch):
    config = tmp_path / "broken.yaml"
    config.write_text("- snapshot_dir: somewhere\n", encoding="utf-8")
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(config))

    with pytest.raises(ValueError, match=str(config.name)):
        registry.available_vendors()


# --- what must not regress --------------------------------------------------------


@pytest.mark.parametrize("vendor_id", ["stripe", "twilio"])
def test_the_hand_written_vendors_still_resolve(configured, vendor_id):
    """The regression that matters. A third resolution path that shadowed the coded adapters
    would swap a resolving adapter for one that answers `operation_for_symbol` with None."""
    assert vendor_id in registry.available_vendors()
    assert registry._builders(vendor_id) is not None


def test_an_unknown_server_fails_naming_what_is_available(configured):
    """No silent default, matching what the registry already does for an unknown vendor. A
    fallback here would attribute one server's changes to another."""
    with pytest.raises(KeyError) as raised:
        registry.load_vendor("mcp:never-configured", configured)

    assert DOCS in str(raised.value)


def test_the_registry_names_no_server():
    """The property a later change will quietly undo, so it is asserted rather than trusted.

    `registry.py` may know the file format and the protocol's id prefix -- the prefix lives in
    the adapter and is imported -- and it must not know that any particular server exists. The
    fixture ids are the ones a careless wiring would have reached for.
    """
    source = Path(registry.__file__).read_text(encoding="utf-8")

    for name in ("example-docs", "example-search", "docs-behind-a-new-url"):
        assert name not in source


def test_no_configured_server_is_a_legitimate_deployment(monkeypatch, tmp_path):
    """An absent file is zero watched servers, not an error -- the same judgement
    `generated-vendors.yaml` makes. Every other vendor still resolves."""
    monkeypatch.setenv(registry.MCP_SERVERS_VARIABLE, str(tmp_path / "absent.yaml"))

    available = registry.available_vendors()

    assert "stripe" in available
    assert not [vendor for vendor in available if vendor.startswith("mcp:")]


def test_the_shipped_file_configures_no_server():
    """Recorded as a test because the alternative is an entry invented to look complete.

    Nothing captures a `tools/list` yet, so there is no way to confirm a real server the way
    every `generated-vendors.yaml` entry was confirmed -- by fetching the path and committing
    the response. A configured server whose captures nobody takes is a vendor that registers,
    is offered on the command line, and fails on first use.
    """
    monkeypatch_free = os.environ.get(registry.MCP_SERVERS_VARIABLE)
    assert monkeypatch_free is None or Path(monkeypatch_free) != registry.MCP_SERVERS_FILE

    assert registry._mcp_servers.__doc__ is not None
    assert registry.MCP_SERVERS_FILE.exists()
    assert registry._read_mcp_servers(registry.MCP_SERVERS_FILE) == {}
