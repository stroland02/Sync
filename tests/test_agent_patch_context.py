from sync.remediate.agent_patch import build_patch_prompt

# `tests/test_agent_patch.py` defines its Finding/VendorChange/CallSite builders as
# module-level constants (FINDING, CHANGE, SITE) rather than as functions or fixtures --
# the plan's own guidance covers fixtures moving to conftest.py, but not this shape, so
# reusing the constants directly is the faithful adaptation: still "the existing builders
# rather than inventing new ones."
from tests.test_agent_patch import CHANGE, FINDING, SITE


def test_no_context_is_byte_identical_to_the_prompt_without_the_parameter():
    """The landing property. Every existing assertion on this function must hold unchanged.

    Compared against the call that omits the parameter entirely rather than against a stored
    fixture, so this stays true as the rest of the prompt changes.
    """
    without = build_patch_prompt(FINDING, CHANGE, SITE)
    with_empty = build_patch_prompt(FINDING, CHANGE, SITE, repo_context="")
    assert with_empty == without


def test_context_appears_in_the_prompt():
    prompt = build_patch_prompt(
        FINDING, CHANGE, SITE, repo_context="Package manager is pnpm."
    )
    assert "Package manager is pnpm." in prompt


def test_context_sits_between_the_rationale_and_the_rules():
    """Section order is load-bearing, and this one has a place rather than an end.

    The repository is described before the edit is constrained, so `Rules:` keeps the last and
    strongest position.
    """
    prompt = build_patch_prompt(
        FINDING, CHANGE, SITE, repo_context="Package manager is pnpm."
    )
    assert prompt.index("Why this matters") < prompt.index("Package manager is pnpm.")
    assert prompt.index("Package manager is pnpm.") < prompt.index("Rules:")


def test_context_sits_ahead_of_the_diagnostics_block():
    """Everything stable stays ahead of the only part that changes between retries.

    `2026-07-25-sync-latency-architecture.md` binds this: anything appended after diagnostics
    invalidates the cached prefix every round.
    """
    prompt = build_patch_prompt(
        FINDING,
        CHANGE,
        SITE,
        diagnostics="TS2554: Expected 1 arguments, but got 2.",
        repo_context="Package manager is pnpm.",
    )
    assert prompt.index("Package manager is pnpm.") < prompt.index("A previous attempt failed")


def test_whitespace_only_context_renders_no_section():
    without = build_patch_prompt(FINDING, CHANGE, SITE)
    assert build_patch_prompt(FINDING, CHANGE, SITE, repo_context="  \n ") == without
