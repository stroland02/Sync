import os
import subprocess
import threading
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from sync.core import CallSite, Finding, Remediator, RepoRef, VendorChange
from sync.remediate import agent_patch
from sync.remediate.agent_patch import AgentRemediator, build_patch_prompt
from sync.runner import ALLOWED_TOOLS, DISALLOWED_TOOLS, ClaudeSdkRunner, StaticRunner, claude_sdk

SITE = CallSite(
    repo_id="r1", path="src/billing.ts", line=6, col=8, vendor_id="stripe",
    operation_id="PostCharges", symbol="stripe.charges.create",
    args_keys=["amount", "currency"], response_fields_read=["id", "status"],
    sdk_version="18.0.0", content_hash="h1",
)
CHANGE = VendorChange(
    # Shaped like a real oasdiff record, not a convenient one: no `field` key
    # (real records never carry one), `path_ptr` is the URL path oasdiff
    # reports (not a JSON pointer), and the changed property is named only in
    # the backticked token inside `text`.
    vendor_id="stripe", from_version="v2300", to_version="v2345",
    kind="response-property-removed", operation_id="PostCharges",
    path_ptr="/v1/charges",
    severity="breaking", source="oasdiff",
    raw={
        "id": "response-property-removed",
        "text": "removed the optional property `payment_method_details/card/checks/cvc_check` from the response",
    },
)
RESPONSE_FIELD_CHANGE = CHANGE.model_copy(
    update={"raw": {"id": "response-property-removed",
                    "text": "removed the optional property `status` from the response"}},
)
# The M0 acceptance run's own finding, kept as the regression fixture. The installed SDK was
# stripe 22.4.0-beta.1, whose declarations still carried `receipt_email`, so this change
# typechecks identically before and after the correct fix.
RECEIPT_SITE = CallSite(
    repo_id="r1", path="app/api/setup_accounts/route.ts", line=42, col=6, vendor_id="stripe",
    operation_id="PostPaymentIntents", symbol="stripe.paymentIntents.create",
    args_keys=["amount", "currency", "receipt_email"], response_fields_read=["id"],
    sdk_version="22.4.0-beta.1", content_hash="h2",
)
RECEIPT_CHANGE = VendorChange(
    vendor_id="stripe", from_version="v2300", to_version="v2345",
    kind="request-property-removed", operation_id="PostPaymentIntents",
    path_ptr="/v1/payment_intents",
    severity="breaking", source="oasdiff",
    raw={"id": "request-property-removed",
         "text": "removed the request property `receipt_email`"},
)
FINDING = Finding(
    detector="vendor_change", claim="response-field", call_site_id="cs1",
    vendor_change_id="vc1",
    severity="breaking", rationale="status removed from PostCharges",
)


@pytest.fixture(autouse=True)
def _connected_provider(monkeypatch):
    """A provider, because the runner now refuses without one.

    Owner ruling, 2026-08-19: a deployment that configures nothing must not spend whoever
    installed it, so `ClaudeSdkRunner` raises rather than defaulting. Every test here drives that
    runner, so every test has to connect a model -- which is also the honest shape, since a run
    with no model connected is not a run.
    """
    monkeypatch.setenv("SYNC_MODEL", "claude-opus-5")
    monkeypatch.setenv("SYNC_MODEL_API_KEY", "test-key-not-a-real-credential")

def _line(prompt: str, prefix: str) -> str:
    """The prompt line carrying a labelled fact, so a test can assert on that fact
    rather than on the whole prompt happening to contain a substring somewhere.
    """
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line
    raise AssertionError(f"no line starting with {prefix!r} in:\n{prompt}")


def _rule(prompt: str, needle: str) -> str:
    """The one scope rule mentioning `needle`, lowercased.

    A rule runs across several lines, so a test that wants to know what a
    particular instruction says has to read the whole bullet: asserting against
    the prompt as a whole would pass on the word appearing under some other rule.
    """
    rules = prompt[prompt.index("Rules:"):].split("\n- ")[1:]
    matched = [rule for rule in rules if needle in rule]
    if len(matched) != 1:
        raise AssertionError(f"expected exactly one rule mentioning {needle!r}, found {len(matched)}")
    return matched[0].lower()
SAVED_FINDING = FINDING.model_copy(update={"id": "f-42"})
REPO = RepoRef(
    repo_id="acme-billing", url="https://example.invalid/r",
    local_path="/tmp/r", head_sha="0" * 40,
)


def test_remediator_satisfies_the_protocol():
    assert isinstance(AgentRemediator(), Remediator)


def test_it_handles_a_breaking_finding():
    assert AgentRemediator().can_handle(FINDING, CHANGE) is True


def test_default_construction_stays_claude_sdk_runner_when_the_sandbox_flag_is_unset(monkeypatch):
    """B97 Decision 1's env-gated selection changes nothing for a caller that never opts in --
    every deployment today, until the sandbox's own credential question is answered."""
    from sync.runner.docker_sdk import SANDBOX_ENV

    monkeypatch.delenv(SANDBOX_ENV, raising=False)
    assert isinstance(AgentRemediator()._runner, ClaudeSdkRunner)


def test_sandbox_flag_without_a_credential_refuses_construction_outright(monkeypatch):
    """Opting in without answering the credential question is a construction-time error, not a
    silent fall-through to the unsandboxed runner -- an operator who set the flag believing it
    took effect must not get `ClaudeSdkRunner` instead with no signal that it happened."""
    from sync.runner.docker_sdk import SANDBOX_ENV, _CREDENTIAL_ENV

    monkeypatch.setenv(SANDBOX_ENV, "1")
    monkeypatch.delenv(_CREDENTIAL_ENV, raising=False)
    with pytest.raises(RuntimeError, match=_CREDENTIAL_ENV):
        AgentRemediator()


