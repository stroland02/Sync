"""A finding gets a name two people can say to each other.

M15 Task 6. A finding is a 32-character hex id, and the plan's problem statement is the whole of
it: *two people cannot discuss one*. The claim under test is not that the name is pretty -- it is
that the name is **derived**, so it survives re-derivation, and **discriminated**, so two findings
in one workspace are not called the same thing.

The refusal recorded in the plan matters as much: **no random word pair**. A name drawn from a
word list would not survive `insert_finding` re-hashing, and a name that changes on re-scan is
worse than an id, because a reader who wrote it down now holds a reference to nothing.
"""

import pytest

from sync.core.naming import finding_name


def test_the_name_is_the_same_every_time_it_is_derived():
    """The property the whole feature rests on.

    `insert_finding` re-derives a finding's id from its natural key on every scan, converging on
    the row it already wrote. A name derived from that id inherits the same convergence -- and a
    name that did not would break exactly when somebody had written it down.
    """
    first = finding_name("stripe", "PostCharges", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")
    second = finding_name("stripe", "PostCharges", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")

    assert first == second


def test_two_findings_on_one_operation_are_told_apart():
    """Same vendor, same operation, different finding: the readable half collides by design.

    Two findings against `PostCharges` *should* read alike -- that is what makes the name useful.
    The discriminator is what stops alike from becoming identical, and it comes from the finding's
    own id rather than from a counter, because a counter would depend on insertion order.
    """
    one = finding_name("stripe", "PostCharges", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")
    two = finding_name("stripe", "PostCharges", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d")

    assert one != two


def test_the_name_says_which_integration_and_operation_it_is_about():
    """A discriminator alone would be a second id, which is the problem rather than the fix."""
    name = finding_name("stripe", "PostCharges", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")

    assert name.startswith("stripe-postcharges-")


def test_a_name_is_safe_to_type_paste_and_put_in_a_branch():
    """Lowercase, and nothing outside `[a-z0-9-]`.

    A vendor id can carry a dot and an operation id a slash or a brace, and a name that inherited
    those would break the moment somebody used it where a name is expected -- a branch, a URL, a
    grep. Slugged once here rather than escaped at each of those.
    """
    name = finding_name("acme.cloud", "GET /v1/charges/{id}", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")

    assert name == name.lower()
    assert all(character.isalnum() or character == "-" for character in name)
    assert "--" not in name


def test_a_long_operation_does_not_run_away_with_the_name():
    """A sixty-character name is not memorable, which is the only thing this feature is for.

    Truncating can make two operations share a readable half; that is what the discriminator is
    for, and it is derived from the untruncated identity, so the two names still differ.
    """
    long_op = "PostAccountsSessionsCapabilitiesRequirementsCollection"
    name = finding_name("stripe", long_op, "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")

    assert len(name) <= 40


def test_two_operations_sharing_a_truncated_prefix_still_get_different_names():
    prefix = "PostAccountsSessionsCapabilities"
    one = finding_name("stripe", prefix + "Requirements", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")
    two = finding_name("stripe", prefix + "Collection", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d")

    assert one != two


def test_a_workspace_of_findings_has_no_two_names_alike():
    """The plan's verification, at a size a real workspace reaches.

    Two thousand findings spread over a realistic spread of vendors and operations. This is the
    guard that would catch a discriminator shortened to save a few characters -- at four hex
    digits the birthday bound puts a collision here at better than even odds, and a collision
    means two different findings a reader cannot tell apart by the name the console shows them.
    """
    vendors = ["stripe", "openai", "twilio", "anthropic", "github"]
    names = {
        finding_name(
            vendors[index % len(vendors)],
            f"Operation{index % 40}",
            f"{index:032x}",
        )
        for index in range(2000)
    }

    assert len(names) == 2000


def test_an_operation_that_slugs_to_nothing_still_names_the_finding():
    """A boundary the graph can genuinely hand over: an operation id of punctuation alone.

    The honest answer is a name that still identifies the finding rather than one with an empty
    middle that reads as a rendering fault.
    """
    name = finding_name("stripe", "///", "9f2c4a1b8e3d5f7a0c2e4b6d8f0a1c3e")

    assert "--" not in name
    assert name.startswith("stripe-")
    assert len(name) > len("stripe-")


@pytest.mark.parametrize("bad_id", ["", "   "])
def test_a_finding_with_no_id_is_refused_rather_than_named_anyway(bad_id):
    """No id means no discriminator, and a name without one is a name that collides silently.

    Refused at the derivation rather than papered over: a caller reaching here without an id has
    a defect upstream, and returning `stripe-postcharges-` would hide it behind something that
    looks like a name.
    """
    with pytest.raises(ValueError):
        finding_name("stripe", "PostCharges", bad_id)
