"""`sync.remediate.sandbox` unit-level behaviour that does not need Docker.

The container-lifecycle primitives (`ephemeral_container`, `disconnect_network`,
`probe_connect`) are proven against a real Docker Desktop in
`tests/test_patch_sandbox.py`, marked `docker`. What belongs here is the part
with no Docker dependency: `build_container_env`'s allowlist-from-empty
construction, and `_parse_probe_output`'s parsing contract -- both pinnable
without a container running.
"""

from __future__ import annotations

from sync.remediate import sandbox


def test_build_container_env_excludes_everything_not_named(monkeypatch):
    """The allowlist starts from nothing. A control-plane credential the parent
    process holds must be absent from the result because nothing named it, not
    because something filtered it out after the fact.
    """
    monkeypatch.setenv("SYNC_GRAPH_DSN", "postgresql://should-not-leak")
    monkeypatch.setenv("SYNC_WEBHOOK_SECRET", "should-not-leak-either")
    monkeypatch.setenv("SYNC_FEED_SIGNING_KEY", "nor-this-one")
    monkeypatch.setenv("PATH", "/usr/bin")

    env = sandbox.build_container_env()

    assert "SYNC_GRAPH_DSN" not in env
    assert "SYNC_WEBHOOK_SECRET" not in env
    assert "SYNC_FEED_SIGNING_KEY" not in env
    assert env["PATH"] == "/usr/bin"


def test_build_container_env_omits_an_unset_allowlisted_variable(monkeypatch):
    """Naming a variable on the allowlist is not a promise it will be there --
    an unset `PYTHONIOENCODING` must not appear as `None` or an empty string,
    either of which would be a different bug reaching the container as a real
    (wrong) value instead of as an absent one.
    """
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)

    env = sandbox.build_container_env()

    assert "PYTHONIOENCODING" not in env


def test_build_container_env_carries_the_auth_credential_the_caller_names(monkeypatch):
    """`auth_env` is the one deliberate hole in the allowlist: the caller states
    by name what the SDK's own CLI needs to authenticate, and only that reaches
    the container. A secret not named here has no route in, the same property
    the platform-plumbing allowlist gives `PATH`.
    """
    monkeypatch.setenv("SYNC_GRAPH_DSN", "should-not-leak")

    env = sandbox.build_container_env(auth_env={"ANTHROPIC_API_KEY": "sk-test-only"})

    assert env["ANTHROPIC_API_KEY"] == "sk-test-only"
    assert "SYNC_GRAPH_DSN" not in env


def test_probe_output_is_reachable_on_the_exact_success_marker():
    result = sandbox._parse_probe_output(returncode=0, stdout="REACHABLE\n", stderr="")

    assert result.reachable is True


def test_probe_output_rejects_unreachable_even_when_returncode_is_zero():
    """Regression guard for the substring bug this parsing was split out to fix:
    `"REACHABLE" in stdout` is true for `_PROBE_SCRIPT`'s failure line too,
    because `"UNREACHABLE"` contains `"REACHABLE"` as a substring. This
    constructs the exact adversarial input that check was blind to -- a zero
    return code paired with the failure line -- to prove the parsing no longer
    trusts the substring on its own. `_PROBE_SCRIPT` itself never produces this
    combination (it always exits non-zero on its failure path), which is
    exactly why the old check went untested by every real probe and still did
    no work.
    """
    result = sandbox._parse_probe_output(returncode=0, stdout="UNREACHABLE: [Errno 111] refused\n", stderr="")

    assert result.reachable is False


def test_probe_output_is_not_reachable_on_nonzero_returncode_with_success_text():
    result = sandbox._parse_probe_output(returncode=1, stdout="REACHABLE\n", stderr="")

    assert result.reachable is False
