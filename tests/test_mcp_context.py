import json

import pytest

from sync.mcp.resources import (
    CONTEXT_MIME_TYPE,
    CONTEXT_URI_TEMPLATE,
    ResourceError,
    read,
    resource_templates_as_data,
)
from sync.mcp.server import SERVER_INSTRUCTIONS


def test_the_context_template_is_advertised():
    templates = {t["uriTemplate"] for t in resource_templates_as_data()}
    assert CONTEXT_URI_TEMPLATE in templates
    assert "sync://feed/{vendor}" in templates


def test_the_context_template_declares_markdown():
    template = next(
        t for t in resource_templates_as_data() if t["uriTemplate"] == CONTEXT_URI_TEMPLATE
    )
    assert template["mimeType"] == CONTEXT_MIME_TYPE


def test_reading_a_repository_with_context_returns_its_body():
    result = read(
        "sync://context/github.com/acme/storefront",
        feed=None,
        known_vendors=(),
        context_reader=lambda repo_id: "Package manager is pnpm.",
    )
    assert result["contents"][0]["text"] == "Package manager is pnpm."
    assert result["contents"][0]["mimeType"] == CONTEXT_MIME_TYPE


def test_reading_a_repository_with_no_context_is_an_error_rather_than_an_empty_string():
    """An empty resource and a repository nobody has described are different facts.

    A client that received "" has no way to tell them apart, and would report the repository as
    described-with-nothing.
    """
    with pytest.raises(ResourceError):
        read(
            "sync://context/github.com/acme/storefront",
            feed=None,
            known_vendors=(),
            context_reader=lambda repo_id: None,
        )


def test_a_server_with_no_context_reader_refuses_rather_than_returning_nothing():
    with pytest.raises(ResourceError):
        read("sync://context/anything", feed=None, known_vendors=())


def test_the_repo_id_keeps_its_slashes():
    """`repo_id` is host/owner/name. A parser that split on the first slash would look up
    'github.com' and find nothing, for every repository."""
    seen = []
    read(
        "sync://context/github.com/acme/storefront",
        feed=None,
        known_vendors=(),
        context_reader=lambda repo_id: seen.append(repo_id) or "body",
    )
    assert seen == ["github.com/acme/storefront"]


def test_the_instructions_name_no_tool_that_does_not_exist():
    from sync.mcp.registry import schemas_as_data

    published = {schema["name"] for schema in schemas_as_data()}
    for word in SERVER_INSTRUCTIONS.split():
        candidate = word.strip("`.,()")
        if candidate.startswith("sync_"):
            assert candidate in published, f"instructions name an absent tool: {candidate}"


def test_the_tool_schemas_golden_file_is_untouched():
    """The tripwire on the frozen four. If this design ever needs the golden file regenerated,
    the design is wrong."""
    from pathlib import Path

    from sync.mcp.registry import schemas_as_data

    golden = json.loads(
        (Path(__file__).parent / "golden" / "tool_schemas.json").read_text(encoding="utf-8")
    )
    assert schemas_as_data() == golden
