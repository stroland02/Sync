"""Which model the patch agent drives, and where it sends the request.

**There is exactly one model cost in this product.** `src/sync/runner/claude_sdk.py` is the only
file that imports a model SDK; the telemetry path calls no model at all -- it records spans of
calls that already happened. So this module governs the whole of Sync's AI spend, which is why it
is worth a test file rather than a constant.

The owner's requirement: run against the frontier default, against a user's own key, or against a
local model, without a fork.
"""

from __future__ import annotations

import pytest

from sync.runner.provider import (
    DEFAULT_MODEL,
    ProviderConfig,
    UnusableProvider,
    resolve_provider,
)


def test_the_default_is_the_frontier_model_and_needs_no_configuration():
    """A deployment that sets nothing gets the documented default rather than an error."""
    config = resolve_provider(env={})

    assert config.model == DEFAULT_MODEL
    assert config.base_url is None
    assert config.kind == "anthropic"


def test_a_model_override_is_honoured_without_changing_the_endpoint():
    """The cheapest change available: same provider, smaller model."""
    config = resolve_provider(env={"SYNC_MODEL": "claude-haiku-4-5-20251001"})

    assert config.model == "claude-haiku-4-5-20251001"
    assert config.kind == "anthropic"
    assert config.base_url is None


def test_a_base_url_makes_it_a_local_or_self_hosted_provider():
    """A local runtime is a base URL, not a separate code path.

    Ollama, LM Studio and vLLM all speak an Anthropic- or OpenAI-compatible API over a URL, so
    supporting them is pointing the client somewhere else rather than writing a second client.
    """
    config = resolve_provider(
        env={"SYNC_MODEL_BASE_URL": "http://localhost:11434", "SYNC_MODEL": "qwen2.5-coder"}
    )

    assert config.kind == "self-hosted"
    assert config.base_url == "http://localhost:11434"
    assert config.model == "qwen2.5-coder"


def test_a_base_url_with_no_model_named_is_refused():
    """A local endpoint serves whatever it serves, and the default is a frontier model name.

    Silently sending `claude-opus-5` to a local runtime asks it for a model it does not have, and
    the failure arrives from the runtime as an opaque error at the worst moment -- mid-repair.
    Refusing here names the fix instead.
    """
    with pytest.raises(UnusableProvider) as raised:
        resolve_provider(env={"SYNC_MODEL_BASE_URL": "http://localhost:11434"})

    assert "SYNC_MODEL" in str(raised.value)


def test_blank_values_fall_back_rather_than_configuring_an_empty_provider():
    """An unset variable and a variable set to whitespace are the same intent.

    Shell scripts export empty strings constantly; treating one as a configured endpoint would
    point the client at nowhere and fail as a connection error rather than as a missing setting.
    """
    config = resolve_provider(env={"SYNC_MODEL": "   ", "SYNC_MODEL_BASE_URL": ""})

    assert config.model == DEFAULT_MODEL
    assert config.base_url is None


def test_the_config_describes_itself_for_the_console():
    """Settings shows what is configured, and the description is built here rather than there.

    A second copy in TypeScript would be the fact written twice that this repository keeps paying
    for -- and this one would disagree about which provider is in use, which is the sentence an
    operator checking their spend most needs to be right.
    """
    local = resolve_provider(env={"SYNC_MODEL_BASE_URL": "http://localhost:11434", "SYNC_MODEL": "qwen"})
    frontier = resolve_provider(env={})

    assert "localhost:11434" in local.describe()
    assert DEFAULT_MODEL in frontier.describe()
    assert isinstance(frontier, ProviderConfig)
