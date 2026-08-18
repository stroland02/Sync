"""View models for the graph itself: the binding surface, the observed rung, detector
accountability.

`sync.dashboard.queries` and `sync.dashboard.fleet` answer questions about one finding and about
every run, respectively. Neither renders the graph the findings come from -- the call sites, the
vendor changes, and the telemetry a binding rests on. This module does, reading `GraphStore`
alone and never `sync.remediate`, matching the convention both of those modules already keep:
every function returns primitives -- dicts, lists, strings, numbers -- never a live model, so a
page that received one could not lazily re-query or mutate it.

Eight functions, eight questions. Four of them take an optional `repo_id` and echo it back:
repository scope is what every console level below Codebase inherits, and a payload that names
the scope it was computed in cannot be rendered under the wrong heading in silence.

- `binding_surface` -- given a vendor operation, which call sites currently depend on it, and
  what has the vendor changed about it. The API Dependency Graph made visible.
- `index_coverage` -- for one repository, how many call sites the index holds per vendor and
  when it last indexed each one. What Sync actually knows about a codebase, and how current
  that knowledge is -- neither had an answer anywhere in the console before this.
- `observed_telemetry` -- for one repository, what traffic showed up, what shape it had, and how
  often it failed. The telemetry rung of the graph, which has no surface at all before this.
- `vendor_findings` -- open findings against one vendor, as the rows the API Services screen
  renders. What the frozen `GraphSurface.whats_at_risk` answers for an agent, answered here
  because that method cannot be narrowed to a repository and `sync.mcp.tools` does not change.
- `detector_accountability` -- across every open finding, which detector raised how many, at
  which rungs, with what claims. `CLAUDE.md` requires a false positive be attributable to a rung;
  this is what lets an operator see that per detector rather than per row.
- `severity_rollup` -- across every open finding, a count per severity and the true total, each
  its own SQL aggregate rather than two numbers read off one Python list.
- `overview_summary` -- the fleet screen's lead answer: open findings by vendor, and a total
  that is honest about whether it stopped counting early. `overview_summary`'s own docstring
  carries why this reads `GraphStore` directly rather than the frozen `GraphSurface`.
- `repo_context` -- one repository's context row: what stays true of the checkout, and which of
  `seeded-file` or `operator` wrote it. Absent is an empty body with a null source, not a 404.

**What none of these may claim.** An observed call is evidence a call site was exercised. It is
not proof the binding is correct -- the correlation that produced it can itself be wrong, which
is exactly why `observed_call.binding_rung` exists as a column and not an assumption. Nothing
here promotes an observation to a verdict; that stays the reader's job, informed by the rung.
"""

from __future__ import annotations

from collections import Counter

from sync.core import ALLOWED_MERGE_METHODS, ALLOWED_MERGE_POLICIES
from sync.core.models import SEVERITY_ORDER
from sync.graph.store import DEFAULT_FINDING_ORDER, FINDING_ORDERS, GraphStore
from sync.mcp.tools import DEFAULT_LIMIT, _TOKENS_PER_AVOIDED_READ

# The only rung a row built from `call_site` alone can honestly carry -- see `binding_surface`'s
# own docstring. Named so the `binding_rung` filter has one place to compare against rather than
# a literal repeated at the filter and at the row-building below.
_CALL_SITE_RUNG = "static"


def _page(items: list[dict], total: int, offset: int) -> dict:
    """One page, shaped identically everywhere this module paginates something: the items, the
    true total the page was drawn from, and the offset of the next page or `None` on the last
    one. A shared shape is what lets three independent sets on one screen (`observed_telemetry`)
    or two on one screen (`binding_surface`) page without a caller having to learn a fourth
    envelope shape for each new set.
    """
    consumed = offset + len(items)
    return {"items": items, "total": total, "next_offset": consumed if consumed < total else None}


_EMPTY_PAGE = {"items": [], "total": 0, "next_offset": None}


def _call_site_row(site) -> dict:
    return {
        "repo_id": site.repo_id,
        "path": site.path,
        "line": site.line,
        "col": site.col,
        "symbol": site.symbol,
        "sdk_version": site.sdk_version,
        "args_keys": list(site.args_keys),
        "response_fields_read": list(site.response_fields_read),
        "loop_depth": site.loop_depth,
        "binding_rung": _CALL_SITE_RUNG,
        "indexed_at": site.indexed_at.isoformat(),
    }


def _change_row(change) -> dict:
    return {
        "change_id": change.id,
        "kind": change.kind,
        "severity": change.severity,
        "from_version": change.from_version,
        "to_version": change.to_version,
        "path_ptr": change.path_ptr,
        "detected_at": change.detected_at.isoformat(),
    }


