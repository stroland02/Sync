import pytest
from claude_agent_sdk import ResultMessage

from sync.core import CallSite, Finding, Remediator, RepoRef, VendorChange
from sync.remediate import agent_patch
from sync.remediate.agent_patch import AgentRemediator, build_patch_prompt

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
FINDING = Finding(
    detector="vendor_change", call_site_id="cs1", vendor_change_id="vc1",
    severity="breaking", rationale="status removed from PostCharges",
)
SAVED_FINDING = FINDING.model_copy(update={"id": "f-42"})
REPO = RepoRef(
    repo_id="acme-billing", url="https://example.invalid/r",
    local_path="/tmp/r", head_sha="0" * 40,
)


def test_remediator_satisfies_the_protocol():
    assert isinstance(AgentRemediator(), Remediator)


def test_it_handles_a_breaking_finding():
    assert AgentRemediator().can_handle(FINDING, CHANGE) is True


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

    monkeypatch.setattr(agent_patch, "query", fake_query)

    AgentRemediator()._run_agent("do the patch", tmp_path, "finding=f-42 repo=acme-billing")

    options = captured["options"]
    assert captured["prompt"] == "do the patch"
    assert options.cwd == tmp_path
    assert options.model == agent_patch.MODEL
    assert options.thinking == {"type": "adaptive"}
    assert options.effort == "xhigh"
    assert options.allowed_tools == agent_patch.ALLOWED_TOOLS
    assert options.disallowed_tools == agent_patch.DISALLOWED_TOOLS


def test_run_agent_raises_when_the_sdk_reports_a_failed_run(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns", errors=["hit max turns"])

    monkeypatch.setattr(agent_patch, "query", fake_query)

    with pytest.raises(RuntimeError, match="hit max turns"):
        AgentRemediator()._run_agent("do the patch", tmp_path, "finding=f-42 repo=acme-billing")


def test_run_agent_raises_when_no_result_message_arrives(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        return
        yield  # pragma: no cover - unreachable; makes this an async generator

    monkeypatch.setattr(agent_patch, "query", fake_query)

    with pytest.raises(RuntimeError):
        AgentRemediator()._run_agent("do the patch", tmp_path, "finding=f-42 repo=acme-billing")


def _failing_query(**_):
    async def fake_query(*, prompt, options):
        yield _ok_result(is_error=True, subtype="error_max_turns", errors=["hit max turns"])

    return fake_query


def test_a_failed_agent_run_names_the_finding_and_the_repository(monkeypatch, tmp_path):
    """An operator aggregating failures across findings has the message and
    nothing else -- a stack trace is not in the aggregate, and every finding in
    a `--limit 0` run raises through the same two lines.
    """
    monkeypatch.setattr(agent_patch, "query", _failing_query())
    repo = REPO.model_copy(update={"local_path": str(tmp_path)})

    with pytest.raises(RuntimeError) as raised:
        AgentRemediator().propose(SAVED_FINDING, CHANGE, SITE, repo)
    assert "f-42" in str(raised.value)
    assert "acme-billing" in str(raised.value)


def test_a_run_with_no_result_message_names_the_finding_and_the_repository(monkeypatch, tmp_path):
    async def fake_query(*, prompt, options):
        return
        yield  # pragma: no cover - unreachable; makes this an async generator

    monkeypatch.setattr(agent_patch, "query", fake_query)
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
    monkeypatch.setattr(agent_patch, "query", _failing_query())
    repo = REPO.model_copy(update={"local_path": str(tmp_path)})

    with pytest.raises(RuntimeError) as raised:
        AgentRemediator().propose(FINDING, CHANGE, SITE, repo)
    assert "None" not in str(raised.value)
