"""Which model the patch agent drives, where the request goes, and whose credential pays.

**This governs the whole of Sync's AI spend.** `sync.runner.claude_sdk` is the only file in the
product that imports a model SDK -- the telemetry path calls no model at all, it records spans of
calls that already happened -- so one module can honestly describe the cost surface.

## The operator's credential is never inherited

**Owner ruling, 2026-08-19.** An earlier version of this module defaulted to a frontier model on
the vendor's own endpoint, which meant a deployment that configured nothing would spend whoever
installed it the first time a repair ran. Nobody chose that, and a bill nobody chose is the wrong
default whatever the model.

So **unconfigured is the default state**, and it is a state rather than an error: the console asks
what is set up, and a Settings screen that raised on a fresh install would be worse than one that
says *connect a model*. The runner asks a stricter question and gets `require_provider`, which
refuses before spending rather than after failing.

Three ways to connect one, and the third costs nothing:

- **Frontier.** `SYNC_MODEL` names the model, `SYNC_MODEL_API_KEY` carries the user's own key.
- **Self-hosted or local.** `SYNC_MODEL_BASE_URL` points at a runtime the operator runs -- Ollama,
  LM Studio, vLLM. No credential, because there is nobody to bill. **A local model is a base URL,
  not a second code path**: they all speak a compatible API over a URL.
- **None at all.** `StaticRunner` executes the pipeline with no model, which is the floor: the
  graph, the detectors and the findings without any agent spend.

## The key is read, never held

`CLAUDE.md`'s rule is unqualified: we never hold customer secrets. This module reads the variable
to answer *is one present* and puts a boolean on the config. Nothing here stores it, logs it, or
returns it, and `test_model_provider.py` asserts it appears in neither `repr()` nor `describe()` --
a config object carrying a key is one log line from leaking it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

MODEL_VAR = "SYNC_MODEL"
BASE_URL_VAR = "SYNC_MODEL_BASE_URL"
# Deliberately not `ANTHROPIC_API_KEY`. That variable is frequently already set in a developer's
# environment by an unrelated tool, and reading it would be the credential inheritance this
# module exists to prevent -- silently, and looking like configuration.
API_KEY_VAR = "SYNC_MODEL_API_KEY"

ProviderKind = Literal["unconfigured", "frontier", "self-hosted"]


class UnusableProvider(RuntimeError):
    """A configuration that would fail later, refused now with the fix named."""


class ProviderNotConfigured(RuntimeError):
    """No model is connected, raised where one is required rather than merely described."""


@dataclass(frozen=True)
class ProviderConfig:
    """What the runner would drive, resolved once. Carries no secret."""

    kind: ProviderKind
    model: str | None
    base_url: str | None
    has_credential: bool
    #: Empty when this config can run. A sentence naming what is missing otherwise.
    blocked_because: str = ""

    @property
    def usable(self) -> bool:
        return self.kind != "unconfigured" and not self.blocked_because

    def describe(self) -> str:
        """One sentence for the console.

        Built here rather than in TypeScript: a second copy would eventually disagree about which
        provider is in use, which is the sentence an operator checking their spend most needs to
        be right.
        """
        if self.kind == "unconfigured":
            return "No model connected, so no repair can be written and nothing is being spent."
        if self.kind == "self-hosted":
            return f"{self.model}, on a self-hosted endpoint at {self.base_url}"
        if not self.has_credential:
            return f"{self.model}, with no credential supplied yet"
        return f"{self.model}, on the vendor's endpoint, with your own credential"


def _clean(env: Mapping[str, str], key: str) -> str | None:
    """A variable's value, or None when unset or blank.

    Blank is unset because shell scripts export empty strings constantly, and reading one as a
    configured endpoint points the client at nowhere -- which then fails as a connection error
    rather than as a missing setting.
    """
    value = (env.get(key) or "").strip()
    return value or None


def resolve_provider(env: Mapping[str, str] | None = None) -> ProviderConfig:
    """What is connected, as a state the console can render.

    `env` is injectable so a test names its own rather than mutating the process, and so the
    console can resolve a configuration it is only describing.
    """
    source = os.environ if env is None else env
    model = _clean(source, MODEL_VAR)
    base_url = _clean(source, BASE_URL_VAR)
    has_key = _clean(source, API_KEY_VAR) is not None

    if base_url is not None and model is None:
        # A local runtime serves whatever it serves. Guessing a frontier name asks it for a model
        # it does not have, and that failure arrives opaque and mid-repair.
        raise UnusableProvider(
            f"{BASE_URL_VAR} names a self-hosted endpoint but {MODEL_VAR} is unset, so the runner "
            f"would have nothing to ask it for. Set {MODEL_VAR} to a model that endpoint serves."
        )

    if base_url is not None:
        return ProviderConfig(
            kind="self-hosted",
            model=model,
            base_url=base_url,
            has_credential=has_key,
        )

    if model is not None:
        return ProviderConfig(
            kind="frontier",
            model=model,
            base_url=None,
            has_credential=has_key,
            blocked_because=(
                ""
                if has_key
                else f"a credential is required for a hosted model: set {API_KEY_VAR} to your own key"
            ),
        )

    return ProviderConfig(
        kind="unconfigured",
        model=None,
        base_url=None,
        has_credential=has_key,
        blocked_because=(
            f"no model is connected: set {MODEL_VAR} with {API_KEY_VAR} for a hosted model, "
            f"or {BASE_URL_VAR} with {MODEL_VAR} for one you run yourself"
        ),
    )


def require_provider(env: Mapping[str, str] | None = None) -> ProviderConfig:
    """The provider, or a refusal.

    The runner's question rather than the console's: refuse before spending, not after failing.
    """
    config = resolve_provider(env)
    if not config.usable:
        raise ProviderNotConfigured(config.blocked_because)
    return config
