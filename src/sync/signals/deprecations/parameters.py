"""Parameters a vendor deprecated while the SDK still accepts them.

The sharpest case in the whole system. Anthropic's own words: deprecated parameters "remain in
the SDK request types so existing code continues to type-check, but their behavior changes per
model." The compiler is green and the vendor returns 400. This repository hit exactly that --
`CLAUDE.md` records `temperature`, `top_p` and `budget_tokens` returning HTTP 400 -- so the
argument for a binding graph here is history rather than theory.

It is also the first finding that needs two facts about one call site: that it passes the
parameter, and that it targets a model the deprecation applies to. `temperature` is fine on an
older model and a 400 on Claude 4.7 or later, so the model scope is parsed rather than
discarded -- without it every repository that has not upgraded gets a false positive.

This module parses. It deliberately emits no `VendorChange`: the join for a parameter is
against `CallSite.args_keys`, not `operation_id`, and emitting changes that no detector can
join would produce findings that point at nothing -- the failure mode this signal exists to
avoid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
_SEPARATOR = re.compile(r"^[\s|:-]+$")
_STATUS = re.compile(r"^\s*(?P<state>deprecated|removed)\b\s*(?:\((?P<scope>[^)]*)\))?", re.I)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MARKDOWN_LINK = re.compile(r"\[(?P<text>[^\]]*)\]\([^)]*\)")

Remedy = str
"""`"rename"` when the vendor named a successor parameter, `"omit"` when it did not."""


@dataclass(frozen=True)
class ParameterDeprecation:
    """One request parameter a vendor no longer honours, for some range of models."""

    vendor_id: str
    parameter: str
    status: str
    behavior: str
    applies_from: str | None = None
    """The model scope the deprecation begins at, verbatim -- "Claude Opus 4.7 and later".

    Kept because it decides whether a call site is affected at all. Discarding it would make
    every repository passing the parameter look broken, including those on models where it
    still works.
    """

    replacement: str | None = None
    """A successor parameter, when the vendor named an identifier rather than giving advice."""

    @property
    def remedy(self) -> Remedy:
        return "rename" if self.replacement else "omit"


def _cells(line: str) -> list[str] | None:
    stripped = line.strip()
    match = _ROW.match(stripped)
    if not match or _SEPARATOR.match(stripped):
        return None
    return [cell.strip() for cell in match.group("cells").split("|")]


def _parameters_in(cell: str) -> list[str]:
    """Parameter names from a cell that may list several.

    The published table groups parameters sharing a fate -- `temperature`, `top_p`, `top_k` in
    one row. Kept grouped, a finding would name three parameters when a call site passes one,
    which a reviewer cannot act on without re-reading the vendor's page.
    """
    names = [part.strip().strip("`").strip() for part in cell.split(",")]
    return [name for name in names if _IDENTIFIER.match(name)]


def _replacement_in(cell: str) -> str | None:
    """A successor parameter, or `None` when the cell is advice rather than an identifier.

    "Omit and use prompting to guide behavior" is guidance. Read as a name it becomes the
    target of a rename, writing a sentence into an argument position -- the same class as the
    `---` placeholder and the markdown link, and the reason the remedy here is removal.
    """
    text = _MARKDOWN_LINK.sub(r"\g<text>", cell).strip().strip("`").strip()
    return text if _IDENTIFIER.match(text) else None


def parse_parameter_deprecations(vendor_id: str, markdown: str) -> list[ParameterDeprecation]:
    """Parameter deprecations from a vendor's published page.

    A parameter row is recognised by its status cell reading "Deprecated" or "Removed",
    optionally followed by a parenthesised model scope. A model lifecycle row carries a bare
    state instead, which is what keeps the two tables on one page from being confused -- read
    as parameters, the lifecycle rows would emit a finding per model name.
    """
    rows: list[ParameterDeprecation] = []

    for line in markdown.splitlines():
        cells = _cells(line)
        if not cells or len(cells) < 3:
            continue

        status_cell, status = next(
            ((cell, match) for cell in cells[1:] if (match := _STATUS.match(cell))),
            (None, None),
        )
        if status is None or status_cell is None:
            continue

        parameters = _parameters_in(cells[0])
        if not parameters:
            continue

        remaining = [cell for cell in cells[1:] if cell is not status_cell]
        behavior = remaining[0] if remaining else ""
        replacement = _replacement_in(remaining[1]) if len(remaining) > 1 else None
        scope = (status.group("scope") or "").strip() or None

        rows.extend(
            ParameterDeprecation(
                vendor_id=vendor_id,
                parameter=name,
                status=status_cell,
                behavior=behavior,
                applies_from=scope,
                replacement=replacement,
            )
            for name in parameters
        )

    return rows