def test_sandbox_flag_with_a_credential_selects_docker_sdk_runner(monkeypatch):
    from sync.runner.docker_sdk import SANDBOX_ENV, _CREDENTIAL_ENV, _IMAGE_ENV, DockerSdkRunner

    monkeypatch.setenv(SANDBOX_ENV, "1")
    monkeypatch.setenv(_CREDENTIAL_ENV, "test-credential")
    # Names the image explicitly so this test never calls `ensure_image_built` -- a cold miss
    # there runs a real `docker build`, which does not belong in this file's gate.
    monkeypatch.setenv(_IMAGE_ENV, "sync-patch-sandbox:test")

    runner = AgentRemediator()._runner

    assert isinstance(runner, DockerSdkRunner)
    assert runner._credential == "test-credential"
    assert runner._image == "sync-patch-sandbox:test"


def test_the_prompt_names_the_exact_file_and_line():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    assert "src/billing.ts" in prompt
    assert "line 6" in prompt


def test_the_prompt_states_what_changed_and_which_field():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    assert "response-property-removed" in prompt
    assert "status" in prompt
    assert "stripe.charges.create" in prompt


def test_the_prompt_constrains_scope_to_the_affected_call():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    lowered = prompt.lower()
    assert "do not" in lowered
    assert "refactor" in lowered


def test_the_affected_field_comes_from_the_backticked_text_not_the_url_path():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE)
    assert "Affected field: cvc_check" in prompt
    assert "Affected field: charges" not in prompt


def test_the_prompt_says_so_plainly_when_the_field_cannot_be_determined():
    change = CHANGE.model_copy(update={"raw": {"id": "response-property-removed"}})
    prompt = build_patch_prompt(FINDING, change, SITE)
    assert "Affected field: could not be determined from the vendor change" in prompt


def test_previous_diagnostics_are_included_on_a_retry():
    prompt = build_patch_prompt(FINDING, CHANGE, SITE, diagnostics="src/billing.ts(6,8): error TS2339")
    assert "TS2339" in prompt


def test_the_prompt_omits_a_diagnostics_section_on_the_first_attempt():
    assert "previous attempt" not in build_patch_prompt(FINDING, CHANGE, SITE).lower()


def test_the_prompt_does_not_tell_the_agent_to_edit_until_the_typechecker_is_clean():
    """This instruction is what killed the M0 acceptance run. Stripe removed
    `receipt_email` from the specification; the installed SDK's declarations still
    carried the property, so the code typechecked identically before and after the
    correct fix. Told to keep editing until `tsc` was clean, the agent found the tree
    already as clean as it could get and produced an empty diff on all three attempts.
    """
    prompt = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE)
    assert "until it is clean" not in prompt.lower()


def test_the_prompt_names_the_edit_the_call_site_requires():
    """The prompt already carries the field, the call site and the arguments passed.
    Naming the edit is what turns those facts into a stopping condition the agent can
    reach without a typechecker.
    """
    line = _line(build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE), "Required edit:")
    assert "receipt_email" in line
    assert "argument" in line


def test_the_completion_criterion_is_having_made_the_edit():
    prompt = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE)
    assert _line(prompt, "Done when:")


def test_the_prompt_still_tells_the_agent_to_run_the_typechecker():
    """The gate keeps its real role -- catching a patch that breaks compilation --
    so the fix must not be to delete the instruction. Deleting it would satisfy
    every other assertion here.
    """
    assert "npx tsc --noEmit" in build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE)


def test_the_prompt_says_a_clean_typecheck_does_not_mean_the_edit_was_unnecessary():
    """A whole family of vendor changes -- anything request-side, anything the SDK's
    generated types lag -- is invisible to the typechecker until the vendor ships a
    regenerated SDK, which is when the customer no longer needs us.
    """
    lowered = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE).lower()
    assert "older version" in lowered
    assert "was needed" in lowered or "was necessary" in lowered


def test_a_response_side_change_names_the_response_field_rather_than_an_argument():
    line = _line(build_patch_prompt(FINDING, RESPONSE_FIELD_CHANGE, SITE), "Required edit:")
    assert "status" in line
    assert "response" in line
    assert "argument" not in line


def test_a_field_the_index_never_recorded_is_admitted_rather_than_guessed():
    """`cvc_check` sits four segments deep in the response schema and the indexer
    records neither it nor its parents. Claiming it is an argument or a response
    field the call site reads would send the agent after an expression that is not
    there; saying the index does not place it is the honest instruction.
    """
    line = _line(build_patch_prompt(FINDING, CHANGE, SITE), "Required edit:")
    assert "cvc_check" in line
    assert "did not record" in line
    assert "is passed as an argument" not in line
    assert "is read from" not in line


def test_the_scope_rules_that_stop_the_agent_wandering_survive():
    """A patch that touches more than the change requires is how this product loses
    trust. These four constraints are load-bearing and outlast any rewording of the
    completion criterion.
    """
    lowered = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE).lower()
    assert "do not refactor surrounding code" in lowered
    assert "helpers that were not there before" in lowered
    assert "do not reformat lines" in lowered
    assert "rather than inventing a placeholder" in lowered


