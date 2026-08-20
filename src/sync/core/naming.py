"""A finding's display name: something two people can say to each other.

M15 Task 6. A finding is addressed by a 32-character hex id, which is correct for a key and
useless in a sentence -- the plan's problem statement is exactly *two people cannot discuss one*.

**Derived, never stored.** `GraphStore.insert_finding` computes a finding's id from its natural
key on every scan, so re-derivation converges on the row it already wrote. A name computed from
that id inherits the same property for free, and needs no column, no migration and no second
thing that can disagree with the first.

**A random word pair was refused**, and the reason is worth keeping: it would not survive
re-hashing. A name that changes on re-scan is worse than an id, because a reader who wrote it in
a ticket now holds a reference to nothing.

**This is a display name, not an identifier.** The id remains the addressable thing -- every URL,
every API path and every join still uses it. What this earns is the sentence *"the stripe
postcharges one, 4b1c9e"*, which the id cannot be spoken as.

The one thing it inherits and does not fix: a call site's id is derived from its position, so a
finding whose call moves to another line is a different finding with a different name. That is the
id's own behaviour, and hiding it behind a name that survived the move would be claiming a
continuity the graph does not record.

`sync.core` imports nothing from a sibling package, and this module holds to that -- it is
`hashlib` and string handling, so a third party writing a vendor adapter can name a finding
without acquiring a database driver.
"""

from __future__ import annotations

import hashlib
import re

# How much of the operation reaches the name. A sixty-character name is not memorable, which is
# the only thing this function is for; truncation is safe because the discriminator below is
# computed from the untruncated identity.
_OPERATION_MAX = 18

# Hex digits of discriminator. Six rather than four, and the arithmetic is the reason: at four
# digits a workspace of two thousand findings is better than even money to collide, and a
# collision is two different findings a reader cannot tell apart by the name on screen.
_DISCRIMINATOR = 6

_NOT_SLUG = re.compile(r"[^a-z0-9]+")


def _slug(raw: str, limit: int) -> str:
    """Lowercase, `[a-z0-9-]` only, no run of separators, trimmed to `limit`.

    A vendor id can carry a dot and an operation id a slash or a brace. Slugged once here rather
    than escaped at each place a name is used -- a branch, a URL, a grep -- because the one that
    got forgotten would be the one that broke.
    """
    slug = _NOT_SLUG.sub("-", raw.strip().lower()).strip("-")
    return slug[:limit].strip("-")


def finding_name(vendor_id: str, operation_id: str, finding_id: str) -> str:
    """A short, stable, human-sayable name for one finding.

    `stripe-postcharges-4b1c9e` -- the integration, the operation, and enough of the finding's own
    identity to tell it from its siblings on the same operation.

    Raises `ValueError` on an empty `finding_id`: with no id there is no discriminator, and a name
    without one collides silently. A caller reaching here without an id has a defect upstream, and
    returning `stripe-postcharges-` would hide it behind something that still looks like a name.
    """
    if not finding_id.strip():
        raise ValueError("finding_id is required: a name with no discriminator collides silently")

    # Over the id rather than over the readable parts, so two findings sharing a vendor, an
    # operation and a truncated prefix still differ -- which is the case truncation creates.
    discriminator = hashlib.sha256(finding_id.strip().encode()).hexdigest()[:_DISCRIMINATOR]

    parts = [part for part in (_slug(vendor_id, 24), _slug(operation_id, _OPERATION_MAX)) if part]
    parts.append(discriminator)
    return "-".join(parts)
