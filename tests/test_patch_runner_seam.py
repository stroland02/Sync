"""The seam between deciding what to patch and driving a model to patch it.

Before this existed, a test that wanted to assert what the pipeline does with a patch had to
replace a library symbol -- `monkeypatch.setattr(agent_patch, "query", ...)` -- which is not a
seam. It asserts against Sync's knowledge of another package's internals, so it keeps passing
when the SDK renames `query`, and it can be handed to no caller outside a test.

`PatchRunner` is the seam. `AgentRemediator` builds the prompt and reads the clone; a runner
drives a model. Two implementations ship: the Claude Agent SDK path, and a static one that
returns a fixed result and so needs no key and no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sync.core.protocols import PatchRunner
from sync.remediate.agent_patch import AgentRemediator, build_patch_prompt, patch_hooks
from sync.runner import ClaudeSdkRunner, StaticRunner
from tests.test_agent_patch import CHANGE, REPO, SAVED_FINDING, SITE


def _repo_at(path: Path):
    return REPO.model_copy(update={"local_path": str(path)})


def test_both_shipped_runners_satisfy_the_protocol():
    assert isinstance(StaticRunner(), PatchRunner)
    assert isinstance(ClaudeSdkRunner(patch_hooks), PatchRunner)


def test_an_sdk_runner_cannot_be_built_without_hooks():
    """The gate is the only thing between an agent holding `Bash` and `curl` in a clone that
    carries `.env` -- the threat model's first-ranked item. An ungated run reports as an
    ordinary success, so nothing downstream would catch a defaulted constructor.
    """
    with pytest.raises(TypeError):
        ClaudeSdkRunner()


def test_the_remediator_drives_the_runner_it_was_given(base_clone):
    runner = StaticRunner()

    AgentRemediator(runner=runner).propose(SAVED_FINDING, CHANGE, SITE, _repo_at(base_clone))

    assert len(runner.calls) == 1
    prompt, repo_path, identity = runner.calls[0]
    assert prompt == build_patch_prompt(SAVED_FINDING, CHANGE, SITE)
    assert repo_path == base_clone
    assert identity == "finding=f-42 repo=acme-billing"


def test_a_static_runner_can_script_what_the_agent_left_in_the_clone(base_clone):
    """The clone is how a runner reports its work -- `propose` reads the diff from git rather
    than from a return value -- so a runner that cannot write to it can only ever produce the
    empty patch, and no test of the staging rules could use one.
    """
    def edit(repo_path: Path) -> None:
        (repo_path / "src" / "a.ts").write_text("export const n: number = 2;\n", encoding="utf-8")

    patch = AgentRemediator(runner=StaticRunner(edit=edit)).propose(
        SAVED_FINDING, CHANGE, SITE, _repo_at(base_clone),
    )

    assert "export const n: number = 2;" in patch.diff
    assert patch.strategy == "agent"


def test_a_runner_that_fails_surfaces_through_propose(base_clone):
    """A runner owns the whole vocabulary of a failed run. `propose` does not inspect the
    reason, so a runner that cannot report one would move the SDK's error handling back
    across the seam.
    """
    runner = StaticRunner(error="agent run failed (error_max_turns) [finding=f-42 repo=acme-billing]")

    with pytest.raises(RuntimeError, match="error_max_turns"):
        AgentRemediator(runner=runner).propose(SAVED_FINDING, CHANGE, SITE, _repo_at(base_clone))


def test_the_default_runner_is_the_sdk_one():
    """A caller that names no runner gets the production path. The seam serves tests and M9's
    outcome vocabulary; it is not a switch somebody has to remember to set.
    """
    assert isinstance(AgentRemediator()._runner, ClaudeSdkRunner)


def test_the_static_runner_reaches_no_model_sdk():
    """The property the seam exists for, asserted rather than assumed. `sync.runner.static`
    importing the SDK would make the whole remediation suite need a key again, and nothing
    downstream would notice -- a fake that quietly works is exactly what this replaces.
    """
    import sync.runner.static as static

    assert "claude_agent_sdk" not in static.__dict__
    source = Path(static.__file__).read_text(encoding="utf-8")
    assert "claude_agent_sdk" not in source