def test_the_prompt_says_subagent_dispatch_is_unavailable_and_names_the_search_tools():
    """B7's own scratch run: the model called the `Agent` tool three times against a change
    whose field was seven levels deep in the response and named nothing more precise than
    `data` -- `Agent` is not in `ALLOWED_TOOLS`, tool_gate refused it every time, and rather
    than falling back to Grep/Glob/Read (which are allowed and could have located the field),
    the model gave up. `_SCOPE_RULES` already named Read/Grep/Glob as how the agent inspects
    the repository, but never said plainly that a subagent is not an option -- an omission a
    model trained to reach for delegation on an ambiguous search will not read as a limit.
    """
    lowered = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE).lower()
    assert "no subagent" in lowered or "sub-agent" in lowered or "cannot dispatch" in lowered
    assert "grep" in lowered and "glob" in lowered


def test_the_prompt_tells_the_agent_how_to_make_a_new_file_part_of_the_patch():
    """Some fixes need a file that is not there yet -- an extracted helper, a type
    declaration, a shim. Nothing in the pipeline can tell such a file apart from
    the build output the agent's own tool calls leave behind, so the agent is the
    only party that can say which it is, and staging is how it says so. An agent
    that is never told this creates the file, leaves it untracked, and the gate
    typechecks a tree with an unresolved import in it.
    """
    lowered = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE).lower()
    assert "git add" in lowered
    assert "unstaged" in lowered


def test_the_prompt_does_not_let_the_agent_stage_everything():
    """The instruction above is only safe while staging stays a per-file
    assertion. `git add -A` in the clone would sweep in whatever the agent's
    tool calls left there -- a build directory, a log, a stray dependency
    install -- and `push_branch` would commit all of it, which is worse than
    the abandon this change exists to remove.
    """
    lowered = build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE).lower()
    assert "git add -a" in lowered
    assert "git add ." in lowered


def test_the_typecheck_instruction_names_the_tree_the_verification_gate_measures():
    """The agent is told to run its own `npx tsc --noEmit`. Left unqualified that
    command measures the working tree, while the gate measures the tree the push
    would carry -- so an agent that created a file and did not stage it gets a
    clean run from its own command and a failure from the gate, over the same
    edit. The instruction has to name the staging that makes the two agree.
    """
    assert "stag" in _rule(build_patch_prompt(FINDING, RECEIPT_CHANGE, RECEIPT_SITE), "npx tsc --noEmit")


def test_the_diagnostics_section_stays_last():
    """Everything ahead of the diagnostics block is byte-identical across retries,
    which is what makes it a cacheable prefix. Anything appended after diagnostics is
    invalidated on every round -- see the prompt-cache boundary in
    docs/superpowers/specs/2026-07-25-sync-latency-architecture.md.
    """
    prompt = build_patch_prompt(
        FINDING, RECEIPT_CHANGE, RECEIPT_SITE, diagnostics="src/x.ts(1,1): error TS2339",
    )
    diagnostics_at = prompt.index("TS2339")
    for prefix in ("Required edit:", "Done when:", "Call site:", "Affected field:"):
        assert prompt.index(_line(prompt, prefix)) < diagnostics_at
    assert "npx tsc --noEmit" in prompt[:diagnostics_at]
    assert prompt.index("A previous attempt failed") < diagnostics_at
    stable = ("Vendor:", "Affected field:", "Call site:", "Required edit:", "Done when:", "Rules:")
    assert not [
        line for line in prompt[diagnostics_at:].splitlines() if line.startswith(stable)
    ]


def test_the_retry_heading_does_not_name_a_stage_the_caller_never_reported():
    """`diagnostics` is a free-form feedback channel: the graph feeds a CI
    rejection and a failed agent run through it as well as tsc output. A
    heading that announces every one of them as a typechecking failure
    misdescribes the input the agent is being asked to act on.
    """
    prompt = build_patch_prompt(
        FINDING, CHANGE, SITE, diagnostics="the repository's own CI rejected this diff",
    )
    assert "previous attempt" in prompt.lower()
    assert "failed typechecking" not in prompt.lower()


def test_corpus_lessons_reach_the_prompt_ahead_of_the_scope_rules():
    """What past attempts at this change kind learned, in the prompt when the corpus holds any.

    The lessons block is Sync's own aggregate over closed vocabularies -- tiers and reason
    codes, never free text -- which is why it travels unfenced where every vendor sentence
    is fenced. The scope rules keep the last position.
    """
    prompt = build_patch_prompt(
        FINDING, CHANGE, SITE,
        corpus_lessons="3 of 4 past attempts at response-property-removed abandoned at tier 0.",
    )
    assert "3 of 4 past attempts" in prompt
    assert prompt.index("3 of 4 past attempts") < prompt.index("Do not")


def test_no_lessons_appends_nothing():
    # Byte-identical without lessons, the same guarantee repo_context makes: a corpus with
    # nothing to say must not move the cacheable prefix or add an empty heading.
    assert build_patch_prompt(FINDING, CHANGE, SITE) == build_patch_prompt(
        FINDING, CHANGE, SITE, corpus_lessons="",
    )


def test_the_agent_asks_for_lessons_about_the_change_it_holds(tmp_path):
    """`lessons_for` is called with the change, so the lookup can narrow to its kind."""
    prompts: list[str] = []

    class _CapturingRunner:
        def run(self, prompt, repo_path, identity):
            prompts.append(prompt)

    remediator = AgentRemediator(
        runner=_CapturingRunner(),
        lessons_for=lambda change: f"lessons about {change.kind}",
    )
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    identity = ["-c", "user.name=t", "-c", "user.email=t@invalid"]
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", *identity, "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", *identity, "commit", "-q", "-m", "seed", "--no-gpg-sign"],
        cwd=tmp_path, check=True,
    )
    repo = RepoRef(repo_id="r1", url="u", local_path=str(tmp_path), head_sha="0" * 40)
    remediator.propose(FINDING, CHANGE, SITE, repo)

    assert prompts and f"lessons about {CHANGE.kind}" in prompts[0]


