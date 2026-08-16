"""`sync.remediate.sandbox` unit-level behaviour that does not need Docker.

The container-lifecycle primitives (`ephemeral_container`, `disconnect_network`,
`probe_connect`) are proven against a real Docker Desktop in
`tests/test_patch_sandbox.py`, marked `docker`. What belongs here is the part
with no Docker dependency: `build_container_env`'s allowlist-from-empty
construction, which is the one piece of this module a unit test can pin without
a container running.
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
