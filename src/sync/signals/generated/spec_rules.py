"""Symbol rules that read a specification, keyed by the name a configuration row states.

Separate from `EXTRACTORS` because the two answer different questions from different inputs. An
extraction rule reads a staged SDK *checkout* and states `extract_symbols(source_root)`; a rule
here reads the *specification* and states `build_symbol_map(document, sdk_document)`. Registering
one in the other's registry fails `register_extraction_rules`, correctly, and collapsing the two
would mean a caller could no longer tell which input a rule needs.

A row names one of these when the tier has to build its symbol map rather than read a checkout --
which is the last thing the two hand-written adapters did that a configuration row could not.
"""

from __future__ import annotations

from typing import Callable, Mapping

from sync.signals.generated.symbols_stripe_openapi import build_symbol_map as _stripe_openapi

SpecSymbolRule = Callable[..., Mapping[str, Mapping[str, object]]]

SPEC_SYMBOL_RULES: dict[str, SpecSymbolRule] = {
    "stripe-openapi": _stripe_openapi,
}