def _ok_result(**overrides) -> ResultMessage:
    fields = dict(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=1, session_id="s1"
    )
    fields.update(overrides)
    return ResultMessage(**fields)


def test_run_agent_configures_the_repo_cwd_and_the_pinned_model(monkeypatch, tmp_path):
    captured = {}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["options"] = options
        yield _ok_result()

    monkeypatch.setattr(claude_sdk, "query", fake_query)

    ClaudeSdkRunner(agent_patch.patch_hooks).run("do the patch", tmp_path, "finding=f-42 repo=acme-billing")

    options = captured["options"]
    assert captured["prompt"] == "do the patch"
    assert options.cwd == tmp_path
    # There is no default model any more: a deployment that configures nothing must not
    # spend whoever installed it (owner ruling, 2026-08-19), so the runner drives whatever the
    # user connected and this asserts the wiring rather than a constant.
    assert options.model == "claude-opus-5"
    assert options.thinking == {"type": "adaptive"}
    assert options.effort == "xhigh"
    assert options.allowed_tools == ALLOWED_TOOLS
    assert options.disallowed_tools == DISALLOWED_TOOLS


def test_the_tools_the_gate_would_refuse_are_denied_before_the_model_sees_them():
    """`Skill` and `Task` are refused by the tool gate, and an unlisted tool is not a blocked
    tool -- the model still sees it, reaches for it, and burns the attempt on a refusal.
    Measured live on 2026-08-20: two remediation runs on demo-v1 ended as "the remediator
    produced no change" because the agent asked for `Skill` twice and gave up. A denial has
    to be stated, so the pair the gate refuses and the SDK advertises is denied here too.
    """
    assert "Skill" in DISALLOWED_TOOLS
    assert "Task" in DISALLOWED_TOOLS
    # The pair that was always denied stays denied.
    assert "WebSearch" in DISALLOWED_TOOLS
    assert "WebFetch" in DISALLOWED_TOOLS


def test_the_run_loads_no_settings_from_the_filesystem(monkeypatch, tmp_path):
    """`cwd` is a clone of a customer's repository, and `.claude/settings.json` is a file that
    repository may ship.

    `ClaudeAgentOptions.setting_sources` defaults to `None`, which the SDK documents as "all
    sources are loaded". A `SessionStart` hook in the clone's own settings is therefore a shell
    command Sync runs -- before the first tool call, so `sync.remediate.tool_gate` never sees
    it, and inside a process that holds every credential the control plane has, since
    `options.env` merges onto `os.environ` rather than replacing it (B97).

    Measured 2026-08-16 against the real SDK: a `.claude/settings.json` written into the
    working directory executed `echo` and the marker came back on a `hook_response` message.
    With `setting_sources=[]` the same experiment reported it did not fire.

    `[]` and not `["user"]`: the operator's own global settings are no more part of a patch
    run than the customer's are. The same experiment showed this host's SessionStart hooks
    firing inside the patch agent and its `init` tool roster carrying the operator's whole
    installed set rather than the six `ALLOWED_TOOLS` names.

    Sync's own hooks are unaffected -- they are passed programmatically through `hooks=`,
    which is not a filesystem source.
    """
    captured = {}

    async def fake_query(*, prompt, options):
        captured["options"] = options
        yield _ok_result()

    monkeypatch.setattr(claude_sdk, "query", fake_query)

    ClaudeSdkRunner(agent_patch.patch_hooks).run("do the patch", tmp_path, "finding=f-42 repo=acme-billing")

    assert captured["options"].setting_sources == []
    # The gate still reaches the run, which is the half a bare isolation flag could break.
    assert set(captured["options"].hooks) == {"PreToolUse", "PostToolUse"}


def test_assistant_prose_reaches_on_note_in_order(monkeypatch, tmp_path):
    """The narration half of the live feed: what the agent said between tool calls, handed to
    the caller's recorder as it streams. Empty prose is skipped -- a message that is only tool
    blocks says nothing worth a row -- and long prose is cut at 500 characters at this seam so
    every recorder gets the bounded form.
    """
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def fake_query(*, prompt, options):
        yield AssistantMessage(content=[TextBlock(text="Reading the call site first.")], model="m")
        yield AssistantMessage(content=[], model="m")
        yield AssistantMessage(content=[TextBlock(text="   ")], model="m")
        yield AssistantMessage(content=[TextBlock(text="y" * 900)], model="m")
        yield _ok_result()

    monkeypatch.setattr(claude_sdk, "query", fake_query)
    notes: list[str] = []

    ClaudeSdkRunner(agent_patch.patch_hooks).run(
        "do the patch", tmp_path, "finding=f-42 repo=acme-billing", on_note=notes.append,
    )

    assert notes[0] == "Reading the call site first."
    assert len(notes) == 2
    assert len(notes[1]) == 500


