"""Reducing a call site to what is safe to keep.

`docs/superpowers/specs/2026-07-25-sync-migration-corpus.md` argues the corpus is only worth
having if it can be reasoned across customers, and it can only be reasoned across customers if
nothing in it identifies one. So a symbol becomes a shape, argument keys become salted digests,
and source text never enters at all.

Two properties are in tension, and the resolution is that they apply to different columns
rather than to every column at once. An earlier version of this docstring claimed rows are
comparable and the `MigrationOutcome` docstring claimed the table is safe to aggregate; both
were true of the shape columns and false of the hashed ones, which is a contradiction someone
would only discover after writing a GROUP BY that silently returns nothing.

Comparable ACROSS deployments: `symbol_shape`, `arg_arity`,
`response_fields_touched_count`, and everything derived from the vendor change. These carry no
salt, so two companies calling the same SDK method produce identical values and aggregation
across them means something. This is the axis the corpus exists to measure -- which change
kinds are mechanically safe.

Comparable WITHIN one deployment only: `arg_key_hashes`. The salt is per deployment by design,
so the same key hashes differently for every customer. Grouping on it across deployments
returns one group per customer and looks like an answer. Within a deployment it does what it is
for: telling whether two call sites pass the same arguments, without recording which.

Opaque everywhere: a shape that kept `charges` would leak which products a customer integrates,
and a table of those is a customer list.
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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


def hash_request_target(url: str, salt: str) -> str:
    """An observed request URL as a salted digest.

    The only question this answers is whether two observed calls went to the same place, which
    is what separates fetching three charges from fetching one charge three times. Answering it
    needs no URL, so no URL is kept: the digest is one-way and the salt is per deployment,
    because the URL space is enumerable and an unsalted digest of `/v1/charges` is `/v1/charges`
    to anyone willing to hash a wordlist.

    The whole URL, not the path. A different `limit` is a different call and the page-size
    finding is precisely that difference. Query parameters are sorted first, so two spellings of
    one request do not look like two calls -- SDKs and proxies do not agree on parameter order.
    The fragment is dropped because it never reaches the server.

    Comparable WITHIN one deployment only, like `arg_key_hashes` and for the same reason.
    """
    split = urlsplit(url)
    normalised = urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(sorted(parse_qsl(split.query, keep_blank_values=True))),
            "",
        )
    )
    return hashlib.sha256(f"{salt}:{normalised}".encode("utf-8")).hexdigest()[:32]
