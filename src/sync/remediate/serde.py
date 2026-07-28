"""Registration of Sync's own types with LangGraph's checkpoint serialiser.

`sync.core` cannot do this for itself and must not: it imports nothing from a
sibling and nothing from the orchestration stack, because a third party writing
a vendor adapter depends on it alone. `sync.remediate` already depends on both,
so the registration lives here and the models stay clean.
"""

from __future__ import annotations

import copy

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from sync.core import CallSite, Evidence, Finding, Patch, RepoRef, VendorChange

# Every sync.core model a RunState carries into a checkpoint. Written out rather
# than derived from the module, because an allowlist that discovers its own
# entries admits whatever anyone adds to `sync.core.models` later.
# `tests/test_checkpoint_serde.py` fails if RunState gains a model this misses.
CHECKPOINTED_TYPES = (CallSite, Evidence, Finding, Patch, RepoRef, VendorChange)


def with_sync_types(checkpointer):
    """Return `checkpointer` with a serialiser that reads Sync's types back as models.

    LangGraph's default allowlist is permissive: it admits every type and logs
    that the permission is temporary. An explicit allowlist is both what silences
    that and what a future version will require -- and it fails open, not closed.
    A type missing from one is reconstructed as its raw `model_dump()` dict
    rather than refused, so the failure surfaces as an AttributeError inside a
    node resuming a run, not at the load that caused it.

    `BaseCheckpointSaver.with_allowlist` looks like the way to do this and is
    not: it returns the saver untouched whenever the existing allowlist is the
    permissive default, which is the only case that needs changing.
    """
    clone = copy.copy(checkpointer)
    clone.serde = JsonPlusSerializer(
        # Carried over rather than defaulted: registering types must not turn a
        # caller's pickle fallback back off.
        pickle_fallback=checkpointer.serde.pickle_fallback,
        allowed_msgpack_modules=CHECKPOINTED_TYPES,
    )
    return clone