def test_no_note_recorder_leaves_the_run_exactly_as_before(monkeypatch, tmp_path):
    """`on_note=None` is the default, and the three-argument call every existing caller and
    fake makes must keep working unchanged."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def fake_query(*, prompt, options):
        yield AssistantMessage(content=[TextBlock(text="narration nobody asked to keep")], model="m")
        yield _ok_result()

    monkeypatch.setattr(claude_sdk, "query", fake_query)

    ClaudeSdkRunner(agent_patch.patch_hooks).run(
        "do the patch", tmp_path, "finding=f-42 repo=acme-billing",
    )


def test_run_agent_raises_when_the_sdk_reports_a_failed_run(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns", errors=["hit max turns"])

    monkeypatch.setattr(claude_sdk, "query", fake_query)

    with pytest.raises(RuntimeError, match="hit max turns"):
        ClaudeSdkRunner(agent_patch.patch_hooks).run("do the patch", tmp_path, "finding=f-42 repo=acme-billing")


def test_run_agent_raises_when_no_result_message_arrives(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        return
        yield  # pragma: no cover - unreachable; makes this an async generator

    monkeypatch.setattr(claude_sdk, "query", fake_query)

    with pytest.raises(RuntimeError):
        ClaudeSdkRunner(agent_patch.patch_hooks).run("do the patch", tmp_path, "finding=f-42 repo=acme-billing")


def _failing_query(**_):
    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns", errors=["hit max turns"])

    return fake_query


def test_a_failed_agent_run_names_the_finding_and_the_repository(monkeypatch, tmp_path):
    """An operator aggregating failures across findings has the message and
    nothing else -- a stack trace is not in the aggregate, and every finding in
    a `--limit 0` run raises through the same two lines.
    """
    monkeypatch.setattr(claude_sdk, "query", _failing_query())
    repo = REPO.model_copy(update={"local_path": str(tmp_path)})

    with pytest.raises(RuntimeError) as raised:
        AgentRemediator().propose(SAVED_FINDING, CHANGE, SITE, repo)
    assert "f-42" in str(raised.value)
    assert "acme-billing" in str(raised.value)


def test_a_run_with_no_result_message_names_the_finding_and_the_repository(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        return
        yield  # pragma: no cover - unreachable; makes this an async generator

    monkeypatch.setattr(claude_sdk, "query", fake_query)
    repo = REPO.model_copy(update={"local_path": str(tmp_path)})

    with pytest.raises(RuntimeError) as raised:
        AgentRemediator().propose(SAVED_FINDING, CHANGE, SITE, repo)
    assert "f-42" in str(raised.value)
    assert "acme-billing" in str(raised.value)


def test_a_finding_with_no_id_yet_does_not_report_its_identity_as_none(monkeypatch, tmp_path):
    """`Finding.id` is None until the store assigns one. "finding=None" in an
    aggregated failure list reads as a bug in Sync rather than as a finding
    that was never persisted.
    """
    monkeypatch.setattr(claude_sdk, "query", _failing_query())
    repo = REPO.model_copy(update={"local_path": str(tmp_path)})

    with pytest.raises(RuntimeError) as raised:
        AgentRemediator().propose(FINDING, CHANGE, SITE, repo)
    assert "None" not in str(raised.value)


def _git(*args: str, cwd: Path) -> str:
    """Real git, failing loudly. A stub agent whose staging quietly did not happen
    would leave the tests below asserting the absence of something that was never
    there.
    """
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()


@pytest.fixture
def clone(tmp_path, monkeypatch):
    """A repository shaped like the clone the patch agent is handed: one tracked
    source file, committed, and the host's git identity suppressed so nothing
    here depends on the developer machine's config.

    The `.gitignore` is load-bearing rather than decoration. It is what a real
    project uses to declare its build output and its logs disposable, and it is
    the boundary `--exclude-standard` reads to tell a byproduct from a file the
    patch might need. A fixture without one describes a repository that has
    declared nothing, where every stray path the agent's `Bash` calls leave is
    genuinely ambiguous.
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)

    path = tmp_path / "clone"
    (path / "src").mkdir(parents=True)
    _git("init", cwd=path)
    (path / "src" / "billing.ts").write_text("export const charge = () => {};\n", encoding="utf-8")
    (path / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
    _git("add", ".gitignore", cwd=path)
    _git("add", "src/billing.ts", cwd=path)
    _git("-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-m", "seed", cwd=path)
    return path


def _propose_after(clone: Path, monkeypatch, work) -> object:
    runner = StaticRunner(edit=work)
    return AgentRemediator(runner=runner).propose(
        SAVED_FINDING, CHANGE, SITE, REPO.model_copy(update={"local_path": str(clone)}),
    )


def test_the_patch_carries_a_new_file_the_agent_staged(clone, monkeypatch):
    """The case this whole change exists for: the correct fix needs a module that
    is not there yet, and the agent creates it and stages it to say the patch
    depends on it. A patch read from `git diff` alone -- the working tree against
    the index -- cannot see a staged addition at all, so the new module is absent
    from the diff the corpus records and from the diff a CI retry is shown.
    """
    def work(path: Path) -> None:
        (path / "src" / "money.ts").write_text("export const toCents = (n: number) => n * 100;\n", encoding="utf-8")
        _git("add", "src/money.ts", cwd=path)
        (path / "src" / "billing.ts").write_text(
            "import { toCents } from './money';\nexport const charge = () => toCents(1);\n",
            encoding="utf-8",
        )

    patch = _propose_after(clone, monkeypatch, work)

    assert "src/money.ts" in patch.diff
    assert "toCents" in patch.diff
    # The tracked edit has to survive the widening: a diff that reported only the
    # staged addition would satisfy the assertions above and describe half a patch.
    assert "src/billing.ts" in patch.diff


def test_the_remediator_threads_a_finding_scoped_recorder_to_its_runner(clone, monkeypatch):
    """`activity_for` follows `lessons_for` across the seam: the caller hands a per-finding
    factory, the remediator resolves it against the finding it holds, and the runner receives
    the recorder as `on_event` plus a note adapter that files prose under kind `"note"`.
    """
    captured: dict = {}

    class RecordingRunner:
        def run(self, prompt, repo_path, identity, *, on_event=None, on_note=None):
            captured["on_event"] = on_event
            captured["on_note"] = on_note

    events: list[tuple] = []

    def activity_for(finding_id):
        assert finding_id == "f-42"
        return lambda kind, tool, summary: events.append((kind, tool, summary))

    AgentRemediator(runner=RecordingRunner(), activity_for=activity_for).propose(
        SAVED_FINDING, CHANGE, SITE, REPO.model_copy(update={"local_path": str(clone)}),
    )

    captured["on_event"]("tool", "Read", "input=...")
    captured["on_note"]("thinking aloud")
    assert events == [("tool", "Read", "input=..."), ("note", None, "thinking aloud")]


def test_without_activity_for_the_runner_is_called_the_way_it_always_was(clone, monkeypatch):
    """The byte-identical guarantee: a runner with the historical three-argument signature --
    the shape every existing fake and `StaticRunner` still have -- keeps working when nobody
    records, so `None` everywhere costs nothing."""

    class LegacyRunner:
        def run(self, prompt, repo_path, identity):
            pass

    patch = AgentRemediator(runner=LegacyRunner()).propose(
        SAVED_FINDING, CHANGE, SITE, REPO.model_copy(update={"local_path": str(clone)}),
    )

    assert patch.diff == ""


def test_a_patch_that_is_only_a_new_file_is_not_read_as_a_remediator_that_changed_nothing(clone, monkeypatch):
    """`route_after_patch` sends an empty diff back for another attempt and then
    abandons, on the reasoning that a run which failed and a run which changed
    nothing leave the same empty diff. A patch whose entire content is a staged
    new file leaves that same empty diff under `git diff`, and is neither.
    """
    def work(path: Path) -> None:
        (path / "src" / "money.ts").write_text("export const toCents = (n: number) => n * 100;\n", encoding="utf-8")
        _git("add", "src/money.ts", cwd=path)

    patch = _propose_after(clone, monkeypatch, work)

    assert patch.diff.strip()
    assert "src/money.ts" in patch.diff


def test_the_patch_omits_a_file_the_agent_left_unstaged(clone, monkeypatch):
    """The guard the widening must not drop, and the false-positive direction of
    the staging check. The agent holds `Bash` and its tool calls leave things in
    the clone that no part of the patch describes -- a build directory, a log, a
    stray dependency install. Those stay out of the patch for exactly the reason a
    staged file is in it: staging is the assertion, and the agent never made one
    about these.

    This repository's `.gitignore` covers both, so neither is a missed `git add`,
    and returning at all is the assertion that matters: a staging check that read
    every untracked path would refuse a correct patch here, and a gate that fires
    on a compiler's temp file is one somebody switches off.
    """
    def work(path: Path) -> None:
        (path / "src" / "billing.ts").write_text("export const charge = () => 1;\n", encoding="utf-8")
        (path / "build").mkdir()
        (path / "build" / "bundle.js").write_text("// generated\n", encoding="utf-8")
        (path / "npm-debug.log").write_text("noise\n", encoding="utf-8")

    patch = _propose_after(clone, monkeypatch, work)

    assert "src/billing.ts" in patch.diff
    assert "bundle.js" not in patch.diff
    assert "npm-debug.log" not in patch.diff


def test_untracked_output_the_repository_does_not_ignore_is_refused_rather_than_guessed_at(
    clone, monkeypatch,
):
    """The cost of the boundary, recorded rather than discovered later. Where a
    repository's ignore rules do not cover what a tool wrote, git has been told
    nothing about the path and neither has Sync, so it is indistinguishable from
    the new module a fix needs and it refuses.

    That refusal is the conservative direction and it is fed back rather than
    fatal, but it is a real cost and the reason it is not paid down with an
    extension allowlist is that no measurement here supports one. `.gitignore` is
    the customer's own declaration; a list of suffixes would be ours, guessed, and
    wrong silently on the first repository that disagreed.
    """
    def work(path: Path) -> None:
        (path / "src" / "billing.ts").write_text("export const charge = () => 1;\n", encoding="utf-8")
        (path / "out.tmp").write_text("// not covered by this repository's ignore rules\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, work)

    assert "out.tmp" in str(raised.value)


def test_an_agent_that_created_files_and_staged_none_is_told_that_rather_than_reported_as_no_change(
    clone, monkeypatch,
):
    """The abandon reason has to name the cause. An agent that writes the new
    module and forgets to stage it leaves an empty diff, which reads as "the
    remediator produced no change" -- a report of the wrong thing entirely, sending
    an operator after a model that did nothing when it did the work and failed to
    assert it. The message goes back to the next attempt as feedback, so it is also
    the only chance the run has to correct itself.
    """
    def work(path: Path) -> None:
        (path / "src" / "money.ts").write_text("export const toCents = (n: number) => n * 100;\n", encoding="utf-8")

    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, work)

    reason = str(raised.value)
    assert "src/money.ts" in reason
    assert "stage" in reason or "staged" in reason
    assert "f-42" in reason


def test_an_agent_that_edits_a_tracked_file_and_leaves_the_new_one_unstaged_is_told_that(
    clone, monkeypatch,
):
    """The mixed case, which an empty-diff guard cannot see. The edit to the tracked
    call site fills the diff, so the run proceeds and the missing module surfaces at
    the gate as `TS2307: Cannot find module` -- a compile error about an import,
    handed to an attempt whose actual mistake was not staging a file. An agent given
    that message edits the import path; an agent given this one stages the file.
    """
    def work(path: Path) -> None:
        (path / "src" / "money.ts").write_text("export const toCents = (n: number) => n * 100;\n", encoding="utf-8")
        (path / "src" / "billing.ts").write_text(
            "import { toCents } from './money';\nexport const charge = () => toCents(1);\n",
            encoding="utf-8",
        )

    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, work)

    reason = str(raised.value)
    assert "src/money.ts" in reason
    assert "git add" in reason
    assert "f-42" in reason


