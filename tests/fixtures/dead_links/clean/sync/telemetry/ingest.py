"""A structural interface outside the published package.

Nothing names `Store` or `record_call` at a call site, because a Protocol is satisfied by
shape. Reporting either would be reporting the type system working.
"""

from typing import Protocol


class Store(Protocol):
    def record_call(self, call: dict) -> None: ...
