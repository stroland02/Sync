"""What the graph can establish about a change and one call site, as the table's inputs.

Moved here from `sync.remediate.tiered` when a third caller appeared. `RoutingFacts` is
declared in `matrix.py` beside the rows that read it, and the function that fills it belongs
next to the table rather than inside one of its callers: the run decides a tier at `locate`,
the watch tick decides one with no clone in hand, and the console previews one for a reader.
Three callers of one derivation, and the whole value of the decision table is that the row
which decided is recorded -- a second implementation is the thing that makes that record a
lie.

`sync.remediate` depends on `sync.route`, so this direction is the only one available: the
reverse would be a cycle at package import.
"""

from __future__ import annotations

from pathlib import Path

from sync.core import CallSite, RepoRef, VendorChange
from sync.route.matrix import RoutingFacts
from sync.route.templates import argument_is_literal_at, language_for
from sync.signals.oasdiff import changed_field


def routing_facts(
    change: VendorChange, site: CallSite, repo: RepoRef | None = None
) -> RoutingFacts:
    """What this layer can establish about the change and the one call site it was given.

    `RoutingFacts` defaults every field to "not established" precisely so a row needing a fact
    declines when the fact is unknown, which is what stops an unpopulated graph routing work to
    a codemod. Three of the four are established here; the fourth is the open one.

    - `field_resolved` comes from the change's own text. A record naming no field is a real
      answer -- `False`, not unknown -- which is what row 2 reads to keep a codemod away from
      a field nobody can name.
    - `value_already_passed` comes from `args_keys`, which is what this call site passes.
    - `field_passed_as_literal` comes from the clone, when there is one. The index records
      which keys a call site passes and never how each was written, so this reads the call
      itself -- see `sync.route.templates.argument_is_literal_at`, which answers `None` for
      anything it cannot establish. Reading the source is not a second index: it is the same
      file the codemod is about to edit, parsed by the same scoping, so router and codemod
      cannot disagree about which call they mean.
    - `call_sites_reading_field` cannot be established here at all. It is a count across the
      whole graph -- how many *indexed* sites read the field -- and `propose` is handed one
      site with no reader for the rest. Row 3, the response-side mechanical row, therefore
      still declines, and a response-property removal still costs an agent run.

    `repo` is optional because two callers have no clone: `nodes.py` previews the route at
    `locate`, and both the watch tick and the console decide without one at all. Without it the
    literal fact stays unknown, so such a preview can only ever name a tier at least as
    expensive as the one `propose` settles on -- a refinement, never a contradiction.
    """
    field = changed_field(change)
    return RoutingFacts(
        field_resolved=field is not None,
        value_already_passed=(field in set(site.args_keys)) if field is not None else None,
        field_passed_as_literal=_passed_as_literal(field, site, repo),
    )


def _passed_as_literal(field: str | None, site: CallSite, repo: RepoRef | None) -> bool | None:
    """The literal fact, or `None` wherever the source cannot settle it.

    Every failure here is `None` rather than `False`. A missing clone, a path the index has
    outlived, bytes that are not UTF-8, a suffix no grammar covers -- none of them is evidence
    about how the argument was written, and absent evidence must never read as permission.
    """
    if field is None or repo is None:
        return None

    language = language_for(site.path)
    if language is None:
        return None

    try:
        source = (Path(repo.local_path) / site.path).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # `CallSite.line` is 1-based off tree-sitter's `start_point` and ast-grep counts from
    # zero, the same conversion `property_omit` makes before the edit.
    return argument_is_literal_at(
        source, field, language=language, line=site.line - 1, col=site.col,
    )