def test_an_agent_that_changed_nothing_at_all_is_still_reported_as_changing_nothing(clone, monkeypatch):
    """The counterweight. A remediator that correctly found nothing to do must
    keep reaching `route_after_patch` with an empty diff rather than raising: the
    empty-diff path records the tier that produced the nothing, and an exception
    would relabel every genuine no-op as a fault.
    """
    patch = _propose_after(clone, monkeypatch, lambda path: None)

    assert patch.diff.strip() == ""
    assert patch.strategy == "agent"


# --- a customer file that is not UTF-8 --------------------------------------------
#
# `git diff` copies file content onto the pipe verbatim, so a source file in a legacy
# encoding makes the child emit bytes that are not UTF-8. Read with `text=True,
# encoding="utf-8"` that decode happens on a reader thread, where the `UnicodeDecodeError`
# is swallowed: the call returns exit 0 with `stdout` set to `None`, and `None` travels on
# as the patch's diff until something concatenates it. Measured against a clone holding one
# cp1252 file, and recorded in
# `docs/superpowers/reports/2026-07-29-a-diff-that-does-not-decode.md`.

# cp1252 for `café` and `montréal`. Written as bytes, never as a committed fixture: anything
# that round-trips a non-UTF-8 file as text repairs it, and the test then passes against a
# valid file. 0xe9 is `é` in cp1252 and an invalid continuation byte in UTF-8.
CP1252_SOURCE = b'export const caf\xe9 = "montr\xe9al";\n'