def binding_surface(
    store: GraphStore,
    vendor_id: str,
    operation_id: str,
    *,
    repo_id: str | None = None,
    path_prefix: str | None = None,
    binding_rung: str | None = None,
    call_sites_limit: int = DEFAULT_LIMIT,
    call_sites_offset: int = 0,
    changes_limit: int = DEFAULT_LIMIT,
    changes_offset: int = 0,
) -> dict:
    """Every call site the index currently holds against one vendor operation, and what the
    vendor has changed about it -- each half its own independent page.

    Reads `call_sites_for_operation` and `vendor_changes_for_operation`, both with a real SQL
    `LIMIT`, plus their matching `_count` reads for the true total each page is drawn from. The
    two pages are independent on purpose: call sites and changes are different questions with
    different cardinalities, and a customer with a long feed history but few call sites (or the
    reverse) must be able to page one without the other's size leaking in.

    `repo_id` is optional and its absence means every repository, matching
    `call_sites_for_operation`'s own contract: an aggregate across customers is a real question
    and a detector is not what is asking it here.

    `path_prefix` narrows the call sites to a directory, and narrows their total with them. It
    does not touch the changes: a vendor change has no position in the customer's codebase --
    `path_ptr` points into the vendor's own specification -- so filtering it by a source path
    would answer a question nobody asked with rows that happened to share a prefix.

    `repositories` is which repositories hold a live call site on this operation and how many
    each holds, **computed with neither `repo_id` nor `path_prefix` applied**. It is the option
    list those filters are set from, and an option list narrowed by the filter it sets collapses
    to whatever is already selected with no way back to the rest. Its counts are therefore counts
    over the whole operation rather than over the page beside it; a caller renders which of the
    two it is showing rather than leaving a reader to assume they agree.

    **Every call site row reports `binding_rung: "static"`, unconditionally.** A call site is
    what the static index found; nothing about the row rests on a resolution step or on watched
    traffic, so `static` is not a default standing in for an unknown value -- it is the only
    rung a row built from `call_site` alone can honestly carry. A stronger rung for the same
    binding would come from `observed_telemetry` on this same repository and vendor operation,
    as a second, separate kind of evidence, never as a replacement written here.

    `binding_rung`, when given, is a real question with a real answer rather than a filter this
    view merely tolerates: since every call site row carries `"static"`, asking for any other
    value is answered with an empty page of call sites -- not silently the unfiltered set, and
    not an error. Changes carry no rung at all and are untouched by this filter.

    An operation nobody calls, or one the vendor has never changed, returns empty pages rather
    than an error: "nothing recorded" is a true answer for either half of this payload.

    **This surface cannot see a call site the code used to have.** `call_sites_for_operation`
    excludes a retracted row and takes no parameter to include it, so nothing here can report
    that a position was ever occupied and then given up -- not as an empty field, not at all.
    That silence is the correct answer to what this view asks ("what does my code depend on
    now"), but it means an absent call site reads identically whether the code never bound this
    operation or bound it and later stopped. A reader after the second story wants
    `GraphStore.get_call_site`, by the id a finding already holds, not this view.
    """
    call_sites_offset = max(call_sites_offset, 0)
    changes_offset = max(changes_offset, 0)

    if binding_rung is not None and binding_rung != _CALL_SITE_RUNG:
        call_sites_page = dict(_EMPTY_PAGE)
        # Empties with the page it describes. A directory named above a table with no rows in it is
        # a claim about rows the reader cannot see, which is the shape of false claim this whole
        # view is careful about elsewhere.
        common_directory = ""
    else:
        sites = store.call_sites_for_operation(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix,
            limit=call_sites_limit, offset=call_sites_offset,
        )
        sites_total = store.call_sites_for_operation_count(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix
        )
        call_sites_page = _page([_call_site_row(s) for s in sites], sites_total, call_sites_offset)
        common_directory = store.call_sites_common_directory(
            vendor_id, operation_id, repo_id=repo_id, path_prefix=path_prefix
        )

    changes = store.vendor_changes_for_operation(
        vendor_id, operation_id, limit=changes_limit, offset=changes_offset
    )
    changes_total = store.vendor_changes_for_operation_count(vendor_id, operation_id)
    changes_page = _page([_change_row(c) for c in changes], changes_total, changes_offset)

    repositories = store.call_site_repositories_for_operation(vendor_id, operation_id)

    return {
        "vendor_id": vendor_id,
        "operation_id": operation_id,
        "repo_id": repo_id,
        "path_prefix": path_prefix,
        "call_sites": call_sites_page,
        # The deepest directory every call site in the *filtered set* shares, or `""`. The screen
        # states it once above the path column and gives each row the part that distinguishes it --
        # on a real repository most of that column's width is a prefix identical on every row.
        # Computed under the page's own predicate rather than over its fifty rows, so the same call
        # site does not render differently on page one and page two.
        "call_sites_common_directory": common_directory,
        "changes": changes_page,
        "repositories": [
            {"repo_id": repo, "call_site_count": count} for repo, count in repositories.items()
        ],
    }


