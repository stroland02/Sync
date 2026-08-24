"""One operation's slice of a specification, small enough to hand an agent.

`build_patch_prompt` names the operation a finding is about and says nothing about its shape, so
the agent is told `PostCharges` changed and left to infer what `PostCharges` looks like. Handing
over the whole document is not the alternative: Anthropic's is 2,015,896 bytes across 144
operations, and the one that matters is a few hundred.

Three properties, and the first is what makes the other two worth having.

**The slice carries the hash it was cut from.** A claim the agent makes from a slice has to be
refutable later, and it is only refutable if a reader can say which document said it. That is the
whole of the owner's constraint on this store: we do not reference information we cannot check.

**References are resolved to a bounded depth, and the rest are named.** An OpenAPI operation is
mostly pointers, so a naive slice hands over `$ref: '#/components/schemas/Charge'` and tells the
agent nothing. The full transitive closure is not the answer either.

The default is one level, and it is measured rather than chosen. Against Stripe's `PostCharges`
in a 7,866,866-byte document:

| depth | slice | roughly | schemas expanded | named |
|---|---|---|---|---|
| 0 | 15,938 bytes | 4k tokens | 0 | 2 |
| 1 | 33,857 bytes | 8k tokens | 2 | 19 |
| 2 | 137,117 bytes | 34k tokens | 21 | 113 |

Depth 1 expands the request and response shapes -- where a breaking change lives -- and still
leaves room for the call site and the diagnostics, which are the two things the agent cannot work
without. Depth 2 displaces them.

A schema past the bound is **named rather than dropped**. The agent has to be able to tell "there
is more here, and it is called `Charge`" from "the vendor declares nothing here", and a silent
truncation is exactly the second reading.

**A reference out of the document is recorded, never followed.** Resolving one is a fetch, and a
slicer that fetches reaches the network from inside a prompt build -- on a path nobody would think
to look at, with a URL the vendor's own document chose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_LOCAL_PREFIX = "#/components/schemas/"

_HTTP_METHODS = ("get", "put", "post", "patch", "delete", "head", "options", "trace")


class SliceTooDeep(Exception):
    """A slice reached more schemas than a prompt can carry, even inside the depth bound.

    Raised rather than truncated. A truncated slice is a specification with holes the agent
    cannot see, and it would read a gap as the vendor declaring nothing there. Refusing leaves
    the prompt as it was before slicing existed: a worse prompt, and an honest one.
    """


@dataclass(frozen=True)
class OperationSlice:
    """What one operation declares, and the schemas it reaches."""

    operation_id: str
    path: str
    http_method: str
    operation: dict[str, Any]
    schemas: dict[str, Any] = field(default_factory=dict)
    not_expanded: tuple[str, ...] = ()
    """Schemas the operation reaches past the depth bound, by name.

    Named so the agent can tell a bounded slice from a vendor that declares nothing there.
    """

    unresolved: tuple[str, ...] = ()
    spec_hash: str | None = None

    def render(self) -> str:
        """The slice as the prompt carries it, hash first."""
        import json

        header = f"operation {self.operation_id} ({self.http_method.upper()} {self.path})"
        if self.spec_hash:
            header += f", from specification {self.spec_hash}"
        lines = [header, json.dumps(self.operation, indent=2, sort_keys=True)]
        if self.schemas:
            lines.append("schemas it references:")
            lines.append(json.dumps(self.schemas, indent=2, sort_keys=True))
        if self.not_expanded:
            lines.append(
                "schemas it reaches beyond this slice's depth, not expanded here: "
                + ", ".join(self.not_expanded)
            )
        if self.unresolved:
            # Named rather than dropped. A reference this build did not follow is a part of the
            # operation the agent has not been shown, and it must not read as one that is absent.
            lines.append(
                "references this build did not follow (they name another document): "
                + ", ".join(self.unresolved)
            )
        return "\n".join(lines)


def operation_slice(
    document: dict[str, Any],
    operation_id: str,
    *,
    spec_hash: str | None = None,
    depth: int = 1,
    max_schemas: int = 64,
) -> OperationSlice | None:
    """The slice for `operation_id`, or `None` where the document declares no such operation.

    `None` and an empty slice are different claims: one says the specification does not describe
    this operation, the other says it describes it as nothing.
    """
    found = _find(document, operation_id)
    if found is None:
        return None

    path, http_method, operation = found
    schemas, not_expanded, unresolved = _reachable(document, operation, depth, max_schemas)
    return OperationSlice(
        operation_id=operation_id,
        path=path,
        http_method=http_method,
        operation=operation,
        schemas=schemas,
        not_expanded=not_expanded,
        unresolved=unresolved,
        spec_hash=spec_hash,
    )


def _find(document: dict[str, Any], operation_id: str) -> tuple[str, str, dict[str, Any]] | None:
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in _HTTP_METHODS:
            operation = item.get(method)
            if isinstance(operation, dict) and operation.get("operationId") == operation_id:
                return path, method, operation
    return None


def _reachable(
    document: dict[str, Any], operation: dict[str, Any], depth: int, max_schemas: int
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
    """Local schemas within `depth` levels, those past it by name, and references leaving here."""
    components = ((document.get("components") or {}).get("schemas") or {})

    collected: dict[str, Any] = {}
    not_expanded: list[str] = []
    unresolved: list[str] = []
    # `seen` rather than a recursion guard: a schema naming itself is ordinary -- a tree node
    # holding children of its own type -- and must terminate rather than raise.
    seen: set[str] = set()

    frontier = [(reference, 1) for reference in _refs_in(operation)]
    while frontier:
        reference, level = frontier.pop()

        if not reference.startswith(_LOCAL_PREFIX):
            if reference not in unresolved:
                unresolved.append(reference)
            continue

        name = reference[len(_LOCAL_PREFIX):]
        if name in seen:
            continue

        if level > depth:
            if name not in not_expanded:
                not_expanded.append(name)
            continue

        seen.add(name)
        schema = components.get(name)
        if schema is None:
            if reference not in unresolved:
                unresolved.append(reference)
            continue

        if len(collected) >= max_schemas:
            raise SliceTooDeep(
                f"the slice reached more than {max_schemas} schemas within depth {depth}; a "
                f"truncated specification reads to an agent as a vendor declaring nothing where "
                f"the missing part was"
            )
        collected[name] = schema
        frontier.extend((child, level + 1) for child in _refs_in(schema))

    return collected, tuple(sorted(n for n in not_expanded if n not in seen)), tuple(sorted(unresolved))


def _refs_in(node: Any) -> list[str]:
    """Every `$ref` anywhere beneath `node`, in no particular order."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_refs_in(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_refs_in(item))
    return found