# The same two words as genuine UTF-8. An accented identifier is not the defect and must not
# become a casualty of the fix.
UTF8_SOURCE = 'export const café = "montréal";\n'.encode("utf-8")


def _rewrite(name: str, content: bytes):
    """A stand-in for the agent editing one tracked file, byte-exactly."""
    def work(path: Path) -> None:
        (path / name).write_bytes(content)

    return work


def test_a_diff_that_is_not_utf_8_refuses_the_patch_and_names_the_file(clone, monkeypatch):
    """The reproduction, as a test. Before the fix this raises nothing here at all: the
    decode fails on `subprocess`'s reader thread, `_git_diff` returns `None`, and
    `Patch(diff=None)` fails pydantic validation or -- had it not -- reaches
    `nodes.py`'s `proposed.diff.strip()` as an `AttributeError` that names no subprocess.

    What the refusal has to carry is the file. The defect's whole cost is that it names
    neither the file nor the call, so an operator sees a `TypeError` about `NoneType`
    somewhere in the graph and has no path back to a customer source file.
    """
    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, _rewrite("src/billing.ts", CP1252_SOURCE))

    reason = str(raised.value)
    assert "src/billing.ts" in reason, f"the refusal must name the file; got {reason!r}"
    assert "git diff HEAD" in reason, f"the refusal must name the call; got {reason!r}"
    assert "f-42" in reason and "acme-billing" in reason


def test_the_refusal_arrives_at_the_caller_and_not_on_a_reader_thread(clone, monkeypatch):
    """The half of the measurement that makes this a defect rather than a preference.

    `threading.excepthook` is installed for the same reason
    `tests/test_subprocess_encoding.py` installs one: it is what proves *where* the failure
    happens. Before the fix the `UnicodeDecodeError` is raised on `Thread-N (_readerthread)`
    where no caller can catch it. After it, nothing is raised on any thread and the failure
    is an exception at the call site.
    """
    raised_on_a_thread: list[BaseException] = []
    original = threading.excepthook
    threading.excepthook = lambda args: raised_on_a_thread.append(args.exc_value)
    try:
        with pytest.raises(RuntimeError):
            _propose_after(clone, monkeypatch, _rewrite("src/billing.ts", CP1252_SOURCE))
    finally:
        threading.excepthook = original

    assert raised_on_a_thread == [], (
        f"the decode still happens where no caller can catch it: {raised_on_a_thread!r}"
    )


def test_an_ordinary_ascii_diff_is_byte_identical_to_what_git_produced(clone, monkeypatch):
    """Without this a fix that mangles every patch passes. Compared against the child's
    own bytes rather than against a substring, because the diff *is* the data.
    """
    edited = "export const charge = () => 1;\n"
    patch = _propose_after(clone, monkeypatch, _rewrite("src/billing.ts", edited.encode("ascii")))

    expected = subprocess.run(
        ["git", "diff", "HEAD"], cwd=clone, capture_output=True, check=True,
    ).stdout
    assert patch.diff.encode("utf-8") == expected
    assert edited in patch.diff


def test_a_diff_carrying_legitimate_non_ascii_utf_8_comes_through_intact(clone, monkeypatch):
    """An accented identifier in a UTF-8 file is not the defect. This is the assertion
    that rules out `errors="replace"`: it would return `caf��` here and the patch
    would apply something the customer did not write.
    """
    patch = _propose_after(clone, monkeypatch, _rewrite("src/billing.ts", UTF8_SOURCE))

    assert "café" in patch.diff
    assert "montréal" in patch.diff
    assert "�" not in patch.diff, "a replacement character means the patch was corrupted"
    expected = subprocess.run(
        ["git", "diff", "HEAD"], cwd=clone, capture_output=True, check=True,
    ).stdout
    assert patch.diff.encode("utf-8") == expected


