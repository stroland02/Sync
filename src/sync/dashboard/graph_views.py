"""View models for the graph itself: the binding surface, the observed rung, detector
accountability.

`sync.dashboard.queries` and `sync.dashboard.fleet` answer questions about one finding and about
every run, respectively. Neither renders the graph the findings come from -- the call sites, the
vendor changes, and the telemetry a binding rests on. This module does, reading `GraphStore`
alone and never `sync.remediate`, matching the convention both of those modules already keep:
every function returns primitives -- dicts, lists, strings, numbers -- never a live model, so a
page that received one could not lazily re-query or mutate it.

Three functions, three questions:

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

**What none of these may claim.** An observed call is evidence a call site was exercised. It is
not proof the binding is correct -- the correlation that produced it can itself be wrong, which
is exactly why `observed_call.binding_rung` exists as a column and not an assumption. Nothing
here promotes an observation to a verdict; that stays the reader's job, informed by the rung.
"""

from __future__ import annotations

from collections import Counter

from sync.graph.store import GraphStore


def binding_surface(
    store: GraphStore, vendor_id: str, operation_id: str, *, repo_id: str | None = None
) -> dict:
    """Every call site the index currently holds against one vendor operation, and what the
    vendor has changed about it.

    Reads `call_sites_for_operation` and `all_vendor_changes`, exactly as `GraphStore` already
    answers them -- no new store method, no SQL of its own. `repo_id` is optional and its
    absence means every repository, matching `call_sites_for_operation`'s own contract: an
    aggregate across customers is a real question and a detector is not what is asking it here.

    **Every call site row reports `binding_rung: "static"`, unconditionally.** A call site is
    what the static index found; nothing about the row rests on a resolution step or on watched
    traffic, so `static` is not a default standing in for an unknown value -- it is the only
    rung a row built from `call_site` alone can honestly carry. A stronger rung for the same
    binding would come from `observed_telemetry` on this same repository and vendor operation,
    as a second, separate kind of evidence, never as a replacement written here.

    An operation nobody calls, or one the vendor has never changed, returns empty lists rather
    than an error: "nothing recorded" is a true answer for either half of this payload.
    """
    sites = store.call_sites_for_operation(vendor_id, operation_id, repo_id=repo_id)
    changes = [
        change
        for change in store.all_vendor_changes(vendor_id)
        if change.operation_id == operation_id
    ]
    return {
        "vendor_id": vendor_id,
        "operation_id": operation_id,
        "repo_id": repo_id,
        "call_sites": [
            {
                "repo_id": site.repo_id,
                "path": site.path,
                "line": site.line,
                "col": site.col,
                "symbol": site.symbol,
                "sdk_version": site.sdk_version,
                "args_keys": list(site.args_keys),
                "response_fields_read": list(site.response_fields_read),
                "loop_depth": site.loop_depth,
                "binding_rung": "static",
                "indexed_at": site.indexed_at.isoformat(),
                "retracted_at": site.retracted_at.isoformat() if site.retracted_at else None,
            }
            for site in sites
        ],
        "changes": [
            {
                "change_id": change.id,
                "kind": change.kind,
                "severity": change.severity,
                "from_version": change.from_version,
                "to_version": change.to_version,
                "path_ptr": change.path_ptr,
                "detected_at": change.detected_at.isoformat(),
            }
            for change in changes
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


def observed_telemetry(store: GraphStore, repo_id: str) -> dict:
    """The telemetry rung of the graph for one repository: what traffic showed up, what shape it
    had, and how often it failed.

    Three reads, three tables, one repository:

    - `observed_calls` -- one row per unit of work's use of one operation. Every derived count
      on a row (`call_count`, `distinct_targets`, `repeated_calls`, `max_resend_count`,
      `error_count`) is read off the model's own properties rather than recomputed from `spans`
      here, so this view cannot disagree with `ObservedCall` about what its own data means.
    - `observed_shapes` -- **not** repository-scoped in the schema; a shape is a fact about what
      a vendor operation sends, independent of who calls it. So this joins in through the
      `(vendor_id, operation_id)` pairs this repository's own observed calls actually name,
      which is what makes "the baseline for what this repo's traffic looks like" answerable
      without inventing a `repo_id` column the table does not have. An uncorrelated call -- empty
      `operation_id`, rung `unresolved` -- names no pair and joins nothing.
    - `observed_error_windows` -- one row per operation's failure count over one window this
      repository's tracker was asked about. Reported as-is: `error_count` has no denominator in
      this table (`schema.sql`'s own grain note), and this view does not compute one.

    **What an observed call can and cannot say.** A row here is evidence that a call site was
    exercised -- proof the code path ran, at least once, against this vendor. It is not proof
    that the binding correlating it to an operation is correct: `binding_rung` on the row says
    which of those two claims this is, `observed` for a correlation that ran or `unresolved` for
    a request nothing could attribute. Neither is a verdict; the reader weighs the finding by it.
    """
    calls = store.observed_calls(repo_id)

    operation_pairs = sorted({
        (call.vendor_id, call.operation_id) for call in calls if call.operation_id
    })
    shapes = [
        shape
        for vendor_id, operation_id in operation_pairs
        for shape in store.observed_shapes(vendor_id, operation_id)
    ]

    windows = store.observed_error_windows(repo_id)

    return {
        "repo_id": repo_id,
        "calls": [
            {
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
            for call in calls
        ],
        "shapes": [
            {
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
            for shape in shapes
        ],
        "error_windows": [
            {
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
            for window in windows
        ],
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
