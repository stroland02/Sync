"""Vendor deprecation tables: the only signal Sync produces that carries a deadline.

Every other detector answers "is this broken?" This one answers "when does this break?", and
a date is worth more than a severity because it can be scheduled.

Three properties make this signal unusually valuable and unusually easy:

**Nobody binds it.** Anthropic's documented audit is to export a CSV of usage by API key and
model; OpenAI publishes shutdown dates in a table. Both tell a team *that* it uses a dying
model. Neither can say which line of code holds the string, because neither has an index of
the customer's source.

**A type checker cannot catch it.** Anthropic's own note: deprecated parameters "remain in the
SDK request types so existing code continues to type-check, but their behavior changes per
model." `tsc` passes; production returns 400. The verification gate Sync already runs is
structurally blind here, which is precisely the case a binding graph exists for.

**The remediation is the most mechanical migration there is** -- one string literal becomes
another, with the replacement named by the vendor. That is tier 0 with no judgement required.

The tables are human documentation and will be restyled without notice, so every parse failure
is a non-result rather than an exception.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from sync.core import Severity, VendorChange

_ROW = re.compile(r"^\|(?P<cells>.+)\|\s*$")
_NOT_BEFORE = re.compile(r"not sooner than\s+(?P<date>.+)$", re.I)
_SEPARATOR = re.compile(r"^[\s|:-]+$")

_STATES = ("active", "legacy", "deprecated", "retired")

# Vendors write dates for humans. Only formats actually observed are accepted; an unrecognised
# one yields None rather than a guess, because a wrong deadline is worse than no deadline.
_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d")


@dataclass(frozen=True)
class ModelDeprecation:
    """One row of a vendor's published model-lifecycle table."""

    vendor_id: str
    model_id: str
    state: str
    replacement: str | None = None
    deprecated_date: date | None = None
    retirement_date: date | None = None
    not_before: date | None = None
    """The floor an active model's row states -- "Not sooner than July 24, 2027".

    Deliberately distinct from `retirement_date`. It is a promise not to retire before a date,
    not a plan to retire on it, and reading it as a deadline would manufacture urgency for a
    model nobody has deprecated.
    """

    @property
    def is_dying(self) -> bool:
        return self.state in ("deprecated", "retired")


def _parse_date(text: str) -> date | None:
    cleaned = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _cells(line: str) -> list[str] | None:
    match = _ROW.match(line.strip())
    if not match or _SEPARATOR.match(line.strip()):
        return None
    return [cell.strip() for cell in match.group("cells").split("|")]


def _state_of(text: str) -> str | None:
    lowered = text.strip().lower()
    return lowered if lowered in _STATES else None


def _is_placeholder(text: str) -> bool:
    """Whether a cell means "nothing here" rather than naming something.

    Vendors write this several ways -- OpenAI uses `---` for five real rows, and `N/A` and an
    em dash both appear. Read as a name, any of them becomes the target of a literal swap: the
    model string is rewritten to `"---"`, which compiles, type-checks, and fails at the vendor.
    A retirement with no replacement has to stay a report.
    """
    cleaned = text.strip()
    if not cleaned:
        return True
    if set(cleaned) <= set("-–—"):
        return True
    return cleaned.lower() in ("n/a", "na", "none", "tbd", "-")


def _strip_code(text: str) -> str:
    """Announcement tables wrap model ids in backticks; the state table does not.

    Left in, a replacement would be written into source as `` "`claude-opus-4-8`" `` -- a
    string that compiles, type-checks, and fails at the vendor.
    """
    return text.strip().strip("`").strip()


def _parse_announcements(markdown: str) -> dict[str, tuple[str | None, date | None]]:
    """Model id to its replacement and shutdown date, from announcement tables.

    Shaped `| date | deprecated model | recommended replacement |`, with no state column --
    which is what keeps them from being read as lifecycle rows. For Anthropic these sit below
    a lifecycle table and only supply the replacement; for OpenAI they are the whole page.
    """
    announcements: dict[str, tuple[str | None, date | None]] = {}

    for line in markdown.splitlines():
        cells = _cells(line)
        if not cells or len(cells) < 3:
            continue
        if any(_state_of(cell) for cell in cells):
            continue

        shutdown = _parse_date(cells[0])
        if shutdown is None:
            continue

        deprecated = _strip_code(cells[1])
        if not deprecated or " " in deprecated or _is_placeholder(deprecated):
            continue

        # A row with no replacement is still a row: the model stops working on the date, and
        # the finding is worth reporting even though nothing can repair it automatically.
        replacement = _strip_code(cells[2])
        if _is_placeholder(replacement) or " " in replacement:
            replacement = None

        announcements[deprecated] = (replacement, shutdown)

    return announcements


def _parse_replacements(markdown: str) -> dict[str, str]:
    """Just the replacement half, for rows whose lifecycle a vendor states itself."""
    return {
        model_id: replacement
        for model_id, (replacement, _) in _parse_announcements(markdown).items()
        if replacement
    }


