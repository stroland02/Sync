"""Reducing a call site to what is safe to keep.

`docs/superpowers/specs/2026-07-25-sync-migration-corpus.md` argues the corpus is only worth
having if it can be reasoned across customers, and it can only be reasoned across customers if
nothing in it identifies one. So a symbol becomes a shape, argument keys become salted digests,
and source text never enters at all.

Two properties are in tension and both are required. Rows must be *comparable* -- two companies
calling the same SDK method have to produce the same shape, or aggregation says nothing. And
rows must be *opaque* -- a shape that kept `charges` would leak which products a customer
integrates, and a table of those is a customer list.
"""

from __future__ import annotations

import hashlib

_VERB = "<verb>"
_CLIENT = "<client>"
_RESOURCE = "<resource>"


def symbol_shape(symbol: str) -> str:
    """A dotted symbol reduced to its structure.

    `stripe.charges.create` becomes `<client>.<resource>.<verb>`. Depth is kept because it
    distinguishes a top-level resource from a nested one, and that distinction predicts how
    mechanical a migration is. Names are not kept, because they are the identifying part.
    """
    parts = symbol.split(".")
    if len(parts) == 1:
        return _VERB

    shaped = [_CLIENT] + [_RESOURCE] * (len(parts) - 2) + [_VERB]
    return ".".join(shaped)


def hash_arg_keys(keys: list[str], salt: str) -> list[str]:
    """Argument keys as salted digests, sorted.

    Salted per deployment because the keys are guessable: an unsalted digest of `amount` is
    `amount` to anyone willing to hash a wordlist, which would make the column a plain-text
    record of what a customer sends.

    Sorted because two call sites passing the same keys in a different order are the same
    shape, and rows that disagree on ordering cannot be grouped.
    """
    return sorted(
        hashlib.sha256(f"{salt}:{key}".encode("utf-8")).hexdigest()[:32] for key in keys
    )
