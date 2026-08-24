"""How each fact in the prompt was established, said rather than assumed.

`Finding.binding_rung` records how a call site came to be attributed to an operation -- read out
of source, inferred by a resolution step, or watched in traffic -- and the prompt carried none of
it. An agent told "call site at src/billing.ts:6, symbol stripe.charges.create" edits with the
same confidence whether that binding is certain or inferred, because nothing in front of it
distinguishes the two.

This is the owner's constraint applied to the prompt rather than to the store: we do not reference
information we cannot check, and a fact whose provenance is unstated cannot be checked by whoever
reads the patch afterwards.
"""

from __future__ import annotations

import pytest

from sync.remediate.agent_patch import build_patch_prompt
from tests.test_agent_patch import CHANGE, FINDING, SITE


def _prompt(rung: str) -> str:
    # Pydantic, not a dataclass: `model_copy` is the equivalent.
    return build_patch_prompt(FINDING.model_copy(update={"binding_rung": rung}), CHANGE, SITE)


@pytest.mark.parametrize("rung", ["static", "resolved", "observed"])
def test_the_prompt_states_how_the_call_site_was_attributed(rung):
    assert rung in _prompt(rung)


def test_a_read_binding_and_an_inferred_one_do_not_read_alike():
    """The whole point. If both render identically the rung is in the prompt as decoration."""
    assert _prompt("static") != _prompt("resolved")


def test_each_rung_is_glossed_rather_than_named_alone():
    """`resolved` is Sync's word, not English. An agent that has to guess what it means is being
    handed a token rather than a fact about how much to trust the line above it."""
    assert "source" in _prompt("static").lower()
    assert "traffic" in _prompt("observed").lower() or "runtime" in _prompt("observed").lower()


def test_an_unattributed_finding_says_so_rather_than_claiming_a_rung():
    """`unattributed` is a fact about history -- a row written before attribution existed. It
    must not render as though a binder produced it, and it must not vanish: an absent provenance
    line reads as a certain one."""
    rendered = _prompt("unattributed")

    assert "unattributed" in rendered
    assert "static" not in rendered.split("Call site")[1][:400]


def test_the_evidence_line_sits_with_the_call_site_it_qualifies():
    """A provenance line the reader has to hunt for qualifies nothing. It belongs in the block
    whose facts it is about."""
    rendered = _prompt("resolved")
    block = rendered.split("Call site")[1]

    assert "resolved" in block[:400]


def test_the_evidence_line_is_not_inside_the_untrusted_fence():
    """Everything inside the fence is the repository's own text, which `HARDENING` tells the
    agent not to read as instruction. This line is Sync speaking *about* that text -- fencing it
    would tell the agent to distrust our own assessment of how far to trust the lines above."""
    rendered = _prompt("resolved")
    fenced = rendered.split("<untrusted-repository-text>")[1].split("</untrusted-repository-text>")[0]

    assert "How this was established" not in fenced
    assert "How this was established" in rendered

