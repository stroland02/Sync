"""Which model the patch agent drives, and where the request goes.

**This governs the whole of Sync's AI spend.** `sync.runner.claude_sdk` is the only file in the
product that imports a model SDK -- the telemetry path calls no model at all, it records spans of
calls that already happened -- so one module can honestly describe the cost surface.

Three shapes, one mechanism:

- **Frontier, default.** Nothing configured: the documented model against the vendor's own
  endpoint. What a first run gets.
- **Frontier, cheaper.** `SYNC_MODEL` names a smaller model. Same endpoint, same credential, less
  spend -- the cheapest change available and the one to reach for first.
- **Self-hosted or local.** `SYNC_MODEL_BASE_URL` points at a runtime the operator runs: Ollama,
  LM Studio, vLLM, or a gateway. **A local model is a base URL, not a second code path** -- they
  all speak a compatible API over a URL, so supporting them is pointing the client elsewhere
  rather than writing another client.

**And zero.** `StaticRunner` executes the pipeline with no model at all, which is the floor: a
deployment that wants the graph and the detectors without agent spend already has that, and this
module does not need to represent it because choosing a runner is a different decision from
configuring one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, Mapping

DEFAULT_MODEL = "claude-opus-5"

MODEL_VAR = "SYNC_MODEL"
BASE_URL_VAR = "SYNC_MODEL_BASE_URL"


class UnusableProvider(RuntimeError):
    """A configuration that would fail later, refused now with the fix named."""


@dataclass(frozen=True)
class ProviderConfig:
    """What the runner will drive, resolved once."""

    model: str
    base_url: str | None
    kind: Literal["anthropic", "self-hosted"]

    def describe(self) -> str:
        """One sentence for the console.

        Built here rather than in TypeScript: a second copy would eventually disagree about which
        provider is in use, and that is the sentence an operator checking their spend most needs
        to be right.
        """
        if self.base_url is None:
            return f"{self.model}, on the vendor's own endpoint"
        return f"{self.model}, on a self-hosted endpoint at {self.base_url}"


def _clean(env: Mapping[str, str], key: str) -> str | None:
    """A variable's value, or None when it is unset or blank.

    Blank is treated as unset because shell scripts export empty strings constantly, and reading
    one as a configured endpoint points the client at nowhere -- which then fails as a connection
    error rather than as a missing setting.
    """
    value = (env.get(key) or "").strip()
    return value or None


def resolve_provider(env: Mapping[str, str] | None = None) -> ProviderConfig:
    """The provider this process will use.

    `env` is injectable so a test names its own rather than mutating the process, and so the
    console can resolve a configuration it is only describing.
    """
    source = os.environ if env is None else env
    model = _clean(source, MODEL_VAR)
    base_url = _clean(source, BASE_URL_VAR)

    if base_url is not None and model is None:
        # A local runtime serves whatever it serves, and the default is a frontier model name.
        # Sending `claude-opus-5` to Ollama asks for a model it does not have, and the failure
        # arrives opaque and mid-repair. Naming the fix here costs one line and saves that.
        raise UnusableProvider(
            f"{BASE_URL_VAR} names a self-hosted endpoint but {MODEL_VAR} is unset, so the "
            f"runner would ask it for '{DEFAULT_MODEL}'. Set {MODEL_VAR} to a model that "
            f"endpoint actually serves."
        )

    return ProviderConfig(
        model=model or DEFAULT_MODEL,
        base_url=base_url,
        kind="self-hosted" if base_url is not None else "anthropic",
    )