def index_coverage(store: GraphStore, repo_id: str) -> dict:
    """How many indexed call sites one repository has per vendor, and when the index last wrote
    a row for each.

    Reads `call_site_coverage`, one `GraphStore` round trip that returns both facts per vendor
    together. This view used to read `call_site_counts` and a since-removed
    `call_site_last_indexed` separately and key one by the other's result -- two round trips
    against the same table have no shared snapshot even inside one transaction, since Postgres's
    default READ COMMITTED gives every statement its own, so a call site indexed for a vendor
    between the two reads put that vendor in one result and not the other and the composition
    raised `KeyError`. One query cannot disagree with itself, so `by_vendor` and `last_indexed`
    below are built from the same rows and share their key set by construction rather than by
    the two reads happening to land close enough together.

    `by_vendor` reports the same counts `call_site_counts` always did, unaltered: the console's
    `Tally` type (`web/src/api/types.ts`) is `Record<string, number>` and several screens already
    read this route against that shape, so the count stays a plain int rather than growing a
    nested object that would break every one of them for a repository this change did not need
    to touch. `last_indexed` sits beside it, keyed the same way.

    **A vendor with no call sites is absent from both `by_vendor` and `last_indexed` -- no zero
    count, no null timestamp.** `call_site_coverage`'s own contract is that this absence has two
    causes a query cannot separate: the indexer looked and found nothing, or it never looked
    because nothing declares which package to look for. Either a zero or a null would assert the
    first, so neither is invented here. `sync.signals.reachability` is where that resolution
    happens, not this view.

    **What `last_indexed` means, and what it does not.** It is when the indexer last wrote a row
    for that vendor in this repository -- the newest `indexed_at` among the call sites
    `call_site_coverage` just counted. It is **not** a promise that the index is current, and it
    is **not** evidence the code has not changed since: a repository re-scanned three weeks ago
    reports the same value the day after that scan and every day after, until another re-index
    moves it. A reader who takes it as either has been misled by a field that looks more
    definitive than it is -- which is exactly why it is reported at all: a count with no sense
    of when it was taken invites treating a stale answer as a current one.

    **No staleness or age figure is computed here.** A duration derived from `last_indexed` at
    response time goes wrong the instant this payload is cached or read later than it was built,
    silently, while the timestamp it would have come from does not. The console formats the age
    against its own clock; this view hands over the fact it can actually stand behind.
    """
    coverage = store.call_site_coverage(repo_id)
    return {
        "repo_id": repo_id,
        "by_vendor": {vendor_id: count for vendor_id, (count, _) in coverage.items()},
        "last_indexed": {
            vendor_id: last_indexed.isoformat() for vendor_id, (_, last_indexed) in coverage.items()
        },
        "total_call_sites": sum(count for count, _ in coverage.values()),
    }


def _observed_call_row(call) -> dict:
    return {
        "repo_id": call.repo_id,
        "vendor_id": call.vendor_id,
        "operation_id": call.operation_id,
        "binding_rung": call.binding_rung,
        "server_address": call.server_address,
        "http_method": call.http_method,
        "trace_id": call.trace_id,
        "url_template": call.url_template,
        "call_count": call.call_count,
        "distinct_targets": call.distinct_targets,
        "repeated_calls": call.repeated_calls,
        "max_resend_count": call.max_resend_count,
        "error_count": call.error_count,
        "first_seen": call.first_seen.isoformat(),
        "last_seen": call.last_seen.isoformat(),
    }


def _observed_shape_row(shape) -> dict:
    return {
        "vendor_id": shape.vendor_id,
        "operation_id": shape.operation_id,
        "field_path": shape.field_path,
        "json_type": shape.json_type,
        "nullable_seen": shape.nullable_seen,
        "spec_enum_values": list(shape.spec_enum_values),
        "source": shape.source,
        "sample_count": shape.sample_count,
        "first_seen": shape.first_seen.isoformat(),
        "last_seen": shape.last_seen.isoformat(),
    }


def _observed_error_window_row(window) -> dict:
    return {
        "repo_id": window.repo_id,
        "vendor_id": window.vendor_id,
        "operation_id": window.operation_id,
        "binding_rung": window.binding_rung,
        "source": window.source,
        "status_class": window.status_class,
        "window_start": window.window_start.isoformat(),
        "window_end": window.window_end.isoformat(),
        "error_count": window.error_count,
        "issue_count": window.issue_count,
    }


