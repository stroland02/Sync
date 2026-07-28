"""The entry point `pyproject.toml` names, plus the string that reaches the registry."""

from sync.remediate import AgentRemediator

HANDLERS = {"handler_v1": "sync.registry"}


def main() -> int:
    remediator = AgentRemediator()
    return 0 if remediator.propose(None) else 1