def _derived_state(retirement: date | None, today: date) -> str:
    """Lifecycle state for a vendor that publishes only a shutdown date.

    A model past its shutdown date is retired whatever any table says, and one with a future
    date is on the way out. Deriving this is both more general than reading a column and more
    truthful than trusting one, since the date is the thing the API actually enforces.
    """
    if retirement is None:
        return "deprecated"
    return "retired" if retirement <= today else "deprecated"


def parse_deprecation_table(
    vendor_id: str, markdown: str, today: date | None = None
) -> list[ModelDeprecation]:
    """Rows from a vendor's published deprecation page.

    Two shapes are handled, because vendors do not agree on one. Anthropic publishes a
    lifecycle table with an explicit state column; OpenAI publishes only shutdown dates and
    leaves state to be inferred. Requiring a state column made the first version of this
    parser silently return nothing for the second vendor.

    Where a vendor does publish state it wins, because it carries information a date cannot:
    a model can be marked deprecated long before any date is set.

    Columns are located by content rather than by position -- these are prose artifacts and
    column order is not a contract anyone has made.
    """
    today = today or date.today()
    rows: list[ModelDeprecation] = []
    # Announcement tables live in the same document as any lifecycle table, and for a vendor
    # without one they are the only source of rows.
    replacements = _parse_replacements(markdown)
    stated: set[str] = set()

    for line in markdown.splitlines():
        cells = _cells(line)
        if not cells or len(cells) < 2:
            continue

        state = next((s for cell in cells if (s := _state_of(cell))), None)
        if state is None:
            continue

        model_id = cells[0]
        if not model_id or " " in model_id:
            continue

        deprecated_date = None
        retirement_date = None
        not_before = None

        for cell in cells[1:]:
            if _state_of(cell):
                continue
            floor = _NOT_BEFORE.search(cell)
            if floor:
                not_before = _parse_date(floor.group("date"))
                continue
            parsed = _parse_date(cell)
            if parsed is None:
                continue
            # The earlier date is the deprecation, the later one the retirement.
            if deprecated_date is None:
                deprecated_date = parsed
            elif parsed >= deprecated_date:
                retirement_date = parsed
            else:
                deprecated_date, retirement_date = parsed, deprecated_date

        # An active row's only date is the "not sooner than" floor, already captured above.
        # Anything else read out of it would be a deadline nobody set.
        if state == "active":
            deprecated_date = None
            retirement_date = None

        rows.append(
            ModelDeprecation(
                vendor_id=vendor_id,
                model_id=model_id,
                state=state,
                replacement=replacements.get(model_id),
                deprecated_date=deprecated_date,
                retirement_date=retirement_date,
                not_before=not_before,
            )
        )
        stated.add(model_id)

    # Vendors that publish no lifecycle table are described entirely by their announcements.
    # Anything already carrying a stated lifecycle is left alone: an explicit column knows
    # things a date cannot, such as a model deprecated before any retirement date exists.
    for model_id, (replacement, shutdown) in _parse_announcements(markdown).items():
        if model_id in stated:
            continue
        rows.append(
            ModelDeprecation(
                vendor_id=vendor_id,
                model_id=model_id,
                state=_derived_state(shutdown, today),
                replacement=replacement,
                deprecated_date=None,
                retirement_date=shutdown,
                not_before=None,
            )
        )

    return rows


def urgency(row: ModelDeprecation, today: date) -> int | None:
    """Days until the model stops working, or None when it is not dying.

    Negative means the retirement date has passed: the vendor states that requests to a retired
    model fail, so this is an outage already in the code rather than a deadline approaching.
    That distinction is why the return is signed rather than clamped.
    """
    if not row.is_dying or row.retirement_date is None:
        return None
    return (row.retirement_date - today).days


def _severity_for(row: ModelDeprecation) -> Severity:
    return "breaking" if row.state == "retired" else "deprecation"


def to_vendor_changes(
    rows: list[ModelDeprecation], from_version: str, to_version: str
) -> list[VendorChange]:
    """`VendorChange` rows for the models that are dying, and only those.

    An active model is not a change. Emitting one would put a finding against every model a
    codebase names, which is how a tool teaches people to ignore it.

    The retirement date rides in `raw` rather than in a new column: `sync.core` is a contract
    every adapter and the graph surface depend on, and one adapter's deadline does not justify
    changing it.
    """
    changes: list[VendorChange] = []

    for row in rows:
        if not row.is_dying:
            continue
        changes.append(
            VendorChange(
                vendor_id=row.vendor_id,
                from_version=from_version,
                to_version=to_version,
                # Namespaced so these can never collide with oasdiff rule ids, which are what
                # `kind` holds everywhere else and what routing tables key on.
                kind=f"deprecation/model-{row.state}",
                operation_id=row.model_id,
                path_ptr="",
                severity=_severity_for(row),
                source="vendor-deprecation-table",
                raw={
                    "model_id": row.model_id,
                    "state": row.state,
                    "replacement": row.replacement,
                    "retirement_date": row.retirement_date.isoformat() if row.retirement_date else None,
                    "deprecated_date": row.deprecated_date.isoformat() if row.deprecated_date else None,
                },
            )
        )

    return changes