def observed_telemetry(
    store: GraphStore,
    repo_id: str,
    *,
    calls_limit: int = DEFAULT_LIMIT,
    calls_offset: int = 0,
    shapes_limit: int = DEFAULT_LIMIT,
    shapes_offset: int = 0,
    error_windows_limit: int = DEFAULT_LIMIT,
    error_windows_offset: int = 0,
) -> dict:
    """The telemetry rung of the graph for one repository: what traffic showed up, what shape it
    had, and how often it failed -- three independent pages, because they are three questions of
    different cardinality stacked on one screen.

    - `observed_calls` -- one row per unit of work's use of one operation. Every derived count
      on a row (`call_count`, `distinct_targets`, `repeated_calls`, `max_resend_count`,
      `error_count`) is read off the model's own properties rather than recomputed from `spans`
      here, so this view cannot disagree with `ObservedCall` about what its own data means.
    - `observed_shapes_for_operations` -- **not** repository-scoped in the schema; a shape is a
      fact about what a vendor operation sends, independent of who calls it. So this joins in
      through `observed_operation_pairs`, the `(vendor_id, operation_id)` pairs this
      repository's *entire* observed history actually names -- not just the pairs on the current
      page of calls, which is what makes the shapes page independent of the calls page rather
      than a subset of it that happens to move when a reader changes `calls_offset`.
      `GraphStore.observed_shapes_for_operations` is one query regardless of how many pairs are
      named, which is what replaces the one-query-per-pair this view used to issue. An
      uncorrelated call -- empty `operation_id`, rung `unresolved` -- names no pair and joins
      nothing: `observed_operation_pairs` excludes it before this ever runs.
    - `observed_error_windows` -- one row per operation's failure count over one window this
      repository's tracker was asked about. Reported as-is: `error_count` has no denominator in
      this table (`schema.sql`'s own grain note), and this view does not compute one.

    **What an observed call can and cannot say.** A row here is evidence that a call site was
    exercised -- proof the code path ran, at least once, against this vendor. It is not proof
    that the binding correlating it to an operation is correct: `binding_rung` on the row says
    which of those two claims this is, `observed` for a correlation that ran or `unresolved` for
    a request nothing could attribute. Neither is a verdict; the reader weighs the finding by it.
    """
    calls_offset = max(calls_offset, 0)
    shapes_offset = max(shapes_offset, 0)
    error_windows_offset = max(error_windows_offset, 0)

    calls = store.observed_calls(repo_id, limit=calls_limit, offset=calls_offset)
    calls_total = store.observed_calls_count(repo_id)
    calls_page = _page([_observed_call_row(c) for c in calls], calls_total, calls_offset)

    operation_pairs = store.observed_operation_pairs(repo_id)
    shapes = store.observed_shapes_for_operations(
        operation_pairs, limit=shapes_limit, offset=shapes_offset
    )
    shapes_total = store.observed_shapes_for_operations_count(operation_pairs)
    shapes_page = _page([_observed_shape_row(s) for s in shapes], shapes_total, shapes_offset)

    windows = store.observed_error_windows(
        repo_id, limit=error_windows_limit, offset=error_windows_offset
    )
    windows_total = store.observed_error_windows_count(repo_id)
    windows_page = _page(
        [_observed_error_window_row(w) for w in windows], windows_total, error_windows_offset
    )

    ctx = store.repo_context(repo_id)
    telemetry_attached_at = (
        ctx.telemetry_attached_at.isoformat()
        if ctx is not None and ctx.telemetry_attached_at is not None
        else None
    )

    return {
        "repo_id": repo_id,
        "telemetry_attached_at": telemetry_attached_at,
        "calls": calls_page,
        "shapes": shapes_page,
        "error_windows": windows_page,
    }