def slice_for_cache(cache_dir, spec_hash: str | None = None):
    """A per-change slice renderer over whatever specification a scan already staged.

    A callable rather than a store, for the reason `AgentRemediator._lessons_for` gives: what a
    document says about one change is a per-change lookup, and taking a function keeps the file
    reading on the caller's side of the seam.

    Answers `""` for every absence -- no staged document, a document that will not parse, an
    operation it does not declare. A slice is an improvement to a prompt and never a
    precondition for one, so a missing one degrades the prompt rather than the run.
    """
    import json
    from pathlib import Path

    directory = Path(cache_dir)

    def render(change) -> str:
        operation_id = getattr(change, "operation_id", None)
        if not operation_id:
            return ""
        for candidate in sorted(directory.glob("*.json")):
            try:
                document = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                # Named rather than subsumed. A staged specification really can be undecodable
                # -- a truncated fetch leaves bytes that are not UTF-8 -- and the answer for all
                # three is the same: skip this candidate. A slice is an improvement to a prompt
                # and never a precondition for one, so an unreadable document costs the slice
                # rather than the run.
                continue
            if not isinstance(document, dict) or "paths" not in document:
                continue
            try:
                sliced = operation_slice(document, operation_id, spec_hash=spec_hash)
            except SliceTooDeep:
                return ""
            if sliced is not None:
                return sliced.render()
        return ""

    return render

