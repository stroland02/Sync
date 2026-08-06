"""View models for the graph itself: the binding surface, the observed rung, detector
accountability.

`sync.dashboard.queries` and `sync.dashboard.fleet` answer questions about one finding and about
every run, respectively. Neither renders the graph the findings come from -- the call sites, the
vendor changes, and the telemetry a binding rests on. This module does, reading `GraphStore`
alone and never `sync.remediate`, matching the convention both of those modules already keep:
every function returns primitives -- dicts, lists, strings, numbers -- never a live model, so a
page that received one could not lazily re-query or mutate it.

Six functions, six questions:

- `binding_surface` -- given a vendor operation, which call sites currently depend on it, and
  what has the vendor changed about it. The API Dependency Graph made visible.
- `index_coverage` -- for one repository, how many call sites the index holds per vendor and
  when it last indexed each one. What Sync actually knows about a codebase, and how current
  that knowledge is -- neither had an answer anywhere in the console before this.
- `observed_telemetry` -- for one repository, what traffic showed up, what shape it had, and how
  often it failed. The telemetry rung of the graph, which has no surface at all before this.
- `detector_accountability` -- across every open finding, which detector raised how many, at
  which rungs, with what claims. `CLAUDE.md` requires a false positive be attributable to a rung;
  this is what lets an operator see that per detector rather than per row.
- `severity_rollup` -- across every open finding, a count per severity and the true total, each
  its own SQL aggregate rather than two numbers read off one Python list.
- `overview_summary` -- the fleet screen's lead answer: open findings by vendor, and a total
  that is honest about whether it stopped counting early. `overview_summary`'s own docstring
  carries why this reads `GraphStore` directly rather than the frozen `GraphSurface`.

**What none of these may claim.** An observed call is evidence a call site was exercised. It is
not proof the binding is correct -- the correlation that produced it can itself be wrong, which
is exactly why `observed_call.binding_rung` exists as a column and not an assumption. Nothing
here promotes an observation to a verdict; that stays the reader's job, informed by the rung.
"""

from __future__ import annotations

from collections import Counter

from sync.graph.store import GraphStore
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
    else:
        sites = store.call_sites_for_operation(
            vendor_id, operation_id, repo_id=repo_id,
            limit=call_sites_limit, offset=call_sites_offset,
        )
        sites_total = store.call_sites_for_operation_count(vendor_id, operation_id, repo_id=repo_id)
        call_sites_page = _page([_call_site_row(s) for s in sites], sites_total, call_sites_offset)

    changes = store.vendor_changes_for_operation(
        vendor_id, operation_id, limit=changes_limit, offset=changes_offset
    )
    changes_total = store.vendor_changes_for_operation_count(vendor_id, operation_id)
    changes_page = _page([_change_row(c) for c in changes], changes_total, changes_offset)

    return {
        "vendor_id": vendor_id,
        "operation_id": operation_id,
        "repo_id": repo_id,
        "call_sites": call_sites_page,
        "changes": changes_page,
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

    return {
        "repo_id": repo_id,
        "calls": calls_page,
        "shapes": shapes_page,
        "error_windows": windows_page,
    }


def severity_rollup(store: GraphStore) -> dict:
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
    """
    return {"by_severity": store.open_findings_severity_counts(), "total": store.open_findings_count()}


# Ceiling on how many open findings `/api/overview`'s total counts before it stops looking and
# reports the bound instead of an exact number, mirroring Sentry's `MAX_HITS_LIMIT`
# (`paginator.py:26`): ten thousand matching rows cost the same as one thousand once the count is
# a real SQL `LIMIT` rather than a full scan, and a bounded count that says so is more honest than
# an exact one that took nineteen seconds of scanning to produce (section 24 of
# `2026-08-05-sync-console-architecture.md` carries the argument).
OPEN_FINDING_COUNT_BOUND = 1000


def overview_summary(store: GraphStore, *, bound: int = OPEN_FINDING_COUNT_BOUND) -> dict:
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
    """
    total, bound_reached = store.open_findings_count_bounded(bound)
    vendor_counts = store.open_findings_vendor_counts()
    summary = store.open_findings_summary()
    indexed_at = summary["indexed_at"]
    return {
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
    }


def detector_accountability(store: GraphStore) -> dict:
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
    """
    findings = store.open_findings()

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
    return {"detectors": detectors, "total_open_findings": len(findings)}
