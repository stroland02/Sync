"""Which model the patch agent drives, where the request goes, and whose credential pays.

**There is exactly one model cost in this product.** `src/sync/runner/claude_sdk.py` is the only
file that imports a model SDK; the telemetry path calls no model at all -- it records spans of
calls that already happened. So this module governs the whole of Sync's AI spend.

**Owner ruling, 2026-08-19: the operator's own credential is never inherited.** A deployment that
configures nothing must not quietly bill whoever installed it. So the default is *unconfigured*,
the patch agent refuses rather than guessing, and the user connects their own frontier key or their
own local model. The key itself is never stored -- `CLAUDE.md`'s unqualified rule -- so this module
reads a variable and reports only whether one is present.
"""

from __future__ import annotations

import pytest

from sync.runner.provider import (
    API_KEY_VAR,
    ProviderConfig,
    ProviderNotConfigured,
    UnusableProvider,
    resolve_provider,
)


def test_nothing_configured_is_unconfigured_rather_than_a_default_frontier_model():
    """The ruling this file exists for.

    A default that reached Anthropic would spend the operator's own credential the first time a
    repair ran, without anybody choosing it. Unconfigured is the honest state and it is reported
    rather than raised, because the console asks what is set up and a Settings screen that 500s on
    a fresh install is worse than one that says *connect a model*.
    """
    config = resolve_provider(env={})

    assert config.kind == "unconfigured"
    assert config.model is None
    assert config.usable is False


def test_a_frontier_model_needs_both_a_model_and_a_key():
    """Naming a model without a credential is a configuration nobody can run."""
    config = resolve_provider(env={"SYNC_MODEL": "claude-haiku-4-5-20251001"})

    assert config.kind == "frontier"
    assert config.usable is False
    assert "credential" in config.blocked_because.lower()


def test_a_frontier_model_with_a_key_is_usable_and_the_key_is_not_carried():
    """The key is read for presence and never stored on the config.

    `CLAUDE.md`: we never hold customer secrets, unqualified. A config object that carried the key
    would be one `repr()` from a log line, so it carries a boolean instead.
    """
    config = resolve_provider(
        env={"SYNC_MODEL": "claude-haiku-4-5-20251001", API_KEY_VAR: "sk-ant-real-key"}
    )

    assert config.usable is True
    assert config.has_credential is True
    assert "sk-ant-real-key" not in repr(config)
    assert "sk-ant-real-key" not in config.describe()


def test_a_local_endpoint_is_usable_without_any_credential():
    """A model on the operator's own machine has nobody to bill.

    This is the zero-cost path the owner asked for, and requiring a key here would make the free
    option look unavailable.
    """
    config = resolve_provider(
        env={"SYNC_MODEL_BASE_URL": "http://localhost:11434", "SYNC_MODEL": "qwen2.5-coder"}
    )

    assert config.kind == "self-hosted"
    assert config.usable is True
    assert config.has_credential is False


def test_a_base_url_with_no_model_named_is_refused():
    """A local runtime serves what it serves, and guessing a frontier name fails mid-repair."""
    with pytest.raises(UnusableProvider) as raised:
        resolve_provider(env={"SYNC_MODEL_BASE_URL": "http://localhost:11434"})

    assert "SYNC_MODEL" in str(raised.value)


def test_blank_values_fall_back_rather_than_configuring_an_empty_provider():
    """Shell scripts export empty strings constantly; one is not a configuration."""
    config = resolve_provider(env={"SYNC_MODEL": "  ", "SYNC_MODEL_BASE_URL": "", API_KEY_VAR: " "})

    assert config.kind == "unconfigured"
    assert config.has_credential is False


def test_requiring_a_provider_raises_when_none_is_connected():
    """The patch agent's own guard: refuse before spending rather than after failing.

    `resolve_provider` reports, `require_provider` insists. The two exist separately because the
    console asks the first question and the runner asks the second.
    """
    from sync.runner.provider import require_provider

    with pytest.raises(ProviderNotConfigured) as raised:
        require_provider(env={})

    assert "SYNC_MODEL" in str(raised.value)


def test_the_config_describes_itself_for_the_console():
    """Settings renders this sentence, built here so two surfaces cannot disagree."""
    local = resolve_provider(
        env={"SYNC_MODEL_BASE_URL": "http://localhost:11434", "SYNC_MODEL": "qwen"}
    )
    none = resolve_provider(env={})

    assert "localhost:11434" in local.describe()
    assert "no model" in none.describe().lower()
    assert isinstance(none, ProviderConfig)