def findings_page(
    store: GraphStore,
    *,
    repo_id: str | None = None,
    vendor_id: str | None = None,
    severity: str | None = None,
    path: str | None = None,
    order: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """Open findings across vendors for one codebase or across the fleet.

    Provides the primary findings view for the Codebase Overview screen (all findings for ONE
    selected codebase, across vendors) as well as the fleet findings view.
    """
    offset = max(offset, 0)
    applied_order = order if order in FINDING_ORDERS else DEFAULT_FINDING_ORDER
    filters = dict(repo_id=repo_id, vendor_id=vendor_id, severity=severity, path_prefix=path)
    rows = store.open_findings_at_risk(
        **filters, order=applied_order, limit=limit, offset=offset
    )
    total = store.open_findings_at_risk_count(**filters)
    summary = store.open_findings_summary(**filters)
    indexed_at = summary["indexed_at"]
    return {
        **_page(
            [
                {
                    "file": row["path"],
                    "line": row["line"],
                    "symbol": row["symbol"],
                    "operation": row["operation_id"],
                    "vendor": row["vendor_id"],
                    "change_kind": row["change_kind"],
                    "severity": row["severity"],
                    "finding_id": row["finding_id"],
                    "binding_source": row["binding_rung"],
                }
                for row in rows
            ],
            total,
            offset,
        ),
        "repo_id": repo_id,
        "vendor_id": vendor_id,
        "order": applied_order,
        "severity_order": list(SEVERITY_ORDER),
        "indexed_at": indexed_at.isoformat() if indexed_at else None,
        "feed_fetched_at": None,
        "binding_source": summary["binding_rung"],
        "context_savings": len(rows) * _TOKENS_PER_AVOIDED_READ,
    }


def vendor_findings(
    store: GraphStore,
    vendor_id: str,
    *,
    repo_id: str | None = None,
    severity: str | None = None,
    path: str | None = None,
    order: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> dict:
    """Open findings against one vendor, as the binding rows the API Services screen renders --
    one page, with the provenance envelope every console page carries.
    """
    return findings_page(
        store,
        repo_id=repo_id,
        vendor_id=vendor_id,
        severity=severity,
        path=path,
        order=order,
        limit=limit,
        offset=offset,
    )


def severity_rollup(
    store: GraphStore, *, repo_id: str | None = None, vendor_id: str | None = None
) -> dict:
    """Every open finding's severity, tallied once: a count per severity and the total.

    `by_severity` is `open_findings_severity_counts`, a real SQL `GROUP BY` -- not a `Counter`
    over a full Python fetch of every `Finding`, which is what this read until the fleet screen's
    scale defect (section 24, `2026-08-05-sync-console-architecture.md`) named it as one more
    instance of the same shape: a question whose cardinality is the number of severities, answered
    by materialising a row per finding. `total` is `open_findings_count`, its own separate
    aggregate, read independently of the breakdown on purpose -- a sum over a filtered or
    paginated set silently understates the true total the moment either is introduced, which is
    the recurring defect this milestone keeps closing (`overview_summary` carries the same
    independence for the vendor breakdown beside it).

    `repo_id` and `vendor_id` narrow both aggregates together. Narrowing one and not the other
    would report a breakdown of one scope against a denominator drawn from a wider one, which is
    the same class of false claim with the arithmetic done for the reader.

    **The two scopes compose rather than replace each other.** A vendor screen opened inside a
    selected repository asks for that vendor *in* that repository -- passing only the vendor
    would put a fleet-wide breakdown under a repository heading, and passing only the repository
    would put every vendor's severities beside one vendor's findings. Both are the same defect
    one axis at a time.

    **A scope with nothing open is `{}` and zero, never the wider answer.** A filter that
    silently serves the unscoped result when it matches nothing is the worst shape a filter can
    take: it reports numbers that are true of something, so nothing on screen looks broken.
    """
    return {
        "by_severity": store.open_findings_severity_counts(repo_id=repo_id, vendor_id=vendor_id),
        "total": store.open_findings_count(repo_id=repo_id, vendor_id=vendor_id),
    }


# Ceiling on how many open findings `/api/overview`'s total counts before it stops looking and
# reports the bound instead of an exact number, mirroring Sentry's `MAX_HITS_LIMIT`
# (`paginator.py:26`): ten thousand matching rows cost the same as one thousand once the count is
# a real SQL `LIMIT` rather than a full scan, and a bounded count that says so is more honest than
# an exact one that took nineteen seconds of scanning to produce (section 24 of
# `2026-08-05-sync-console-architecture.md` carries the argument).
OPEN_FINDING_COUNT_BOUND = 1000


def overview_summary(
    store: GraphStore, *, repo_id: str | None = None, bound: int = OPEN_FINDING_COUNT_BOUND
) -> dict:
    """The fleet screen's lead answer: open findings by vendor, and a total that says honestly
    whether it stopped counting early.

    This is what `/api/overview` reads instead of the frozen `GraphSurface.whats_at_risk` --
    `sync.mcp.tools` is frozen and `whats_at_risk` always walks every open finding doing one
    `get_call_site` round trip per row to build its shallow rows, so no `limit` passed to it
    bounds the underlying scan; the route used to call it twice (a probe, then a page sized to
    the probe's own total) and tally vendors in a Python loop over the result, which is section
    24's defect measured at 9-19 seconds against ten thousand call sites. This view answers the
    same question against `GraphStore` directly, as `binding_surface` and `observed_telemetry`
    already do for their own screens, entirely in real SQL:

    - `total_findings` is `open_findings_count_bounded` -- a `count(*)` over a subquery Postgres
      stops scanning at `bound`, so the total costs the same at any true count above it.
      `total_findings_bound` and `total_findings_bound_reached` travel with it so the console can
      render "1,000+" rather than a bare number a nineteen-second scan would have implied was
      exact.
    - `vendors` is `open_findings_vendor_counts`, a `GROUP BY` over the whole table and
      deliberately **not** bounded: the caveat in section 24.2 is written in hard for exactly this
      pairing -- a distribution derived from a bounded page is the distribution of whichever rows
      the ordering reached, not of the population, and a bounded total is honest where a bounded
      breakdown presented as the breakdown is not. Vendor cardinality does not grow with finding
      count, so this `GROUP BY` is cheap at any scale the bounded total is protecting against.
    - `indexed_at` and `binding_source` are `open_findings_summary`'s one-query snapshot over
      every open finding -- unbounded for the reason the vendor breakdown is: they describe the
      whole answer, not a truncated page of it.
    - `feed_fetched_at` is always `None`. `sync/api/__main__.py` constructs the frozen
      `GraphSurface` with no `feed_fetched_at` anywhere in this deployment, so the field this
      route has always reported was already always null; this keeps reporting the same true
      absence instead of inventing a value the surface it replaces never had either.
    - `context_savings` is `total_findings * _TOKENS_PER_AVOIDED_READ` -- the same constant
      `whats_at_risk`'s own envelope multiplies by, read from `sync.mcp.tools` rather than
      restated, so the two routes' claims about the cost of a file read they avoided cannot drift
      apart. Built from the *bounded* total rather than the true one: past `bound` this
      understates the real savings, which is the honest direction for a number the console
      already renders beside a total that says it stopped counting early.
    - `context_savings_bound_reached` travels with `context_savings` for the same reason
      `total_findings_bound_reached` travels with `total_findings`: a figure derived from a
      truncated scan must carry the fact that it was truncated, rather than leaving a render
      site to notice on its own that the sibling total was bounded and infer the multiplication
      inherited the same ceiling. Today the two flags are always equal -- `context_savings` has
      no scan of its own, only `total_findings`'s -- but the field is named for what it asserts
      about *this* number, not for the mechanism behind it, so a future change to how savings is
      estimated (a per-finding cost rather than a flat multiplier, say) would not silently strand
      a render site that had learned to read `total_findings_bound_reached` for both.

    `repo_id` narrows every one of those reads together and is echoed back in the payload. It is
    `None` on the fleet screen, which is the level above Codebase and the one place a fleet-wide
    answer is the answer; anywhere below it, a null here rendered under a repository's name is a
    false claim about that repository.
    """
    total, bound_reached = store.open_findings_count_bounded(bound, repo_id=repo_id)
    vendor_counts = store.open_findings_vendor_counts(repo_id=repo_id)
    summary = store.open_findings_summary(repo_id=repo_id)
    indexed_at = summary["indexed_at"]
    payload = {
        "repo_id": repo_id,
        "vendors": [
            {"vendor_id": vendor_id, "open_finding_count": count}
            for vendor_id, count in vendor_counts.items()
        ],
        "total_findings": total,
        "total_findings_bound": bound,
        "total_findings_bound_reached": bound_reached,
        "indexed_at": indexed_at.isoformat() if indexed_at else None,
        "feed_fetched_at": None,
        "binding_source": summary["binding_rung"],
        "context_savings": total * _TOKENS_PER_AVOIDED_READ,
        "context_savings_bound_reached": bound_reached,
    }
    if repo_id is None:
        payload["repositories"] = store.open_findings_repository_summaries()
    return payload


def repo_context(store: GraphStore, repo_id: str) -> dict:
    """One repository's context, as the row the console renders.

    Echoes `repo_id` back for the reason every repository-scoped view here does: a payload that
    names the scope it was computed in cannot be rendered under the wrong heading in silence.

    `source` is part of the payload rather than an internal detail. The precedence rule --
    a `seeded-file` row is overwritten by the next index and an `operator` row is not -- is
    invisible in the body and surprising when met, so a screen that rendered bare prose would
    be hiding the one fact a reader needs before editing it.

    An absent row is an empty body with a null source rather than a 404. A repository that has
    no context is a normal repository, and the screen that offers to write some is the same
    screen that shows what is there.
    """
    found = store.repo_context(repo_id)
    return {
        "repo_id": repo_id,
        "body": found.body if found is not None else "",
        "source": found.source if found is not None else None,
        "updated_at": found.updated_at.isoformat() if found is not None and found.updated_at else None,
        "telemetry_attached_at": (
            found.telemetry_attached_at.isoformat()
            if found is not None and found.telemetry_attached_at is not None
            else None
        ),
    }


def repo_settings(store: GraphStore, repo_id: str) -> dict:
    """One repository's automation and merge settings, as the row the console renders."""
    settings = store.repo_settings(repo_id)
    return {
        "repo_id": repo_id,
        "merge_policy": settings.merge_policy,
        "merge_method": settings.merge_method,
        "base_branch": settings.base_branch,
        "allowed_merge_policies": list(ALLOWED_MERGE_POLICIES),
        "allowed_merge_methods": list(ALLOWED_MERGE_METHODS),
        "merge_policy_refusals": settings.merge_policy_refusals,
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def detector_accountability(store: GraphStore, *, repo_id: str | None = None) -> dict:
    """Every open finding, aggregated by the detector that raised it: how many, at which rungs,
    with what claims and severities.

    **Scoped to `open_findings`, which is the only findings read `GraphStore` offers.** That
    method excludes a finding whose status is no longer `'open'` and one whose call site has
    been retracted (`GraphStore.open_findings`'s own docstring). A closed finding is invisible
    here exactly as it is invisible everywhere else in the console today -- this is not a new
    limit this view invents, it inherits the one `GraphStore` already has.

    **The rung breakdown per detector is the point, not an incidental column.** `CLAUDE.md`
    requires that a false positive be attributable to the rung that produced it, and a detector
    is where that attribution has to land: a detector whose findings rest entirely on `static`
    is making a claim of one kind, and one whose findings mix `static` and `observed` is making
    two different kinds of claim under one name. Collapsing the rungs into a single count per
    detector would erase exactly the distinction this column exists to preserve.

    `repo_id` narrows it to one codebase, which is what makes this readable underneath the
    Codebase level rather than only beside it: "which detector is producing my false positives"
    is a question about one repository at least as often as about the fleet. `open_findings_page`
    unbounded rather than `open_findings` is one read for both cases -- the unpaginated method
    takes no filter, because `sync.mcp.tools.GraphReader` pins its signature exactly.
    """
    findings = store.open_findings_page(repo_id=repo_id)

    by_detector: dict[str, dict] = {}
    for finding in findings:
        entry = by_detector.setdefault(
            finding.detector,
            {
                "detector": finding.detector,
                "total": 0,
                "by_rung": Counter(),
                "by_claim": Counter(),
                "by_severity": Counter(),
            },
        )
        entry["total"] += 1
        entry["by_rung"][finding.binding_rung] += 1
        entry["by_claim"][finding.claim] += 1
        entry["by_severity"][finding.severity] += 1

    detectors = [
        {
            "detector": entry["detector"],
            "total": entry["total"],
            "by_rung": dict(entry["by_rung"]),
            "by_claim": dict(entry["by_claim"]),
            "by_severity": dict(entry["by_severity"]),
        }
        for _, entry in sorted(by_detector.items())
    ]

    # -- Grain: One count per distinct open finding across all detectors, broken down by binding_rung.
    # Open findings are counted once each across the whole scope.
    # Every known rung ('static', 'resolved', 'observed', 'unresolved', 'unattributed') is explicitly present in the tally.
    known_rungs = ("static", "resolved", "observed", "unresolved", "unattributed")
    rung_tally: dict[str, int] = {rung: 0 for rung in known_rungs}
    for finding in findings:
        rung_tally[finding.binding_rung] = rung_tally.get(finding.binding_rung, 0) + 1

    return {
        "repo_id": repo_id,
        "detectors": detectors,
        "by_rung": rung_tally,
        "total_open_findings": len(findings),
    }


def vendor_change_volume(store: GraphStore, vendor_id: str) -> dict:
    """Aggregated change volume and timeline for one vendor: M0-W329 dashboard 4.

    Answers 'how often does this vendor publish changes, and what kind' over time.
    Draws from `vendor_change` alone.
    """
    changes = store.all_vendor_changes(vendor_id)
    by_kind: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    monthly: dict[str, dict] = {}

    for change in changes:
        by_kind[change.kind] += 1
        if change.severity:
            by_severity[change.severity] += 1
        period = change.detected_at.strftime("%Y-%m")
        bucket = monthly.setdefault(
            period, {"period": period, "count": 0, "by_kind": Counter()}
        )
        bucket["count"] += 1
        bucket["by_kind"][change.kind] += 1

    timeline = [
        {"period": p, "count": b["count"], "by_kind": dict(b["by_kind"])}
        for p, b in sorted(monthly.items())
    ]

    newest_at = max((c.detected_at for c in changes), default=None)
    oldest_at = min((c.detected_at for c in changes), default=None)

    return {
        "vendor_id": vendor_id,
        "total_changes": len(changes),
        "by_kind": dict(by_kind),
        "by_severity": dict(by_severity),
        "timeline": timeline,
        "newest_change_at": newest_at.isoformat() if newest_at else None,
        "oldest_change_at": oldest_at.isoformat() if oldest_at else None,
    }


def repository_graph(store: GraphStore, repo_id: str, *, limit: int | None = None) -> dict:
    """This repository's call sites and the vendors they reach: the graph the Overview draws.

    Owner decision 2 puts the dependency graph beside the fact tiles on the first screen, which
    makes it not optional. `DependencyCanvas` already draws one; what did not exist was a scoped
    read answering the whole graph at once. The console cannot know which operations to ask about
    before it has the graph naming them, so composing this from the per-operation route would be
    a round trip per node to draw one picture.

    **Every binding carries its rung, and here that rung is always `static`.** A call site is what
    the static index found; nothing about it rests on a resolution or a correlation step. A
    stronger rung for the same operation is a fact about this repository's telemetry and belongs
    to `observed_telemetry`, never blended into an edge drawn here.

    `last_indexed` is repeated from `index_coverage` rather than recomputed, and it is staleness
    rather than a promise of currency: a repository scanned three weeks ago reports the same value
    every day until another pass moves it. No age is derived, because a duration computed at
    response time goes wrong the moment the payload is cached and the timestamp it came from does
    not.

    **A bound is declared rather than applied quietly.** `total_bindings` counts what exists and
    `truncated` says whether the drawn set is all of it, so a console holding a partial graph can
    say so. A graph silently missing edges misreports a codebase's exposure, which is the one
    thing this picture is for.
    """
    coverage = index_coverage(store, repo_id)
    by_vendor = coverage["by_vendor"]
    last_indexed = coverage["last_indexed"]

    sites = store.call_sites_for_repository(repo_id, limit=limit)
    total = store.call_sites_for_repository_count(repo_id)

    bindings = [
        {
            "vendor_id": site.vendor_id,
            "operation_id": site.operation_id,
            "path": site.path,
            "line": site.line,
            "symbol": site.symbol,
            "rung": "static",
        }
        for site in sites
    ]

    vendors = [
        {
            "vendor_id": vendor_id,
            "indexed_call_sites": by_vendor[vendor_id],
            "last_indexed": last_indexed.get(vendor_id),
        }
        for vendor_id in sorted(by_vendor)
    ]

    return {
        "repo_id": repo_id,
        "vendors": vendors,
        "bindings": bindings,
        "total_bindings": total,
        "truncated": len(bindings) < total,
    }


def vendor_operation_exposure(
    store: GraphStore, vendor_id: str, *, repo_id: str | None = None
) -> dict:
    """Which of one vendor's operations this codebase calls, and on what evidence.

    Owner decision 29 makes this the vendor page's opening answer: *what does this vendor cost
    me*, before *what has this vendor done*. Exposure is call sites, so this counts call sites.

    **Every row carries its rung, and the rung is `static` rather than derived.** A call site is
    what the static index found -- `CLAUDE.md` requires the rung on every binding and on every
    artifact derived from one, and a row that could not name its rung would be a false positive
    nobody could attribute. A stronger rung for the same operation is a fact about telemetry and
    is reported beside it, never blended into it: `observed` is its own key, so a reader can see
    that the graph found four call sites *and* that traffic confirmed one of them, which is two
    facts rather than an average of two facts.

    **`observed` is three-valued and the third value is the point.** `True` and `False` are
    answers telemetry gave. `None` means nothing looked -- either no telemetry is attached to the
    repository, or the question was asked across every repository at once, where attachment
    differs per repository and no single answer exists. Collapsing `None` onto `False` would
    report "we checked and saw no traffic" for an operation nobody ever measured, which is the
    substitution this console exists to refuse (B157).

    No ratio and no score. Counts, and a rung, and a tri-state.
    """
    operations = store.call_sites_by_operation(vendor_id, repo_id=repo_id)

    # Telemetry attaches per repository, so a fleet-wide question has no single attachment to
    # report and every row's `observed` stays `None`.
    context = store.repo_context(repo_id) if repo_id is not None else None
    attached_at = context.telemetry_attached_at if context is not None else None

    observed_operations: set[str] | None = None
    if repo_id is not None and attached_at is not None:
        observed_operations = {
            operation
            for vendor, operation in store.observed_operation_pairs(repo_id)
            if vendor == vendor_id
        }

    return {
        "vendor_id": vendor_id,
        "repo_id": repo_id,
        "telemetry_attached_at": attached_at.isoformat() if attached_at is not None else None,
        "operations": [
            {
                "operation_id": row["operation_id"],
                "call_site_count": row["call_site_count"],
                "repository_count": row["repository_count"],
                "binding_rung": "static",
                "observed": (
                    None
                    if observed_operations is None
                    else row["operation_id"] in observed_operations
                ),
            }
            for row in operations
        ],
    }
