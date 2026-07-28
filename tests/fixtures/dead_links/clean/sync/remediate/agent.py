"""A concrete implementation of a protocol. `propose` is reached through the interface, so
no caller ever names it on this class."""


class AgentRemediator:
    strategy = "agent"

    def propose(self, finding: object) -> str:
        return "diff"