def test_the_file_named_is_the_one_whose_bytes_do_not_decode(clone, monkeypatch):
    """Naming the first changed file, or the repository, would satisfy the test above while
    sending a reader to a file that is perfectly valid.
    """
    def work(path: Path) -> None:
        (path / "src" / "clean.ts").write_bytes(b"export const clean = 1;\n")
        (path / "src" / "legacy.ts").write_bytes(CP1252_SOURCE)
        _git("add", "src/clean.ts", "src/legacy.ts", cwd=path)

    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, work)

    reason = str(raised.value)
    assert "src/legacy.ts" in reason
    assert "src/clean.ts" not in reason, f"named a file that decodes cleanly: {reason!r}"


# --- `_undecodable_path`, driven directly ------------------------------------------

_DIFF_HEADERS = (
    b"diff --git a/src/one.ts b/src/one.ts\n"
    b"--- a/src/one.ts\n"
    b"+++ b/src/one.ts\n"
    b"@@ -1 +1 @@\n"
    b"-const a = 1;\n"
    b"+const a = 2;\n"
    b"diff --git a/src/two.ts b/src/two.ts\n"
    b"--- a/src/two.ts\n"
    b"+++ b/src/two.ts\n"
    b"@@ -1 +1 @@\n"
    b"-const b = 1;\n"
    b"+const b = \xe9;\n"
)


def test_the_named_path_is_the_last_header_before_the_offending_byte():
    assert agent_patch._undecodable_path(_DIFF_HEADERS, _DIFF_HEADERS.index(b"\xe9")) == "src/two.ts"
    assert agent_patch._undecodable_path(_DIFF_HEADERS, _DIFF_HEADERS.index(b"const a = 2")) == "src/one.ts"


def test_a_plus_plus_plus_line_inside_a_hunk_is_not_read_as_a_header():
    """A customer repository that keeps patch files under version control has these. An
    added line whose content is `++ b/elsewhere.ts` renders in the diff as `+++ b/elsewhere.ts`
    -- git's `+` for an added line, then the content's own two -- and a scan for the last
    `+++ ` line would name a file that is not in this diff at all. Requiring a `--- ` line
    immediately above is what tells a header from content.

    The three characters are load-bearing and the first draft of this test had two, which
    matched nothing and left the guard unexercised: dropping it from `_undecodable_path`
    survived mutation. Hence the assertion below on the fixture itself.
    """
    content = b"++ b/elsewhere.ts"
    diff = (
        b"diff --git a/patches/fix.patch b/patches/fix.patch\n"
        b"--- a/patches/fix.patch\n"
        b"+++ b/patches/fix.patch\n"
        b"@@ -0,0 +1,2 @@\n"
        b"+" + content + b"\n"
        b"+const b = \xe9;\n"
    )
    assert b"\n+++ b/elsewhere.ts\n" in diff, (
        "this fixture does not contain the collision it exists to describe, so it cannot "
        "distinguish a guarded scan from a naive one"
    )
    assert agent_patch._undecodable_path(diff, diff.index(b"\xe9")) == "patches/fix.patch"


def test_a_deleted_file_is_named_from_the_side_that_still_has_a_path():
    """`+++ /dev/null` on a deletion, so the destination header names no file and the
    content whose bytes reached the pipe came off the `---` side.
    """
    diff = (
        b"diff --git a/src/gone.ts b/src/gone.ts\n"
        b"--- a/src/gone.ts\n"
        b"+++ /dev/null\n"
        b"@@ -1 +0,0 @@\n"
        b"-const b = \xe9;\n"
    )
    assert agent_patch._undecodable_path(diff, diff.index(b"\xe9")) == "src/gone.ts"


# --- `_unstaged_additions`: the measurement behind its exemption -------------------


@pytest.mark.parametrize("quotepath", ["true", "false"])
def test_git_cannot_hand_this_call_a_path_that_is_not_utf_8(clone, quotepath):
    """Why `_unstaged_additions` takes a measured exemption where `_git_diff` takes a fix.

    `git diff HEAD` copies content; this call reports paths, and git owns their encoding at
    both settings of `core.quotepath`. With it at its default a non-ASCII path is octal-escaped
    into pure ASCII; with it off the path arrives as the UTF-8 git stores internally, converted
    from NTFS's UTF-16. Neither is a byte sequence that is not UTF-8, which is the claim the
    exemption on the call makes -- and this test is what establishes it rather than asserting it.

    The audit measured `git ls-files -z`, where `core.quotepath` is ignored entirely. This call
    passes no `-z`, so the setting is live and both values had to be checked.
    """
    _git("config", "core.quotepath", quotepath, cwd=clone)
    (clone / "src" / "café.ts").write_bytes(b"export const x = 1;\n")

    listed = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=clone,
        capture_output=True, check=True,
    ).stdout

    assert listed, "git listed nothing, so this measures no path at all"
    listed.decode("utf-8")  # raises UnicodeDecodeError if git ever emits something else
    if quotepath == "true":
        assert listed.isascii(), f"quotepath was expected to escape this to ascii: {listed!r}"
        assert b"caf\\303\\251.ts" in listed
    else:
        assert not listed.isascii()
        assert b"caf\xc3\xa9.ts" in listed


def test_the_unstaged_guard_still_names_a_path_git_reported_with_escapes(clone, monkeypatch):
    """M3-W82's guard decides the same thing over a non-ASCII path as over any other:
    the patch is refused and the path is named. What git hands back at
    `core.quotepath`'s default is the escaped spelling, which is what the message carries.
    """
    _git("config", "core.quotepath", "true", cwd=clone)

    def work(path: Path) -> None:
        (path / "src" / "café.ts").write_bytes(b"export const x = 1;\n")

    with pytest.raises(RuntimeError) as raised:
        _propose_after(clone, monkeypatch, work)

    reason = str(raised.value)
    assert "caf\\303\\251.ts" in reason
    assert "git add" in reason
