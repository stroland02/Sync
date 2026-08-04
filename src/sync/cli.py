"""Local driver for a Sync run. The only entry point at M0."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import urlsplit

from langgraph.checkpoint.postgres import PostgresSaver

import yaml

from sync.benchmark.checkout import read_checkout
from sync.benchmark.report import render_report
from sync.benchmark.score import index_sources, materialise, score_change
from sync.core import CallSite, Finding, LanguageAdapter, RepoRef, VendorChange
from sync.core.protocols import RequestCorrelator
from sync.detect.efficiency import EfficiencyDetector
from sync.detect.observed_drift import DeclaredField, ObservedDriftDetector
from sync.detect.parameter_deprecation import LinkedDeprecation, ParameterDeprecationDetector
from sync.detect.status_rate import StatusRateDetector
from sync.detect.vendor_change import VendorChangeDetector
from sync.forge.github import GitHubForge
from sync.forge.webhook import (
    SIGNATURE_HEADER,
    WebhookFormatError,
    WebhookSignatureError,
    record_merge_outcome,
)
from sync.graph.store import GraphStore
from sync.index.literals import index_operation_literals
from sync.index.python_lang import PythonAdapter
from sync.index.typescript import TypeScriptAdapter
from sync.remediate.agent_patch import AgentRemediator
from sync.remediate.corpus import corpus_salt
from sync.remediate.graph import build_graph
from sync.remediate.literal_swap import LiteralSwapRemediator
from sync.remediate.parameters import ParameterOmitRemediator, ParameterRenameRemediator
from sync.remediate.property_omit import PropertyOmitRemediator
from sync.remediate.tiered import TerminalTier, TieredRemediator
from sync.route.matrix import catalogue_index
from sync.signals.deprecations import (
    DEPRECATION_SOURCES,
    DeprecationAdapter,
    ParameterDeprecation,
    http_fetch,
    model_deprecation_sources,
    parameter_deprecation_sources,
    parameters_to_vendor_changes,
    parse_parameter_deprecations,
)
from sync.signals.datadog.shapes import DatadogShapeReader
from sync.signals.feed import public_key_bytes, render_feed, sign_feed
from sync.signals.intake import (
    assess_repository,
    read_registry_apis,
    read_sdk_repositories,
)
from sync.signals.registry_tier.directory import parse_directory
from sync.signals.reachability import observed_call_counts, rank_reachability
from sync.signals.registry import (
    SYMBOL_MAP_FILENAME,
    VendorContext,
    available_vendors,
    load_vendor,
    prepare_vendor,
)
from sync.signals.sentry.errors import SentryErrorReader, UnreadableExport
from sync.signals.sentry.shapes import SentryShapeReader
from sync.telemetry import ingest_payload

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"

# Where the GitHub webhook secret is read from when no file is named. An environment
# variable rather than a setting with a default: a shared secret has no value this
# repository is allowed to know, so there is nothing to default to.
WEBHOOK_SECRET_ENV = "SYNC_WEBHOOK_SECRET"

# Where the feed signing key comes from when no file is named. The private half is never in
# this repository and never will be: `sync.core.keys` holds only the public bytes, and
# `tests/test_feed_cache.py` scans every tracked file to keep it that way.
FEED_SIGNING_KEY_ENV = "SYNC_FEED_SIGNING_KEY"

# How long a downloaded vendor page is reused. The same twelve hours `DeprecationAdapter` uses,
# for the same reason: these pages change on a human's schedule, and refetching two of them on
# every scan is how a run earns a rate limit and lands in the failure path below.
DEPRECATION_MAX_AGE = timedelta(hours=12)

# How deep a response schema is walked. Stripe's specification refers to itself -- a charge
# carries a refund carrying a charge -- so an unbounded walk does not return, and a run that
# hangs before the first detector starts is worse than one that describes fields shallowly. A
# field deeper than this is also one the observed baseline is least likely to carry, since the
# code that would have to read it stops long before.
MAX_SCHEMA_DEPTH = 4


def _select(findings: list[Finding], limit: int) -> list[Finding]:
    """`--limit 0` takes every finding; `--limit N` takes the first N.

    Pulled out of `run()` so the selection rule is reachable by a test that
    never touches Postgres, the network, or the Agent SDK.
    """
    return findings if limit == 0 else findings[:limit]


def load_catalogue() -> dict[str, dict]:
    """oasdiff's own checker catalogue, keyed by the rule id `VendorChange.kind` holds.

    Read from the pinned binary rather than kept as a copy here, which is what keeps routing
    honest across an oasdiff upgrade: the rule set grows and a stale local list would route
    new kinds silently. Loaded once per run and handed to both the cascade and the graph, so
    there is one table and not two that can drift apart.
    """
    from sync.signals.oasdiff import run_oasdiff_checks

    return catalogue_index(run_oasdiff_checks())


def build_remediator(catalogue: dict[str, dict] | None = None) -> TieredRemediator:
    """The tier cascade, cheapest first, with the agent last and unconditional.

    Pulled out of `run()` for the same reason `_select` is: the ordering is the whole
    economic claim and it should be checkable without Postgres, the network, or the Agent
    SDK. Until this existed nothing in `src/` constructed a `TieredRemediator` at all --
    `sync.route.matrix` classified changes and `TieredRemediator` composed tiers, and
    neither ran, because `build_graph` was handed a bare `AgentRemediator`.

    The agent is wrapped rather than listed. `nodes.make_patch` calls `propose()` directly
    and has never consulted `can_handle`, so the agent handles every finding today
    whatever its severity; a cascade that gated the last tier would make that dormant
    check live and narrow what the pipeline repairs, as a side effect of a change made for
    another reason entirely.

    The deprecation signal's three codemods lead, grouped: `LiteralSwapRemediator` repairs a
    retired model and the two parameter tiers repair a deprecated argument, which is the same
    vendor page answered in the two shapes vendors publish guidance in. Then the oasdiff
    codemod, then the agent.

    Position matters in one direction only and absolutely. Each codemod's `can_handle` keys on
    a different `change.kind`, so no two ever contend and the order among them is grouping
    rather than precedence -- but `TerminalTier` answers `can_handle` with `True` for
    everything, so a remediator placed after it is never reached however correct it is. Both
    parameter tiers were missing from this list entirely, which sent every parameter
    deprecation to a model call over a change a codemod resolves deterministically.
    """
    return TieredRemediator(
        [
            LiteralSwapRemediator(),
            ParameterOmitRemediator(),
            ParameterRenameRemediator(),
            PropertyOmitRemediator(),
            TerminalTier(AgentRemediator()),
        ],
        catalogue=catalogue,
    )


# Every language adapter a repository is offered to, in the order it is offered. A table
# rather than a branch, for the reason `sync.signals.registry` exists: a chain on a file
# extension here would be language knowledge living in the entry point, which is the shape
# that made a second vendor adapter unreachable until the registry replaced it. Each adapter
# answers `matches` from the repository's own manifest, so this module decides nothing about
# any language -- it only asks, in order.
#
# TypeScript leads, and the order is load-bearing for exactly one case: a repository declaring
# the SDK in both languages resolves to TypeScript, which is what every run did before Python
# existed. Changing that would move repositories from a language Sync can verify to one it
# cannot, silently.
#
# Registering a third is a line here, the same readable diff `_BUILDERS` takes. Discovery is
# deliberately absent until an adapter ships from outside this repository.
def language_adapters() -> tuple[Callable[..., Any], ...]:
    """The table, resolved on every call rather than bound at import.

    A module-level tuple would capture the class objects when this module is imported, which is
    the hazard `_parameter_deprecations` already records for its fetch default: a test replacing
    `cli.TypeScriptAdapter` replaced something the tuple had already captured, and every run
    that believed it had stubbed the indexer was resolving the real one. Ten tests said so.
    """
    return (TypeScriptAdapter, PythonAdapter)


def _decline_line(adapter: Any, repo: RepoRef) -> str:
    """One indexer's account of why it did not claim the repository.

    `decline_reason` is optional the way `unverifiable_reason` is: `LanguageAdapter` is a
    protocol this module does not own, so a third party's adapter that has never heard of it goes
    on working and is listed as having explained nothing -- which is a fact about that adapter,
    and more useful in the message than a blank.

    Nothing here is allowed to raise, which is the whole reason it is a function. It runs while
    the run is already stopping and it is where every indexer's account is assembled, so one
    adapter's failure would trade all of them for a traceback about the refusal rather than the
    refusal -- and an adapter from outside this deployment is a boundary, not internal code. So a
    missing `language_id`, a missing explanation and a failing one all resolve to something
    printable that names the adapter.
    """
    language = str(getattr(adapter, "language_id", type(adapter).__name__))
    explain = getattr(adapter, "decline_reason", None)
    if explain is None:
        return f"  {language}: declined without saying why"
    try:
        return f"  {language}: {explain(repo)}"
    except Exception as exc:
        return f"  {language}: declined and could not say why ({exc!r})"


def select_language_adapter(repo: RepoRef, vendor_adapter: Any) -> Any:
    """The `LanguageAdapter` for this repository, or a refusal each indexer explains its part of.

    `matches` is the whole of the decision and it belongs to each adapter: TypeScript reads
    `package.json`, Python reads `pyproject.toml` and `requirements.txt`, and neither fact is
    one this module should hold. `decline_reason` follows the decision rather than leading it,
    for the same reason -- the file names are in the account because the adapter that read them
    wrote it.

    An unmatched repository raises rather than defaulting, which is the registry's rule and for
    its reason. A silent fallback would index a Python project with a TypeScript indexer, find
    nothing, and report a clean scan -- a run that appears to work and establishes nothing.

    What it raises *with* is the part that was wrong. Four situations reach this line as one
    `False` per indexer -- a vendor declaring no package, a manifest that could not be read, no
    manifest at all, and a manifest that was read and does not name the package -- and the
    refusal said the repository declares no SDK for all four. For the first that is false twice
    over: the repository may declare the SDK, and the absent configuration is this deployment's.
    `sync.signals.intake` already answers the neighbouring question one reason per dependency,
    including a channel for a manifest that would not parse, and this is that discipline applied
    where a run actually stops.
    """
    declined: list[str] = []
    for build in language_adapters():
        adapter = build(vendor_adapter=vendor_adapter)
        if adapter.matches(repo):
            return adapter
        declined.append(_decline_line(adapter, repo))

    vendor_id = getattr(vendor_adapter, "vendor_id", "unnamed")
    raise LookupError(
        f"no indexer claims {repo.url} for vendor '{vendor_id}':\n" + "\n".join(declined)
    )


_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_PORT = re.compile(r":\d+/")


def _repo_id(url: str) -> str:
    """A repository's identity, derived from its remote rather than its checkout.

    Call site ids hash `repo_id`, so this value decides whether two customers
    whose `src/billing.ts` both call `stripe.charges.create` occupy one row or
    two. Every spelling of one remote has to reduce to one string: scheme,
    trailing `.git`, scp-style `git@host:owner/name`, a port, an embedded
    credential. The credential in particular must not survive, because the
    result is written to every `call_site` row and hashed into the branch name
    the forge pushes.

    Path case is preserved. GitHub is case-insensitive there, but not every
    host is, and splitting one repository in two is a cheaper mistake than
    merging two distinct ones.
    """
    remote = _SCHEME.sub("", url.strip().rstrip("/"))
    userinfo, at, rest = remote.partition("@")
    if at and "/" not in userinfo:
        remote = rest
    remote = _PORT.sub("/", remote, count=1)
    remote = remote.replace(":", "/", 1)
    host, _, path = remote.removesuffix(".git").partition("/")
    return f"{host.lower()}/{path}"


def _clone(url: str, dest: Path) -> RepoRef:
    subprocess.run(["git", "clone", "--depth", "50", url, str(dest)], check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest,
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.strip()
    return RepoRef(repo_id=_repo_id(url), url=url, local_path=str(dest), head_sha=head)


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True,
        capture_output=True, text=True, encoding="utf-8",
    )


def _reset_clone(repo: RepoRef) -> None:
    """Return the clone to the commit it was cloned at.

    One clone serves every finding, and `push_branch` leaves HEAD on the branch
    it pushed with the patch committed. Without this the next finding's agent
    starts from the previous finding's tip: its branch carries that commit as a
    parent, its pull request shows both diffs, and its CI verifies a combination
    neither finding proposed. An abandoned finding is worse -- its edits are
    still in the tree, uncommitted, and `push_branch` stages with `git add -u`,
    so they land in the next finding's commit under a message describing
    something else.

    `git clean` runs without `-x`, so ignored files survive. `node_modules` is
    what `prepare` spent tens of seconds installing, and reinstalling it per
    finding would cost more than the clone this protects.
    """
    path = Path(repo.local_path)
    _git(["checkout", "-f", repo.head_sha], path)
    _git(["clean", "-fd"], path)


def _checkout_branch(repo: RepoRef, branch: str) -> None:
    """Put the clone on a branch some earlier process pushed.

    A resumed run's checkpoint describes a working copy that died with its
    temporary directory. `await_ci` reads HEAD out of the clone to match CI runs
    against the commit it pushed, so a fresh clone left on the default branch
    polls for the wrong sha and reports no CI run until it times out.
    """
    path = Path(repo.local_path)
    # The refspec is explicit because `git fetch origin <branch>` leaves only
    # FETCH_HEAD behind, and a resumed run that pushes again needs the
    # remote-tracking ref that `--force-with-lease` compares against.
    _git(["fetch", "origin", f"+{branch}:refs/remotes/origin/{branch}"], path)
    _git(["checkout", "-f", "-B", branch, f"origin/{branch}"], path)


# Nodes whose inputs outlive the process that produced them: what they need is
# in the pushed branch. A run interrupted before `push_branch` left its patch in
# a temporary directory that is now gone, so resuming it would typecheck a tree
# holding none of the work and then commit an empty index. Those start over.
RESUMABLE_NODES = frozenset({"await_ci", "open_pr"})


def _thread_to_invoke(graph, base: str) -> tuple[str, bool]:
    """Pick the checkpoint thread for one finding, and say whether to resume it.

    Two different situations otherwise share one thread id. A run that died
    mid-flight -- the worker restarted during the CI wait -- has to resume:
    re-entering it with input instead replays every node from the start, which
    here means a second agent run and a second pushed branch. A run that
    *finished* must not be re-entered at all: `finding.id` is a stable hash and
    `head_sha` is unchanged on a re-run against the same commit, so the operator
    who fixes a broken environment and runs again presents byte-identical
    coordinates, and that finished run's state -- `patch`, `verify_ok`,
    `static_fatal`, all of them read by routing functions -- would be merged
    into the new run as though it had produced them.

    The generation suffix separates the two: finished generations are stepped
    over, and the first unused or unfinished one is invoked. `snapshot.next`
    holds the tasks LangGraph still owes on a thread, so it distinguishes an
    interrupted run from a finished one; `created_at` distinguishes a thread
    that has never run from either.
    """
    generation = 0
    while True:
        thread_id = f"{base}:{generation}"
        snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
        if snapshot.created_at is None:
            return thread_id, False
        if snapshot.next and set(snapshot.next) <= RESUMABLE_NODES:
            return thread_id, True
        generation += 1


def _resolve(schema: Any, schemas: dict) -> dict | None:
    """A schema with its `$ref` followed, or `None` where there is nothing to follow it to.

    Termination is `MAX_SCHEMA_DEPTH`'s job, not this function's. Tracking which references have
    already been seen on the branch would terminate too, and would also prune `/child/name` on a
    self-referential schema -- a field the vendor really does return. One bound that costs depth
    beats two where the second quietly costs reach.
    """
    if not isinstance(schema, dict):
        return None
    reference = schema.get("$ref")
    if not isinstance(reference, str):
        return schema
    name = reference.rsplit("/", 1)[-1]
    if name not in schemas:
        return None
    return _resolve(schemas[name], schemas)


def _json_types(schema: dict) -> frozenset[str]:
    """The JSON types a schema permits, in the vocabulary `ObservedShape` records.

    `integer` collapses to `number` because JSON has one numeric type and the observation side
    cannot tell them apart -- keeping the distinction would report every integer field as
    drifting on its first observation.
    """
    declared = schema.get("type")
    names = declared if isinstance(declared, list) else [declared]
    mapped = {
        "number" if name == "integer" else name
        for name in names
        if isinstance(name, str) and name != "null"
    }
    return frozenset(mapped)


def _nullable(schema: dict) -> bool:
    """Both spellings. OpenAPI 3.0 writes `nullable: true`; 3.1 puts `null` in the type list."""
    declared = schema.get("type")
    if isinstance(declared, list) and "null" in declared:
        return True
    return schema.get("nullable") is True


def _walk_schema(schema: dict, schemas: dict, prefix: str, depth: int) -> Iterator[DeclaredField]:
    if depth >= MAX_SCHEMA_DEPTH:
        return
    required = set(schema.get("required") or [])
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return

    for name, child in properties.items():
        resolved = _resolve(child, schemas)
        if resolved is None:
            continue
        field_path = f"{prefix}/{name}"
        yield DeclaredField(
            field_path=field_path,
            json_types=_json_types(resolved),
            required=name in required,
            nullable=_nullable(resolved),
        )
        yield from _walk_schema(resolved, schemas, field_path, depth + 1)


def _declared_response_fields(document: dict) -> dict[str, list[DeclaredField]]:
    """What the published specification says each operation's response contains.

    `ObservedDriftDetector` compares the observed baseline against this, and nothing in the
    repository turned a specification into declared fields -- the detector shipped able to run
    and with no way to be given its own input.

    An operation describing no JSON response body is omitted rather than recorded as declaring
    nothing. An empty declaration would report every observed field as undeclared, which is the
    detector's loudest finding raised from an absence of information.
    """
    schemas = (document.get("components") or {}).get("schemas") or {}
    declared: dict[str, list[DeclaredField]] = {}

    for methods in (document.get("paths") or {}).values():
        if not isinstance(methods, dict):
            continue
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                continue

            body = (
                ((operation.get("responses") or {}).get("200") or {}).get("content") or {}
            ).get("application/json") or {}
            root = _resolve(body.get("schema"), schemas)
            if root is None:
                continue

            fields = list(_walk_schema(root, schemas, "", 0))
            if fields:
                declared[operation_id] = fields

    return declared


def _declared_fields(documents: Sequence[dict]) -> dict[str, list[DeclaredField]]:
    """The declared response fields across every document a vendor published.

    One vendor publishes one specification and another publishes one per product, and the drift
    detector asks a question about the vendor rather than about a document. The merge is on
    `operation_id` because that, with the vendor, is what the graph and the detector both key
    on.

    **An operation two documents both declare is dropped rather than resolved.** Nothing Twilio
    publishes promises its ids are unique across 61 products -- the adapter records the source
    document in `raw` for exactly that reason -- and a plain merge settles the clash in favour
    of whichever was read last. The cost of settling it is not a wrong number: the detector
    would compare one product's observed traffic against the other product's declarations, and
    report every field the observed product really does return as one the vendor never
    declared. That is a confident false finding in the detector whose entire justification is
    precision over recall.

    Dropping costs findings for that operation instead, because `ObservedDriftDetector.scan`
    iterates the declared map and never examines an operation absent from it. A missed finding
    costs one incident; a false one costs the reviewer's willingness to read the next.

    It is printed, never silent. An operation that quietly stops being checked is
    indistinguishable from a detector finding nothing, which is the confusion the per-detector
    counts in `_scan` exist to end.
    """
    declared: dict[str, list[DeclaredField]] = {}
    collided: set[str] = set()

    for document in documents:
        for operation_id, fields in _declared_response_fields(document).items():
            if operation_id in declared or operation_id in collided:
                collided.add(operation_id)
                declared.pop(operation_id, None)
                continue
            declared[operation_id] = fields

    if collided:
        print(
            "observed-drift: "
            f"{', '.join(sorted(collided))} declared by more than one document; "
            "dropped rather than compared against the wrong product's declarations",
            file=sys.stderr,
        )
    return declared


def _page(url: str, destination: Path, fetch: Callable[[str], str]) -> str:
    """A vendor page, from cache when it is recent enough and from the network otherwise."""
    if destination.exists() and destination.stat().st_size > 0:
        stamp = datetime.fromtimestamp(destination.stat().st_mtime, tz=timezone.utc)
        if max(datetime.now(timezone.utc) - stamp, timedelta(0)) < DEPRECATION_MAX_AGE:
            return destination.read_text(encoding="utf-8")

    body = fetch(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(body, encoding="utf-8")
    return body


def _parameter_deprecations(
    cache_dir: Path, fetch: Callable[[str], str] | None = None
) -> list[ParameterDeprecation]:
    """Deprecated request parameters from every vendor that publishes a table of them, skipping
    any vendor that cannot be reached.

    `DeprecationAdapter` raises when a page cannot be retrieved, and is right to: for the model
    signal an empty answer is indistinguishable from a healthy vendor with nothing deprecated.
    The caller here is a scan that runs two other detectors, so the same failure must cost this
    detector's findings and nothing else. It is printed rather than swallowed, because a silent
    zero is exactly the confusion this wiring exists to end.

    The fetch is injected so a test needs no network, and it resolves to the module's own
    `http_fetch` at call time rather than in the signature's default. A default binds the
    function object when this module is imported, so a test replacing `cli.http_fetch` replaced
    something this call had already captured -- and every `run()` test that believed it had
    stubbed the network was downloading both vendor pages for real.
    """
    fetch = fetch or http_fetch
    deprecations: list[ParameterDeprecation] = []

    # Only the sources that publish a parameter table. Parsing a page without one returns
    # nothing rather than raising, so what the filter prevents is not a bad row: it is the
    # failure message above claiming this detector lost findings for a vendor that publishes
    # none, which is the silent-zero confusion the whole signal exists to end.
    for source in parameter_deprecation_sources():
        destination = cache_dir / f"{source.vendor_id}-deprecations.md"
        try:
            body = _page(source.url, destination, fetch)
        except Exception as exc:
            print(
                f"parameter-deprecation: {source.vendor_id} page unavailable "
                f"({type(exc).__name__}: {exc})",
                file=sys.stderr,
            )
            continue
        deprecations.extend(parse_parameter_deprecations(source.vendor_id, body))

    return deprecations


def _parameter_changes(
    rows: Sequence[ParameterDeprecation], today: date
) -> list[tuple[ParameterDeprecation, VendorChange]]:
    """Parameter deprecations paired with the `VendorChange` each one became.

    Pairs rather than a list, because the detector has to name the change its finding came
    from and `make_locate` abandons a run whose finding names none. The correspondence is
    established here, at the one point both ends exist at once.

    Each row is converted **alone**, which is what makes that a fact rather than an inference.
    Zipping the input against a batch conversion would hold today and rest on an ordering
    nothing states, and the failure mode of a wrong assumption here is not a missing finding --
    it is a rename remedy applied to the parameter that wanted an omission.

    `parameters_to_vendor_changes` was finished, tested, and called by nothing, so the remedy
    and the vendor's own wording never reached a remediator that keys on
    `kind == "deprecation/parameter"`. This is that call site.

    The version range is the honest part. A deprecation happens on a date and not across a
    release, so there is no range to record -- and borrowing the run's Stripe window would file
    an Anthropic parameter under `v2320..v2330`, a provenance the row does not have. Both ends
    carry the date the vendor's page was read instead: equal because there is no span, and a
    date because that is the only coordinate this artifact actually has.

    `today` is passed rather than read here, so two halves of one scan cannot disagree about
    what day it is and a test is not a fact about when the suite ran.
    """
    stamp = today.isoformat()
    paired: list[tuple[ParameterDeprecation, VendorChange]] = []

    for row in rows:
        produced = parameters_to_vendor_changes([row], from_version=stamp, to_version=stamp)
        if len(produced) != 1:
            # Cannot happen against today's converter, which emits one row per input. Written
            # as a drop rather than an assertion because the alternative to dropping is
            # guessing which of several rows this deprecation became, and a wrong guess names
            # the wrong change.
            print(
                f"parameter-deprecation: {row.vendor_id} `{row.parameter}` produced "
                f"{len(produced)} vendor change(s); dropped rather than joined to a guess",
                file=sys.stderr,
            )
            continue
        paired.append((row, produced[0]))

    return paired


def _model_deprecations(
    cache_dir: Path,
    from_version: str,
    to_version: str,
    fetch: Callable[[str], str] | None = None,
    today: date | None = None,
) -> list[VendorChange]:
    """Retired models as `VendorChange` rows, from every vendor that publishes them, skipping a
    vendor that is unreachable.

    `DeprecationAdapter` was finished, tested, and constructed nowhere in `src/`, so no
    `ModelDeprecation` ever became a `VendorChange` and `LiteralSwapRemediator` sat in the
    cascade with nothing to act on. This is that call site.

    The cache path is the one `_page` writes for the parameter half, deliberately: where a vendor
    publishes both tables the two halves read one page, and the adapter's own freshness window is
    the same twelve hours. `_parameter_deprecations` runs first and leaves that page there, so the
    adapter finds it fresh and the run downloads such a vendor once rather than twice. A vendor
    publishing only retirements is fetched here and nowhere else, which is the same one download.
    The sharing is the file rather than a variable because the adapter fetches for itself and its
    signature is not this module's to change.

    The version range is Stripe's and means nothing to a model retirement -- a model dies on the
    vendor's calendar, not across an API version boundary. It is carried because `fetch_changes`
    is the `VendorAdapter` protocol and every `VendorChange` records the window it was found in.

    One vendor failing costs that vendor's changes and no more, and is printed rather than
    swallowed. The adapter is right to raise on an unparseable page: an empty answer is
    indistinguishable from a healthy vendor with nothing deprecated. The scan around it runs
    other detectors, so it is here that the failure stops being fatal.

    `fetch` resolves at call time for the reason `_parameter_deprecations` records: a signature
    default captures the function object at import and is unreachable by a test that replaces
    the module's.
    """
    fetch = fetch or http_fetch
    changes: list[VendorChange] = []

    for source in model_deprecation_sources():
        adapter = DeprecationAdapter(
            source,
            fetch=fetch,
            cache_path=cache_dir / f"{source.vendor_id}-deprecations.md",
            max_age=DEPRECATION_MAX_AGE,
            # Injected rather than left to the adapter's own clock, so one scan measures every
            # vendor's urgency from one day and a test asserting a number stays true next year.
            today=today,
        )
        try:
            changes.extend(adapter.fetch_changes(from_version, to_version))
        except Exception as exc:
            print(
                f"model-deprecation: {source.vendor_id} unavailable "
                f"({type(exc).__name__}: {exc})",
                file=sys.stderr,
            )

    return changes


def _literal_call_sites(repo: RepoRef) -> tuple[list[CallSite], list[str]]:
    """Call sites for the model ids named as string literals, and the paths it could not read.

    `typescript.py` finds SDK member chains, which is the right shape for `stripe.charges.create`
    and the wrong one for a model id: no member chain leads to a string in an options object.
    `index.literals` exists for that and nothing called it, so the parameter-deprecation detector
    had no rows to match against however many deprecations it was handed.

    The prefixes come from each vendor's own `DeprecationSource`, keeping vendor naming out of
    the index stage. `sdk_version` is unknown here and says so -- a model literal is named by the
    customer's code, not by a package the manifest pins.

    **Every source, unfiltered.** This is the one deprecation call site that asks nothing about
    which table a vendor publishes: it indexes model ids in the customer's own code, and a
    finding of either kind needs a call site to attach to. Narrowing it to one signal's sources
    would leave the other signal's findings pointing at nothing.

    What leniency cost here went beyond the literal: the row's content hash was taken over a
    line the file does not contain, and its sibling argument keys were whatever the
    substitution made of them -- which `ParameterDeprecationDetector` then joins on.

    **A file that does not decode is skipped and named, not decoded leniently.** This read used
    `errors="replace"`, which `sync.benchmark.checkout.read_checkout`,
    `sync.signals.generated.symbols_speakeasy._text` and both manifest readers each refuse by
    name -- and here it was worse than in any of them, because `operation_id` *is* the literal's
    value and it is the key a retirement joins on. Two measured outcomes: an accented byte inside
    a matched literal recorded `claude-3-caf\\ufffd`, a model no vendor retires and no code names;
    and `.ts` is MPEG transport stream as well as TypeScript, so a video file in the tree parsed
    into a phantom `anthropic` call site. Neither value is inert either -- U+FFFD in an
    `operation_id` raises `UnicodeEncodeError` in anything that later writes it to a cp1252
    stream, far from the file it came from.

    What that costs is real and is the trade `read_checkout` already argued: a valid `.ts` file in
    a legacy encoding holds model literals this no longer indexes, where leniency did recover
    them. Telling such a file from a binary cheaply is not possible, so the paths are named -- a
    reader who sees `src/legacy.ts` knows to look, and silently recovering some of its literals
    out of mojibake told them nothing at all.

    **Those paths are returned rather than printed, so the run can count them.** The reason is
    the one `sync.benchmark.score` states about `skipped_files`: whoever read the tree knows what
    it could not read, and nothing further down can recover it. A warning printed per file said a
    file was missed without ever saying how much was, which is not a coverage figure -- and a run
    that cannot state its coverage reports the same `0 finding(s)` over a repository it read and
    one it mostly could not.
    """
    root = Path(repo.local_path)
    sites: list[CallSite] = []
    unread: list[str] = []

    for file_path in root.rglob("*.ts"):
        if "node_modules" in file_path.parts or file_path.name.endswith(".d.ts"):
            continue
        relative = file_path.relative_to(root).as_posix()
        try:
            source = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Returned rather than printed here, and counted by the caller. One unreadable file
            # must not empty the index -- the property `index_operation_literals` already keeps
            # for a file that does not parse -- and a per-file warning is not a coverage figure:
            # it says a file was missed without ever saying how much was.
            unread.append(relative)
            continue
        for vendor in DEPRECATION_SOURCES:
            sites.extend(
                index_operation_literals(
                    source, path=relative, repo_id=repo.repo_id, vendor_id=vendor.vendor_id,
                    sdk_version="unknown", prefixes=vendor.prefixes,
                )
            )

    return sites, unread


def _adapter_unread(adapter: LanguageAdapter, repo: RepoRef) -> list[str]:
    """The source paths the language indexer skipped, or nothing if it does not report.

    `getattr` rather than a protocol member, for the reason `unverifiable_reason` and
    `sdk_bindings` are read that way: `LanguageAdapter` is a boundary this module does not own,
    and a third party's adapter that reports nothing has to scan rather than crash. Both shipped
    adapters report, so the fallback is for an adapter this repository has not seen.

    Both of them skip a source file that is not UTF-8 and log it, and until now nothing in `src/`
    read the record -- so a run's coverage figure described the literal pass, which walks `*.ts`,
    and presented itself as the whole answer while the pass that walks every source file said
    nothing.
    """
    report = getattr(adapter, "unread_paths", None)
    return list(report(repo)) if report is not None else []


def _coverage_lines(unread: Sequence[str]) -> list[str]:
    """What a run could not read, or nothing at all when it read everything.

    Nothing at all rather than a zero, which is `sync.benchmark.report._skipped_block`'s reasoning
    and holds here for the same reason: a heading that prints on every run is a heading the next
    reader learns to skip, and this one matters exactly when it appears.

    Worded to echo that block deliberately, and duplicated rather than shared. `sync.benchmark` is
    a harness and this is the run path; importing the harness to phrase a run's report would put
    the benchmark on the pipeline's import graph to save six lines. The two saying the same thing
    is the property worth having, and the wording is what carries it.
    """
    if not unread:
        return []
    return [
        f"{len(unread)} path(s) could not be read as source and were not indexed",
        "  A binary is nothing an indexer wanted; a source file in a legacy encoding is a call",
        "  site this run does not cover. Telling the two apart cheaply is not possible.",
        *[f"  {path}" for path in unread],
    ]


def _detector_suite(
    store: GraphStore,
    *,
    spec_documents: Sequence[dict],
    call_sites: Sequence[CallSite],
    deprecations: Sequence[LinkedDeprecation],
    vendor_id: str,
    repo_id: str,
    deprecation_vendors: Sequence[str] = (),
) -> list[tuple[str, object]]:
    """Every detector a scan runs, named, in the order it runs them.

    This list is the difference between a detector existing and a detector running. Three
    satisfied the protocol and exactly one was ever constructed; the other two were finished,
    tested work that could not produce a single finding, which is the same as not having built
    them. `scripts/lint_dead_links.py` is what now catches that case, and it caught `efficiency`
    before this line existed.

    `VendorChangeDetector` is scoped to one vendor, so a retired Anthropic model upserted into
    the graph is invisible to the Stripe instance however correctly it was written. One detector
    per deprecation vendor is what turns those rows into findings; without them the model half
    of the deprecation signal would look wired and produce nothing, which is the failure this
    whole assembly exists to make impossible to ship again.

    Assembled here rather than inline in `run()` so the set is checkable without Postgres, the
    network or the Agent SDK -- the same reason `_select` and `build_remediator` were pulled out.

    `efficiency` runs last because it is the only one that answers a question about cost rather
    than about breakage, and a scan's first output should be what is about to break.
    """
    # Every detector that reads call sites out of the graph is given the repository being scanned.
    # Two of them already took `repo_id` for their telemetry and asked for call sites without it,
    # which crossed one customer's spans against another's code; the graph could not hold two
    # repositories at all until `replace_call_sites` replaced the whole-database truncate, and now
    # that it can, an unscoped detector is a pull request opened against the wrong repository.
    return [
        ("vendor_change", VendorChangeDetector(store, repo_id=repo_id)),
        ("parameter-deprecation", ParameterDeprecationDetector(deprecations, call_sites)),
        # Several documents rather than one: a vendor that publishes per product declares its
        # response fields across all of them, and taking only the first would report every field
        # in every other product as undeclared -- the detector's loudest finding, raised from
        # this file having read less than the vendor published.
        ("observed-drift", ObservedDriftDetector(
            store, _declared_fields(spec_documents), vendor_id, repo_id=repo_id
        )),
        *[
            (
                f"model-deprecation:{vendor}",
                VendorChangeDetector(store, vendor_id=vendor, repo_id=repo_id),
            )
            for vendor in deprecation_vendors
        ],
        ("status-rate", StatusRateDetector(store, repo_id=repo_id, vendor_id=vendor_id)),
        ("efficiency", EfficiencyDetector(store, repo_id=repo_id, vendor_id=vendor_id)),
    ]


def _scan(detectors: Sequence[tuple[str, object]], store: GraphStore) -> list[Finding]:
    """Run every detector, persist what they found, and say what each one produced.

    One detector failing must not cost the others. A vendor page that cannot be fetched or a
    baseline that is not there loses that detector's findings, and losing the whole run because
    one input was missing is the worse trade.

    The count is printed per detector, including zero. A detector that silently produces nothing
    forever is indistinguishable from one that is broken, and that confusion is what this exists
    to end -- so a failure prints too, rather than being reported as a quiet zero.

    A detector carrying a `declined` channel gets its count printed beside the findings, and a
    detector without one is not reported as having declined nothing. Zero would be a claim it
    never made, and the distinction is the same one `report.unreadable` draws below.

    Every finding is inserted here, through the one path. Two detectors writing findings two ways
    is how they end up with two notions of what a finding is, and the architecture rests on one
    `Finding` type reaching one remediation pipeline.
    """
    findings: list[Finding] = []

    for name, detector in detectors:
        try:
            produced = list(detector.scan())
        except Exception as exc:
            print(f"{name}: unavailable ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue

        for finding in produced:
            finding.id = store.insert_finding(finding)
        findings.extend(produced)
        declined = getattr(detector, "declined", None)
        note = f", {len(declined)} declined" if declined is not None else ""
        print(f"{name}: {len(produced)} finding(s){note}")

    return findings


def run(args: argparse.Namespace, today: date | None = None) -> int:
    # The one clock read in the deprecation signal, taken here because this is the entry point
    # and a scan should measure every vendor's deadlines from one day. Injectable so a test
    # asserting a number of days stays true next year rather than being deleted.
    today = today or date.today()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    # Which adapter serves `--vendor` is the registry's answer, not a name written here. Staging
    # is the same call, because what a vendor needs downloaded and derived before a scan differs
    # per vendor -- one specification at a git tag for one of them, a directory of them for
    # another -- and every one of those shapes is knowledge this file is not allowed to hold.
    prepared = prepare_vendor(args.vendor, VendorContext(
        cache_dir=cache, from_version=args.from_version, to_version=args.to_version,
    ))
    vendor = prepared.adapter

    store = GraphStore(args.dsn)
    store.apply_schema()

    with tempfile.TemporaryDirectory() as workdir:
        repo = _clone(args.repo, Path(workdir) / "repo")

        try:
            # Selection is now data at the index stage as well as the signal stage: the
            # repository's own manifest decides, through each adapter's `matches`, and this
            # module names no language.
            adapter = select_language_adapter(repo, vendor)
        except LookupError as exc:
            print(str(exc), file=sys.stderr)
            return 2

        # One transaction for the whole ingest. It holds an ACCESS EXCLUSIVE
        # lock on the graph tables from the TRUNCATE until it commits, so any
        # concurrent reader blocks for the length of the ingest rather than
        # reading the previous graph. That is acceptable only because M0 runs
        # one scan at a time; the alternative is worse, since a run that dies
        # part-way through would otherwise leave a graph that is neither the old
        # one nor the new one, and the detector cannot tell a missing row from
        # an absent call site.
        #
        # A stale row from a previous invocation is indistinguishable from a real
        # finding to the detector, so everything a scan re-derives is cleared
        # first. `call_site` is the exception and is now converged per repository
        # instead: position is part of a call site's identity, so one blank line
        # inserted above a call used to leave the old row behind forever with its
        # finding attached, and the only thing that had ever cleared those was a
        # truncate of the whole database -- which erases every other repository's
        # rows, exactly what a hosted control plane must never do.
        #
        # Converged by retraction rather than by deletion, which is not a detail:
        # `finding.call_site_id` cascades, so deleting the stale row deletes what
        # the previous scan concluded about it. `replace_call_sites` carries the
        # argument and `open_findings` is what keeps a retracted site out of the
        # remediation path.
        # Finding ids are stable hashes of (detector, call_site_id, vendor_change_id),
        # so a re-inserted finding gets the same id its checkpoint thread already
        # used -- checkpoint coordinates survive the truncate.
        #
        # What is still truncated wholesale, and is still cross-repository:
        # `finding` and `vendor_change` are re-derived every scan, and the observed
        # tables are cleared by a scan that did not produce them. Narrowing those is
        # a decision per table with its own grain argument and is not made here.
        # Fetched before the transaction opens. The ingest holds an ACCESS EXCLUSIVE lock on the
        # graph tables, and two vendor pages behind a slow network would hold it for the length
        # of the download rather than the length of the write.
        deprecations = _parameter_deprecations(cache)
        parameter_changes = _parameter_changes(deprecations, today)
        # After the parameter half, which leaves each vendor's page in the cache the adapter
        # reads: one download per vendor serves both halves of the signal.
        model_deprecations = _model_deprecations(
            cache, args.from_version, args.to_version, today=today
        )

        with store.transaction():
            store.truncate_all(keep=("call_site",))

            # Kept as well as stored: `ParameterDeprecationDetector` takes call sites directly,
            # and the store answers `call_sites_for_operation` rather than "all of them". The id
            # comes back from the write, and a finding addresses its call site by id.
            #
            # One call rather than a loop, because the retraction is half of it:
            # `replace_call_sites` converges this repository on the revision just indexed and stops
            # asserting the positions it no longer has. A loop of upserts cannot, and left a ghost
            # per call site that moved.
            literal_sites, literal_unread = _literal_call_sites(repo)
            call_sites = list(adapter.index(repo)) + literal_sites
            for site, site_id in zip(
                call_sites, store.replace_call_sites(repo.repo_id, call_sites)
            ):
                site.id = site_id

            # After `index`, because that is when the adapter learns: `_readable_sources` records
            # as the walk reaches each file, so asking before it reports nothing.
            #
            # A set, because the two passes overlap. A `.ts` file that is not UTF-8 is skipped by
            # the language indexer and by the literal pass, and summing them would over-report --
            # a wrong number a reader would trust for being the larger one.
            unread = sorted(set(literal_unread) | set(_adapter_unread(adapter, repo)))

            for change in vendor.fetch_changes(args.from_version, args.to_version):
                store.upsert_vendor_change(change)

            for change in model_deprecations:
                store.upsert_vendor_change(change)

            # The parameter half, stored and linked in one pass. These rows join against
            # `CallSite.args_keys` rather than `operation_id`, so `VendorChangeDetector` raises
            # nothing from them -- `ParameterDeprecationDetector` does -- and that detector has
            # to name the change its finding came from or `make_locate` abandons the run.
            #
            # The id comes back from the upsert, which is why the pairing is built here rather
            # than earlier: before this line the change exists and its id does not, and a
            # detector constructed then could only have recomputed the store's own hash.
            linked = [
                LinkedDeprecation(
                    deprecation=deprecation,
                    vendor_change_id=store.upsert_vendor_change(change),
                )
                for deprecation, change in parameter_changes
            ]

            # Persist findings before running the graph: `scan()` returns unsaved
            # findings with no id, and the checkpointer needs a stable thread_id.
            findings = _scan(
                _detector_suite(
                    store,
                    spec_documents=prepared.documents,
                    call_sites=call_sites,
                    deprecations=linked,
                    vendor_id=args.vendor,
                    repo_id=repo.repo_id,
                    # The same set `_model_deprecations` read, because a retirement upserted
                    # for a vendor with no detector is a row nothing will ever read.
                    deprecation_vendors=[
                        source.vendor_id for source in model_deprecation_sources()
                    ],
                ),
                store,
            )

        # Before the finding count, because it qualifies it. A reader who sees the number first
        # has already drawn a conclusion from it.
        for line in _coverage_lines(unread):
            print(line)

        print(f"{len(findings)} finding(s)")
        if not findings:
            return 0

        # Each finding costs an agent run, a push, and a full CI wait, in sequence.
        # A wide version range produces enough of them to run for hours, so the
        # default processes one. `--limit 0` takes them all.
        selected = _select(findings, args.limit)
        print(f"remediating {len(selected)} of {len(findings)}")

        with PostgresSaver.from_conn_string(args.dsn) as checkpointer:
            checkpointer.setup()
            catalogue = load_catalogue()
            graph = build_graph(
                store=store, adapter=adapter, remediator=build_remediator(catalogue),
                forge=GitHubForge(), checkpointer=checkpointer, catalogue=catalogue,
            )
            for finding in selected:
                base = f"{finding.id}:{args.run_id or repo.head_sha[:12]}"
                thread_id, resuming = _thread_to_invoke(graph, base)
                config = {"configurable": {"thread_id": thread_id}}

                if resuming:
                    # The checkpoint's RepoRef names a temporary directory that
                    # died with the process that wrote it; only the pushed
                    # branch survived, so the clone goes there and the state
                    # learns where this process put its own copy.
                    _checkout_branch(repo, graph.get_state(config).values["branch"])
                    graph.update_state(config, {"repo": repo})
                else:
                    _reset_clone(repo)
                    # `_reset_clone` keeps ignored files on purpose, so a dependency
                    # tree the previous finding doctored would survive into this one.
                    if adapter.discard_contaminated_dependencies(repo):
                        print("discarded the previous finding's dependency tree")

                # Resuming takes `None`: an interrupted thread handed a payload
                # re-enters at START and redoes the patch and the push it had
                # already paid for.
                state = graph.invoke(
                    None if resuming else {"finding": finding, "repo": repo},
                    config=config,
                )
                # `report_reason` is listed because a tier -1 run has neither of the other
                # two by design, and the spec is explicit that these are real findings
                # worth surfacing -- they are simply not remediation findings.
                detail = (
                    state.get("pr_url")
                    or state.get("abandon_reason")
                    or state.get("report_reason")
                )
                print(f"{state['outcome']}: {detail}")

    return 0


def _operation_resolver(correlator) -> Callable[[str, str], str | None]:
    """Turn a request method and a full URL into an operation id, or None.

    The one vendor-shaped step in the whole shape path, and it is delegated whole: the readers
    take this callable rather than a URL convention because mapping a URL onto an operation is a
    fact about one vendor's paths, and that knowledge lives in that vendor's adapter.

    Splitting the URL is this function's entire contribution. A reader is handed what the tracker
    recorded, which is an absolute URL with a query string; `operation_for_request` is given a
    path, because a template matches segments and a query string is not one.
    """
    def resolve(method: str, url: str) -> str | None:
        operation = correlator.operation_for_request(method, urlsplit(url).path)
        return operation.operation_id if operation is not None else None

    return resolve


def _fold_sentry(store: GraphStore, vendor_id: str, resolve) -> Callable[[Any], int]:
    """Sentry forwards one event; an export is a list of them.

    Both shapes are accepted here rather than in the reader, because the reader's unit is an
    event and a list is a fact about how somebody exported a batch. Normalising it there would
    make the reader responsible for a file format it never sees.

    `spec_enums` is deliberately not supplied, and it is the one argument that could put a value
    in the baseline. A member listed there is recorded verbatim, which is correct when it came
    from the vendor's published specification and is a leak when it came from anywhere else --
    and the payload being read is a captured production response. Wiring it from a specification
    is a real improvement and it is not this command's to make blind: the safe default is to
    retain nothing, and that is what an absent mapping does.
    """
    reader = SentryShapeReader(store, vendor_id, resolve)

    def fold(payload: Any) -> int:
        events = payload if isinstance(payload, list) else [payload]
        return sum(reader.ingest(event) for event in events)

    return fold


def _fold_datadog(store: GraphStore, vendor_id: str, resolve) -> Callable[[Any], int]:
    """Datadog answers a search with a page of records, which its reader already walks."""
    return DatadogShapeReader(store, vendor_id, resolve).ingest


SHAPE_FORMATS: dict[str, Callable[[GraphStore, str, Any], Callable[[Any], int]]] = {
    "datadog": _fold_datadog,
    "sentry": _fold_sentry,
}
"""Which error-tracker export format a payload is in, and how to fold it.

Adding a third tracker is an entry here. The names are payload formats rather than API vendors,
which is the distinction the boundary rule turns on: `CLAUDE.md` keeps a vendor's URL
conventions, `operationId` scheme and SDK naming out of shared code, and none of that is here.
Which API the payload describes arrives through `--vendor`, is resolved by the registry, and
reaches the readers only as `_operation_resolver` -- so this file still names no vendor's
conventions and a Stripe path is still Stripe's adapter's business.

The honest qualification: two tracker names do appear here. They are the observability products
whose export shapes differ, the same way `--format` on any importer names the formats it reads,
and there is no arrangement of this table that teaches `cli.py` anything about an API.
"""


def _payload_bytes(payload: str) -> bytes:
    """One export's bytes, from a file or from the pipe, decoded by nobody yet.

    The pipe is why this exists. `sys.stdin` decodes with the machine's locale codepage rather
    than UTF-8, so an export carrying a byte that codepage has no character for raises before
    the JSON is ever parsed -- and a `UnicodeDecodeError` is a `ValueError` rather than a
    `JSONDecodeError`, so it escapes the handler that exists to report an unreadable payload and
    reaches the operator as a traceback. The buffer underneath is what was actually piped, and
    what becomes of those bytes is the caller's: three decode them as UTF-8 themselves, and
    `merge_outcome` deliberately never does, because the HMAC covers exactly what GitHub sent.
    """
    return sys.stdin.buffer.read() if payload == "-" else Path(payload).read_bytes()


def shapes(args: argparse.Namespace) -> int:
    """Fold captured error-tracker payloads into the observed-shape baseline.

    `ObservedDriftDetector` is the detector the drift specification calls the most valuable one
    Sync has, because it needs neither a vendor to publish nor a failure to have happened -- it
    fires on shape divergence alone. It has always found nothing, and the reason was not the
    sample floor: `SentryShapeReader` and `DatadogShapeReader` both write `observed_shape` and
    neither was ever constructed, so the baseline had no writer at all.

    This reads payloads somebody else exported -- a file, or stdin -- and is not a server. The
    refusal of ingestion infrastructure stands: a listener needs a port, a supervisor and an
    authentication story, none of which makes an observation mean more once it lands. A
    deployment wanting live data exports it and feeds it in, which is an operational choice.

    Nothing about the payload is retained beyond what the readers return. They record paths,
    types and nullability, and the sole value they keep is an enum member the vendor published;
    everything else is discarded at the observation boundary. So this function does not log a
    payload, does not write one to the cache, and does not report a count per field -- an error
    payload is a captured production response, and it is the most customer-sensitive input Sync
    touches.

    Re-ingesting the same export converges on the same rows and adds to `sample_count`, which is
    the natural key's intent: the counter is evidence that a shape recurs, and two identical
    bodies from two different responses are two real observations. The store cannot tell those
    from one export fed twice, so feeding one twice inflates the floor the detector depends on.
    That is an operator error this command cannot detect -- separating them needs a payload
    identity the table has no column for.
    """
    cache = Path(args.cache)
    symbol_map_path = cache / SYMBOL_MAP_FILENAME
    if not symbol_map_path.exists():
        print(
            f"no symbol map at {symbol_map_path}; run `sync run` against this cache first",
            file=sys.stderr,
        )
        return 2

    fold_for = SHAPE_FORMATS.get(args.format)
    if fold_for is None:
        print(
            f"no reader for format '{args.format}'; available: {', '.join(sorted(SHAPE_FORMATS))}",
            file=sys.stderr,
        )
        return 2

    vendor = load_vendor(args.vendor, VendorContext(
        cache_dir=cache, from_version="", to_version="",
    ))
    if not isinstance(vendor, RequestCorrelator):
        print(
            f"the {args.vendor} adapter cannot correlate an observed request to an operation, "
            f"so these payloads have nothing to be folded against",
            file=sys.stderr,
        )
        return 2

    try:
        payload = json.loads(_payload_bytes(args.payload).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # A payload that cannot be read and a vendor that sent nothing are different facts, and
        # reporting the first as zero rows would read as a quiet vendor.
        print(f"could not read {args.payload}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    store = GraphStore(args.dsn)
    store.apply_schema()

    written = fold_for(store, args.vendor, _operation_resolver(vendor))(payload)
    # The count of rows, and nothing about what was in them. A payload that resolved to no
    # operation writes nothing and is not an error: most requests in a customer's error tracker
    # are not this vendor's.
    print(f"{written} shape observation(s) recorded from {args.format}")
    return 0


def _window_bound(value: str) -> datetime | None:
    """One end of the queried period, or `None` when it is not one.

    An offset is required rather than assumed. A naive bound would be read in whatever timezone
    the database happens to run in, so the counts would land under a period the operator did not
    ask about -- and every comparison of one window against another, which is the only thing
    these rows support, would be against a window an hour or eight out of place.
    """
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


# JSON's own words for what a payload turned out to be. The operator reading the refusal below
# is holding a JSON file, and `dict` is Python's name for what that file calls an object.
_JSON_KINDS = {
    dict: "object", str: "string", bool: "boolean", int: "number", float: "number",
    type(None): "null",
}


def sentry_errors(args: argparse.Namespace) -> int:
    """Fold an exported Sentry issue list into `observed_error_window`.

    The first half of what M5 is for. Sentry was already wired in and the only question anything
    asked it was what a response body looked like, so an error rising against one vendor
    operation -- the signal the milestone exists to join against a deploy and a vendor change --
    had no numerator anywhere in the graph.

    Nothing downstream of this reads those rows yet, and that is the intended end state: a
    detector written against one fixture is a detector tuned to a fixture.

    The window comes from the operator because only they know what period they asked Sentry for.
    Nothing here can check that the export matches it -- an issue list carries no record of the
    query that produced it -- so a file exported over one period and ingested under another files
    its counts under a window they did not happen in. The bounds are validated for what can be
    checked: readable, offset-bearing, and in order.

    This reads what somebody else exported and is not a server, for the reason `shapes` gives:
    a listener needs a port, a supervisor and an authentication story, none of which makes an
    observation mean more once it lands.
    """
    since, until = _window_bound(args.since), _window_bound(args.until)
    if since is None or until is None:
        print(
            "--since and --until must each be a timestamp with a UTC offset, "
            "such as 2026-07-20T14:00:00+00:00",
            file=sys.stderr,
        )
        return 2
    if since >= until:
        # Reversed, the bounds still make a legal key, so the rows would land under a period no
        # query could ask about again.
        print(f"the window {args.since} to {args.until} ends before it starts", file=sys.stderr)
        return 2

    cache = Path(args.cache)
    symbol_map_path = cache / SYMBOL_MAP_FILENAME
    if not symbol_map_path.exists():
        print(
            f"no symbol map at {symbol_map_path}; run `sync run` against this cache first",
            file=sys.stderr,
        )
        return 2

    vendor = load_vendor(args.vendor, VendorContext(
        cache_dir=cache, from_version="", to_version="",
    ))
    if not isinstance(vendor, RequestCorrelator):
        print(
            f"the {args.vendor} adapter cannot correlate an observed request to an operation, "
            f"so these counts have nothing to be attributed to",
            file=sys.stderr,
        )
        return 2

    try:
        payload = json.loads(_payload_bytes(args.payload).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # A payload that cannot be read and a vendor whose operations did not fail are different
        # facts, and reporting the first as zero rows would read as a quiet week.
        print(f"could not read {args.payload}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if not isinstance(payload, list):
        # Sentry's own error bodies are objects, so an expired token arrives here as one. Folded
        # as a single issue it writes nothing and exits 0 reporting zero windows, which tells the
        # operator their integration is healthy and quiet at the moment it stopped working.
        print(
            f"an issues export is a list of issues; {args.payload} holds a JSON "
            f"{_JSON_KINDS.get(type(payload), type(payload).__name__)}",
            file=sys.stderr,
        )
        return 2

    store = GraphStore(args.dsn)
    store.apply_schema()

    reader = SentryErrorReader(
        store, args.repo_id, args.vendor, _operation_resolver(vendor)
    )
    try:
        ingested = reader.ingest(payload, since, until)
    except UnreadableExport as exc:
        # Refused for the reason every other refusal in this command is: nothing happened, and
        # the alternative is telling the operator their integration was quiet during an hour
        # this could not read a single record of.
        print(
            f"{exc}; the window {args.since} to {args.until} is left as it was",
            file=sys.stderr,
        )
        return 2
    # Counts of rows, and nothing about what was in them. An export holding nothing this vendor
    # owns writes none and is not an error: a customer whose error stream is all their own bugs
    # is the ordinary case. The removals are reported beside the writes because a re-query that
    # deleted rows and wrote none otherwise prints what an empty export prints, and a deletion
    # here is the half nothing can undo.
    print(
        f"{ingested.written} error window(s) recorded from sentry, "
        f"{ingested.removed} stale row(s) removed"
    )
    return 0


def ingest(args: argparse.Namespace) -> int:
    """Fold one captured OTLP/JSON export payload into `observed_call`.

    `ingest_payload` had no caller in `src/` outside its own package `__init__`, so the decode
    and the fold both worked and no span had ever reached the graph.

    This reads bytes somebody else already collected -- a file, or stdin. It is not a server and
    must not become one. `2026-07-27-sync-pipeline-discipline.md` refuses ingestion
    infrastructure rather than OTLP: a listener needs a port, a supervisor, and an
    authentication story telling one customer's collector from another's, none of which makes a
    span mean more once it lands. What makes a span mean something is the correlation below, and
    that runs here today.

    The correlator is the vendor adapter, which needs the symbol map a `run` writes: a span
    carries a URL and the graph is keyed by operation, and nothing else can bridge the two. A
    missing map is refused rather than worked around, because an ingest that correlates nothing
    produces a graph indistinguishable from a customer who does not call this vendor.

    The salt is the deployment's existing one rather than an argument or a second file.
    `ingest.py` names it as something that had to be decided before it could have a caller --
    stable for the lifetime of a deployment and stored somewhere, or the same URL digests two
    ways and the repeated-call finding disappears with nothing in the schema able to detect it.
    `corpus_salt` already satisfies exactly that, under the same three constraints, so the
    decision here is to reuse it: a second salt store would be a second thing an operator has
    to carry between hosts and a second one they can silently lose.
    """
    cache = Path(args.cache)
    symbol_map_path = cache / SYMBOL_MAP_FILENAME
    if not symbol_map_path.exists():
        print(
            f"no symbol map at {symbol_map_path}; run `sync run` against this cache first",
            file=sys.stderr,
        )
        return 2

    # `load_vendor` rather than `prepare_vendor`: this reads a cache a previous run staged and
    # must reach no network to do it.
    vendor = load_vendor(args.vendor, VendorContext(
        cache_dir=cache, from_version="", to_version="",
    ))
    if not isinstance(vendor, RequestCorrelator):
        # A real divergence between adapters, reported rather than crashed on.
        # `RequestCorrelator` is deliberately separate from `VendorAdapter` -- a vendor whose
        # traffic nobody instruments has no reason to implement it -- so an adapter can be
        # complete and still have no way to turn an observed request back into an operation.
        # Discovering that as an `AttributeError` mid-fold would report a missing method where
        # the answer is that this vendor has no correlation story yet.
        print(
            f"the {args.vendor} adapter cannot correlate an observed request to an operation, "
            f"so this payload has nothing to be folded against",
            file=sys.stderr,
        )
        return 2

    try:
        payload = json.loads(_payload_bytes(args.payload).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # A payload that cannot be read and a repository that does not call this vendor are
        # different facts, and every query downstream of `observed_call` reads the first as the
        # second. Uncaught it was a traceback, which says nothing about whether spans landed.
        print(f"could not read {args.payload}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    store = GraphStore(args.dsn)
    store.apply_schema()

    report = ingest_payload(payload, store, args.repo_id, vendor, corpus_salt())
    # `uncorrelated` is the number worth watching: an ingest that correlates nothing looks
    # exactly like a repository that does not call this vendor from every query downstream.
    print(
        f"{report.spans_read} span(s), {report.correlated} correlated, "
        f"{report.uncorrelated} unresolved, {report.rows_written} row(s)"
    )
    return 0


def _webhook_secret(secret_file: str | None) -> bytes | None:
    """The shared secret GitHub signs deliveries with, or `None` when there is not one.

    Two sources and no third. An environment variable is how a process holds a credential
    without it reaching a file, and a file is how an operator holds one without it reaching a
    process listing -- `--secret VALUE` is deliberately not offered, because an argument is
    visible in `ps` and lands in shell history. There is no default and no committed value: this
    is a shared secret rather than a public key, so any value in the tree teaches the pattern
    that puts a real one in a diff later.

    The value *is* the key. GitHub's secret is a string somebody types into a settings page and
    the HMAC is taken over its bytes, so decoding it here would be a Sync-specific rule an
    operator pasting their own secret would get wrong -- and would fail as a signature mismatch
    that looks exactly like forgery.

    Trailing whitespace is stripped from a file because `echo secret > file` writes a newline
    the shared secret does not have, and an HMAC under the wrong key is indistinguishable from
    a forged delivery. An empty value is no value: an exported-but-empty variable is the
    ordinary way a secret goes missing in a shell, and reading it as one would verify every
    delivery against the empty string.

    A file that cannot be opened is left to raise, and the caller refuses on it by name.
    `_signing_key` answers `None` for material it cannot use, on the argument that a parser's
    complaint about a key quotes offsets and lengths -- but nothing is parsed here and nothing
    was read, so an `OSError` describes a path and an errno rather than any byte of the file.
    `None` is also already spoken for: it means no secret was supplied, and the caller answers
    it with a message naming both sources, which is advice an operator who passed
    `--secret-file` has already taken. Swallowing the read would also fall through to the
    environment, and verifying against a credential the operator did not name is a signature
    check that passed for the wrong reason.

    A named file that held only whitespace answers `None` too, and the caller tells that from an
    absent secret by the argument rather than by the return: the two have different remedies and
    only one of them is the advice that message carries.
    """
    if secret_file:
        return Path(secret_file).read_bytes().strip() or None
    return os.environ.get(WEBHOOK_SECRET_ENV, "").strip().encode("utf-8") or None


def merge_outcome(args: argparse.Namespace) -> int:
    """Record what one GitHub pull request delivery says about a patch Sync opened.

    `record_merge_outcome` verified a signature, told a forgery from a malformed payload, and
    updated the corpus -- and nothing handed it a delivery, so `pr_merged` stayed null and merge
    rate, "the direct test of the product claim", had no numerator. This is the caller.

    Not a server, and it must not become one. `2026-07-27-sync-pipeline-discipline.md` refuses
    ingestion infrastructure, and the shape is the one `ingest` already took: bytes somebody else
    collected, handed in. A listener would need a port, a supervisor and an authentication story
    telling one installation's deliveries from another's, none of which makes a delivery mean
    more once it lands.

    Bytes, never text. The HMAC covers exactly what GitHub sent, so a payload decoded and
    re-encoded on the way past verifies against a different string and fails in a way that reads
    as forgery.

    A missing secret refuses rather than skipping the check. There is no question to ask of
    unverified bytes, and a receiver that processed them anyway would let anyone on the internet
    write the table every future routing decision is measured against.
    """
    try:
        secret = _webhook_secret(args.secret_file)
    except OSError as exc:
        # The path and the kind of failure, and nothing else. Not `str(exc)` either: this is the
        # one refusal in this command whose subject is a credential, and the exception class
        # already tells an absent file from an unreadable one.
        print(
            f"could not read the webhook secret from {args.secret_file}: "
            f"{type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    if secret is None and args.secret_file:
        # A file that opened and held nothing is not a secret nobody supplied. The message below
        # answers the second and names both sources, which is advice an operator who passed
        # --secret-file has already taken. What the file held is not described: trailing
        # whitespace is stripped before this, so there is nothing to describe and nothing that
        # could be said about a longer file without narrowing a credential.
        print(
            f"the webhook secret file {args.secret_file} holds nothing usable. "
            "Refusing rather than processing an unverified delivery.",
            file=sys.stderr,
        )
        return 2

    if secret is None:
        print(
            f"no webhook secret: set {WEBHOOK_SECRET_ENV} or pass --secret-file. "
            "Refusing rather than processing an unverified delivery.",
            file=sys.stderr,
        )
        return 2

    try:
        body = _payload_bytes(args.payload)
    except OSError as exc:
        # Exit 2 rather than 1. One is a verdict about a delivery -- forged, or genuine and
        # unusable -- and a body nothing ever read is neither, so a wrapper scripting on the
        # difference would retry a mistyped path as though GitHub had sent something.
        print(f"could not read {args.payload}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    # Fetched by whoever holds a GitHub client, not here: the pull request event carries a count
    # and a link rather than the commits. Absent, the column stays null rather than zero, and
    # zero would read as "no human touched this patch" -- the claim the benchmark rests on.
    try:
        commits = (
            json.loads(Path(args.commits).read_text(encoding="utf-8")) if args.commits else None
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # `None` is already the value for a `--commits` nobody passed, so a file that could not
        # be read cannot answer with one: the delivery would be recorded with
        # human_edits_before_merge left null, which the benchmark reads as unmeasured rather
        # than as a measurement the operator asked for and did not get.
        print(f"could not read {args.commits}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    store = GraphStore(args.dsn)
    store.apply_schema()

    try:
        written = record_merge_outcome(body, args.signature, secret, store, commits)
    except WebhookSignatureError:
        # The message says nothing about the secret or the digest. An operator pastes this
        # into an issue, and "expected X, got Y" is a free guess at how close a forgery came.
        print("delivery rejected: the signature does not verify", file=sys.stderr)
        return 1
    except WebhookFormatError as exc:
        print(f"delivery rejected: {exc}", file=sys.stderr)
        return 1

    if written:
        print("merge outcome recorded")
    else:
        # Not an error. Humans and other automation open pull requests in the same repository
        # and every one of them delivers here, so the ordinary answer is that this one was not
        # Sync's or did not decide anything.
        print("nothing to record: the delivery decides nothing or names no attempt Sync opened")
    return 0


def _signing_key(key_file: str | None):
    """The Ed25519 private key the feed is signed with, or `None` when there is not one.

    Two sources and no third, which is the rule `_webhook_secret` already established: an
    environment variable is how a process holds a credential without it reaching a file, a file
    is how an operator holds one without it reaching a process listing, and `--key VALUE` is
    deliberately not offered because an argument is visible in `ps` and lands in shell history.

    PEM rather than raw bytes, for two reasons that agree. It is what an operator's key
    management already produces -- `openssl genpkey -algorithm ed25519` writes exactly this --
    and reconstructing a key from raw bytes needs a call that `tests/test_feed_cache.py` scans
    every tracked file for. That scan exists to keep a private key out of this repository, and
    the right response to it is a loader that does not need the call rather than an exception
    to the rule.

    Material this cannot parse answers `None` like absent material. The caller's job is to
    refuse, and the two cases have the same remedy -- supply a usable key -- so telling them
    apart would only be an invitation to describe what was wrong with the bytes.

    A file that cannot be *opened* is a third case and is left to raise, which is the rule
    `_webhook_secret` already established: nothing has been parsed and nothing was read, so an
    `OSError` describes a path and an errno rather than any byte of the key. The caller refuses
    on it by name.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    material = (
        Path(key_file).read_bytes()
        if key_file
        else os.environ.get(FEED_SIGNING_KEY_ENV, "").encode("utf-8")
    )
    if not material.strip():
        return None

    try:
        key = serialization.load_pem_private_key(material, password=None)
    except (ValueError, TypeError):
        # Nothing about the material reaches the log. A parser's complaint about a key quotes
        # offsets and lengths, and a narrowed key is a leaked key.
        return None

    # A different algorithm would sign, and every consumer would reject the result as a forgery.
    return key if isinstance(key, Ed25519PrivateKey) else None


def publish_feed(args: argparse.Namespace) -> int:
    """Write one vendor's signed feed into a directory, and stop.

    `render_feed`, `sign_feed` and `public_key_bytes` were finished and called by nothing, which
    left the consuming half -- `FeedCache` verifying before it parses, `sync://feed/{vendor}`
    serving the result -- with nothing to consume. This is the producer.

    Not a publisher of bytes to anywhere. `2026-07-26-sync-public-change-feed.md` puts hosting
    outside the architecture: static files behind a CDN, no server-side logic, and the keypair
    and the publish job are operational rather than architectural. So this writes
    `{vendor}.json` and `{vendor}.json.sig` into a directory it is handed, and whoever runs it
    decides where those bytes go -- the boundary `ingest` and `merge-outcome` already hold.

    The rows come from the graph rather than from a vendor's API. The feed publishes what a
    scan already computed, so publishing reaches no network and a vendor nobody has scanned
    publishes an empty array rather than an error: the array is the whole contract, and a vendor
    that shipped nothing has a feed.

    A missing key refuses, and the refusal happens before anything is written. An unsigned feed
    drives code changes on bytes nothing vouched for, and a half-written pair is worse than
    nothing -- a consumer may fetch a payload while its signature does not yet exist, which is
    indistinguishable from a payload whose signature was stripped.

    Both files are written as bytes. A signature covers exactly the bytes signed, so a payload
    that went out through a text mode on this platform would carry translated line endings and
    fail verification in a way that reads as forgery.
    """
    try:
        key = _signing_key(args.key_file)
    except OSError as exc:
        # The path and the kind of failure, and nothing else. `None` is spoken for -- it means no
        # usable key material -- and the message that answers it names both sources, which is
        # advice an operator who passed --key-file has already taken.
        print(
            f"could not read the feed signing key from {args.key_file}: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    if key is None:
        print(
            f"no usable feed signing key: set {FEED_SIGNING_KEY_ENV} or pass --key-file with an "
            "Ed25519 private key in PEM form. Refusing rather than publishing a feed nothing "
            "vouched for.",
            file=sys.stderr,
        )
        return 2

    store = GraphStore(args.dsn)
    store.apply_schema()

    payload = render_feed(store.all_vendor_changes(args.vendor), args.vendor)
    signature = sign_feed(payload, key)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Signature first. Either order leaves a window where a reader can see one file and not the
    # other, and the safe direction is the one where the payload is what appears last: a
    # signature with no payload is a fetch that fails, while a payload with no signature is
    # unverified bytes a consumer might act on.
    (out_dir / f"{args.vendor}.json.sig").write_bytes(signature)
    (out_dir / f"{args.vendor}.json").write_bytes(payload)

    count = len(json.loads(payload.decode("utf-8")))
    print(f"published {args.vendor}: {count} change(s) to {out_dir}")
    return 0


def feed_public_key(args: argparse.Namespace) -> int:
    """Print the public half of the signing key, for an operator to commit.

    The legitimate caller of `public_key_bytes`, and the reason it exists: `sync.core.keys`
    holds the trust anchor as a hex literal rotatable only through a release, and somebody has
    to derive it from a key this repository must never hold. Hex because that is the form the
    constant takes, so the output is what goes in the diff.

    Nothing is written and nothing else is printed. A command that also emitted the private half
    "for convenience" is how a key reaches a terminal scrollback.
    """
    try:
        key = _signing_key(args.key_file)
    except OSError as exc:
        # Duplicated rather than shared, for the reason every refusal in this module is: what a
        # wrong reading costs differs per command, and here it is a trust anchor an operator was
        # about to paste into `sync.core.keys`.
        print(
            f"could not read the feed signing key from {args.key_file}: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    if key is None:
        print(
            f"no usable feed signing key: set {FEED_SIGNING_KEY_ENV} or pass --key-file.",
            file=sys.stderr,
        )
        return 2

    print(public_key_bytes(key).hex())
    return 0


def benchmark(args: argparse.Namespace) -> int:
    """Print the tier B quality axes for whatever the corpus holds.

    `compute_axes` and `compute_binding_accuracy` were finished, tested, and reached from
    nothing in `src/`, which left the spec's instruction -- recorded, not gated, reviewed by a
    human -- with no surface for the reviewing to happen on.

    Reading only. Nothing is written, nothing is compared to a threshold, and the exit code says
    the report was produced rather than whether the numbers were good: a subcommand that exited
    non-zero on a low merge rate would be the gate the spec forbids, arriving by the back door.

    The corpus holds no rows today, so the honest output is every axis unmeasured over zero
    samples. `apply_schema` runs first for that reason -- against a database no run has touched,
    the alternative to an empty report is an error about a missing table, which tells an
    operator nothing about the pipeline.
    """
    store = GraphStore(args.dsn)
    store.apply_schema()

    # Read before anything is scored. Scoring truncates the graph it works in, so the corpus has
    # to be in hand before that happens even though the two databases are required to differ --
    # the ordering costs nothing and does not depend on the check below holding.
    outcomes = store.migration_outcomes()

    if not args.score_pair:
        print(render_report(outcomes), end="")
        return 0

    if args.score_dsn is None or args.score_dsn == args.dsn:
        # `score_pair` empties the store before indexing the mutated tree, because the detector
        # reads every call site the graph holds and a row from another tree is a finding nobody
        # labelled. Pointed at the corpus database that would delete the outcomes this same
        # command just rendered, so the refusal is what makes it impossible to get wrong once.
        print(
            "--score-pair scores into the same database it truncates, so --score-dsn is required "
            "and must not name the same database as --dsn",
            file=sys.stderr,
        )
        return 2

    try:
        scored = _score_corpus(Path(args.score_pair), args.score_dsn)
    except (KeyError, LookupError, ValueError) as exc:
        print(f"pair specification: {exc}", file=sys.stderr)
        return 2

    print(
        render_report(
            outcomes,
            findings=scored.findings,
            labels=scored.labels,
            reference=scored.reference,
            skipped_files=scored.skipped_files,
        ),
        end="",
    )
    return 0


def _corpus_targets(
    spec_path: Path, hold_back: Sequence[Any], sites: Sequence[CallSite], change: VendorChange
) -> list[str]:
    """The call sites a specification asks to be broken: every one on the changed operation
    except the ones it holds back.

    Holding one back is what gives binding precision a negative it could be wrong about. An
    untargeted site is never edited, so nothing writes the changed dependency into it, and it is
    unaffected by construction rather than by anyone's judgement -- while still being a site
    `call_sites_for_operation` returns and the field match is run against. Targeting every site
    leaves precision's false-positive term with no candidates at all, which is why it read
    1.0000 over the frozen corpus and would have through any binder whatsoever.

    The specification names them and this only honours the naming, for the reason the changed
    field is also written down rather than derived: which sites a corpus breaks is a
    distribution, and a harness that chose one would be choosing it without saying so. Every
    held-back site is also a site recall no longer measures, which is a trade a reader of the
    number has to be able to see in the file the number was taken over.

    By position rather than by call site id, because a position is checkable against the pinned
    commit by a reader and an id is a hash of one.

    A position no indexed site on the changed operation holds is refused rather than skipped: a
    specification whose checkout has moved would otherwise hold nothing back, target everything
    as before, and report a corpus carrying a negative that it does not have.
    """
    on_operation = [site for site in sites if site.operation_id == change.operation_id]
    if not on_operation:
        raise LookupError(
            f"no indexed call site reaches {change.operation_id}, so there is nothing this "
            f"change could break and a score over it would be a score over an empty corpus"
        )

    by_position = {(site.path, site.line, site.col): site.id for site in on_operation}
    held: set[str] = set()
    for entry in hold_back:
        absent = [key for key in ("path", "line", "col") if key not in (entry or {})]
        if absent:
            raise KeyError(
                f"{spec_path}: a hold_back entry names no {', '.join(absent)}, so it addresses "
                f"no call site"
            )
        position = (str(entry["path"]), int(entry["line"]), int(entry["col"]))
        if position not in by_position:
            raise KeyError(
                f"{spec_path} holds back {position[0]}:{position[1]}:{position[2]}, which is not "
                f"an indexed call site on {change.operation_id}; the specification names a "
                f"position this checkout does not have, and scoring it anyway would break every "
                f"site and report a negative the corpus no longer holds"
            )
        held.add(by_position[position])

    targets = [site.id for site in on_operation if site.id not in held]
    if not targets:
        raise KeyError(
            f"{spec_path} holds back every indexed call site on {change.operation_id}, leaving "
            f"the mutation nothing to break; a pair with no target labels every site unaffected "
            f"and emits no finding, which reads as a flawless run over an empty positive set"
        )
    return targets


def _score_corpus(spec_path: Path, score_dsn: str):
    """Generate a labelled pair from a corpus specification and score the pipeline against it.

    A file rather than eight flags, and for the reason `generated-vendors.yaml` is a file: a
    score is worth having only if what it was taken over is recorded where a reader can check it.
    Every field is required and a missing one raises naming the file -- a corpus that quietly
    defaulted its change kind would report a number over a mutation nobody chose.

    The vendor is loaded rather than staged, so this reaches no network: `load_vendor` builds the
    adapter over artifacts a previous `sync run` left in the cache, which is the same offline
    contract `sync ingest` has.

    Which call sites to break is the caller's decision and this is the caller, but the decision
    is read out of the specification rather than made here -- `_corpus_targets` carries why.
    `generate_pair` refuses to choose targets itself, deliberately, and a harness that picked a
    subset would be choosing a distribution without saying so.
    """
    try:
        spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        # Raised rather than printed, because the caller owns the refusal and every other
        # unusable specification arrives there the same way. `yaml.YAMLError` inherits from
        # `Exception` rather than from `ValueError`, so a tab where a space belongs was a
        # traceback; the decode was caught by the caller and reported the codec's byte offset
        # with no file named, which is unhelpful when two paths reach that command.
        raise ValueError(f"could not read {spec_path}: {type(exc).__name__}: {exc}") from exc

    required = ("repo", "vendor", "cache", "from_version", "to_version", "change")
    missing = [key for key in required if key not in spec]
    if missing:
        raise KeyError(f"{spec_path} names no {', '.join(missing)}")
    change_spec = spec["change"]
    change_required = ("kind", "operation", "field")
    change_missing = [key for key in change_required if key not in change_spec]
    if change_missing:
        raise KeyError(f"{spec_path}: change names no {', '.join(change_missing)}")

    vendor = load_vendor(spec["vendor"], VendorContext(
        cache_dir=Path(spec["cache"]),
        from_version=str(spec["from_version"]),
        to_version=str(spec["to_version"]),
    ))

    root = Path(spec["repo"])
    sources, skipped = read_checkout(root)

    change = VendorChange(
        vendor_id=vendor.vendor_id,
        from_version=str(spec["from_version"]),
        to_version=str(spec["to_version"]),
        kind=str(change_spec["kind"]),
        operation_id=str(change_spec["operation"]),
        path_ptr=str(change_spec.get("path", "")),
        severity="breaking",
        source="oasdiff",
        raw={"id": str(change_spec["kind"]),
             "text": f"removed `{change_spec['field']}` from {change_spec['operation']}"},
    )

    store = GraphStore(score_dsn)
    store.apply_schema()

    with tempfile.TemporaryDirectory() as workdir:
        repo = RepoRef(
            repo_id=f"benchmark:{root.name}", url=str(root),
            local_path=str(Path(workdir) / "indexed"), head_sha="0" * 40,
        )
        # Written before the adapter is chosen, because `matches` reads the manifest off disk:
        # `select_language_adapter` asks each language's adapter whether this repository declares
        # the vendor's package, and a tree that is still a dict answers nothing. `index_sources`
        # writes it again, which is a no-op over identical bytes.
        materialise(sources, Path(repo.local_path))
        adapter = select_language_adapter(repo, vendor)
        sites = index_sources(sources, store, repo, adapter)
        change.id = store.upsert_vendor_change(change)

        targets = _corpus_targets(spec_path, spec.get("hold_back") or [], sites, change)

        mutated = RepoRef(
            repo_id=repo.repo_id, url=repo.url,
            local_path=str(Path(workdir) / "mutated"), head_sha=repo.head_sha,
        )
        return score_change(sources, change, sites, targets, store, mutated, adapter,
                            skipped_files=tuple(skipped))


def intake(args: argparse.Namespace) -> int:
    """Report which of a repository's declared dependencies Sync can actually watch.

    A run answers one question -- does this repository depend on the vendor it was told to look
    at -- and says nothing about the rest of the manifest, so a customer pointing Sync at their
    codebase cannot find out what it covers. The middle category is the reason this exists:
    watchable but unconfigured is the work queue, and it is invisible until something prints it.

    Reads what is on disk and reaches no network. Evidence that a package's SDK is
    generator-produced has to be confirmed rather than assumed, and confirming it is a fetch --
    so this command reports what the deployment already knows and leaves the middle category
    smaller than it truly is rather than guessing to fill it. That direction is deliberate: this
    report is a sales asset as much as an engineering one, and an overstatement is worse than an
    omission.

    Exit code says the report was produced, not whether the answer was good. A command that
    exited non-zero on poor coverage would be a gate nobody asked for, and coverage is the thing
    being measured.
    """
    evidence = read_sdk_repositories(Path(args.evidence)) if args.evidence else {}
    # The directory is a document somebody fetched, parsed here rather than downloaded: this
    # command reports what the deployment already knows, and a fetch inside it would make a
    # report of what is on disk quietly online.
    if args.registry_directory:
        try:
            document = json.loads(Path(args.registry_directory).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            # Refused rather than reported as a directory holding nothing. An entry the document
            # declines already reaches the operator through `report.unreadable`, but a document
            # that never parsed has no entries to decline: the directory is what promotes a
            # declared dependency into the watchable category, so an empty one shrinks the work
            # queue this command exists to print and nothing anywhere says why.
            print(
                f"could not read {args.registry_directory}: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2
        directory, directory_unreadable = parse_directory(document)
    else:
        directory, directory_unreadable = [], ()

    registry_apis = (
        read_registry_apis(Path(args.registry_evidence)) if args.registry_evidence else {}
    )
    report = assess_repository(
        Path(args.repo),
        generator_manifests=evidence,
        registry_entries=directory,
        registry_unreadable=directory_unreadable,
        registry_apis=registry_apis,
        registry_moved_since=args.registry_moved_since,
    )

    if args.rank_by_repo_id:
        # Ranked only when asked, and only against a repository the indexer has already run
        # over. `sync run` is what writes `call_site`, so ranking an unindexed repository would
        # report every watched dependency as a measured zero -- not a missing feature but a
        # confident wrong answer, indistinguishable to a reader from a repository that genuinely
        # calls nothing. Requiring the id rather than defaulting it is what keeps that
        # unreachable: an operator has to name the repository whose index they mean.
        store = GraphStore(args.dsn)
        store.apply_schema()
        ranking = rank_reachability(
            report,
            call_sites=store.call_site_counts(args.rank_by_repo_id),
            observed_calls=observed_call_counts(store.observed_calls(args.rank_by_repo_id)),
        )
        print(ranking.to_json())
    else:
        print(report.to_json())

    for problem in report.unreadable:
        # To stderr, and never silently. A manifest that would not parse is not a repository
        # with no dependencies, and reported as one it reads as a clean scan of an empty project;
        # a declined catalogue entry is the same narrowing arriving from a different file. The
        # prefix names neither, because each problem already names its own source.
        print(f"unreadable: {problem}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="sync")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="detect and remediate vendor changes in a repository")
    run_parser.add_argument("--vendor", default="stripe", choices=available_vendors())
    run_parser.add_argument("--from-version", dest="from_version", required=True)
    run_parser.add_argument("--to-version", dest="to_version", required=True)
    run_parser.add_argument("--repo", required=True, help="git URL of the repository to scan")
    run_parser.add_argument("--dsn", default=DEFAULT_DSN)
    run_parser.add_argument("--cache", default=".cache/specs")
    run_parser.add_argument("--limit", type=int, default=1, help="findings to remediate; 0 for all")
    run_parser.add_argument("--run-id", dest="run_id", default=None,
                            help="checkpoint namespace; defaults to the cloned commit")
    run_parser.set_defaults(func=run)

    ingest_parser = sub.add_parser(
        "ingest", help="fold a captured OTLP/JSON payload into the observed-call graph"
    )
    ingest_parser.add_argument("--vendor", default="stripe", choices=available_vendors())
    ingest_parser.add_argument("--payload", required=True,
                               help="path to an OTLP/JSON export request, or - for stdin")
    ingest_parser.add_argument("--repo-id", dest="repo_id", required=True,
                               help="the repository whose traffic this payload describes")
    ingest_parser.add_argument("--dsn", default=DEFAULT_DSN)
    ingest_parser.add_argument("--cache", default=".cache/specs",
                               help="where a previous `sync run` left symbols.json")
    ingest_parser.set_defaults(func=ingest)

    shapes_parser = sub.add_parser(
        "shapes", help="fold captured error-tracker payloads into the observed-shape baseline"
    )
    shapes_parser.add_argument("--vendor", default="stripe", choices=available_vendors())
    # Choices read from the table rather than restated, so a tracker added there is offered here
    # without a second edit -- and a reader registered and unreachable is the defect this
    # command exists to close, not one to reintroduce at the parser.
    shapes_parser.add_argument("--format", default="sentry", choices=sorted(SHAPE_FORMATS),
                               help="which error tracker exported this payload")
    shapes_parser.add_argument("--payload", required=True,
                               help="path to an exported payload, or - for stdin")
    shapes_parser.add_argument("--dsn", default=DEFAULT_DSN)
    shapes_parser.add_argument("--cache", default=".cache/specs",
                               help="where a previous `sync run` left symbols.json")
    shapes_parser.set_defaults(func=shapes)

    sentry_errors_parser = sub.add_parser(
        "sentry-errors",
        help="fold an exported Sentry issue list into the observed error-window counts",
    )
    sentry_errors_parser.add_argument("--vendor", default="stripe", choices=available_vendors())
    sentry_errors_parser.add_argument("--payload", required=True,
                                      help="path to an exported issue list, or - for stdin")
    sentry_errors_parser.add_argument("--repo-id", dest="repo_id", required=True,
                                      help="the repository whose errors this export describes")
    # The period the export was queried over. Required and never defaulted: an issue list carries
    # no record of the query that produced it, so a guessed window would file real counts under a
    # period they did not happen in and nothing downstream could tell.
    sentry_errors_parser.add_argument("--since", required=True,
                                      help="start of the queried window, with a UTC offset")
    sentry_errors_parser.add_argument("--until", required=True,
                                      help="end of the queried window, with a UTC offset")
    sentry_errors_parser.add_argument("--dsn", default=DEFAULT_DSN)
    sentry_errors_parser.add_argument("--cache", default=".cache/specs",
                                      help="where a previous `sync run` left symbols.json")
    sentry_errors_parser.set_defaults(func=sentry_errors)

    merge_parser = sub.add_parser(
        "merge-outcome",
        help="record one GitHub pull request delivery against the migration corpus",
    )
    merge_parser.add_argument("--payload", required=True,
                              help="path to the delivery body, or - for stdin")
    merge_parser.add_argument("--signature", required=True,
                              help=f"the {SIGNATURE_HEADER} header value, verbatim")
    # A path, never a value: an argument is visible in `ps` and lands in shell history.
    merge_parser.add_argument("--secret-file", dest="secret_file", default=None,
                              help=f"file holding the shared secret; "
                                   f"defaults to ${WEBHOOK_SECRET_ENV}")
    merge_parser.add_argument("--commits", default=None,
                              help="path to the branch's commits, as GitHub's API returns them; "
                                   "omitted leaves human_edits_before_merge unmeasured")
    merge_parser.add_argument("--dsn", default=DEFAULT_DSN)
    merge_parser.set_defaults(func=merge_outcome)

    publish_parser = sub.add_parser(
        "publish-feed", help="write one vendor's signed change feed to a directory"
    )
    publish_parser.add_argument("--vendor", required=True,
                                help="which vendor's feed to publish")
    publish_parser.add_argument("--out-dir", dest="out_dir", required=True,
                                help="directory the two files are written to; hosting them is "
                                     "somebody else's job")
    # A path, never a value: an argument is visible in `ps` and lands in shell history.
    publish_parser.add_argument("--key-file", dest="key_file", default=None,
                                help=f"file holding the Ed25519 signing key in PEM form; "
                                     f"defaults to ${FEED_SIGNING_KEY_ENV}")
    publish_parser.add_argument("--dsn", default=DEFAULT_DSN)
    publish_parser.set_defaults(func=publish_feed)

    public_key_parser = sub.add_parser(
        "feed-public-key",
        help="print the public half of the signing key, as the hex sync.core.keys holds",
    )
    public_key_parser.add_argument("--key-file", dest="key_file", default=None,
                                   help=f"file holding the Ed25519 signing key in PEM form; "
                                        f"defaults to ${FEED_SIGNING_KEY_ENV}")
    public_key_parser.set_defaults(func=feed_public_key)

    intake_parser = sub.add_parser(
        "intake",
        help="report which of a repository's declared dependencies Sync can watch",
    )
    intake_parser.add_argument("--repo", required=True,
                               help="path to a checkout whose manifest should be read")
    intake_parser.add_argument("--evidence", default=None,
                               help="a file of confirmed package-to-SDK-repository entries; "
                                    "without one the watchable category is reported empty")
    intake_parser.add_argument(
        "--registry-directory", dest="registry_directory", default=None,
        help="a public OpenAPI directory document; entries in it make a declared dependency "
             "watchable, never watched -- the directory mirrors a specification rather than "
             "hosting it",
    )
    intake_parser.add_argument(
        "--registry-evidence", dest="registry_evidence", default=None,
        help="a file of confirmed package-to-directory-entry pairs; the join is never a name "
             "resemblance, so without one the directory promotes nothing",
    )
    intake_parser.add_argument(
        "--registry-moved-since", dest="registry_moved_since", default=None,
        help="only count a directory entry whose specification moved after this timestamp; "
             "without it an entry last touched years ago counts the same as one that moved today",
    )
    intake_parser.add_argument(
        "--rank-by-repo-id", dest="rank_by_repo_id", default=None,
        help="rank the report by the call sites indexed for this repo_id instead of listing it; "
             "requires that `sync run` has already indexed that repository, since an unindexed "
             "one would report every watched dependency as never called",
    )
    intake_parser.add_argument("--dsn", default=DEFAULT_DSN,
                               help="read indexed call sites and observed calls from here when "
                                    "ranking; unused otherwise")
    intake_parser.set_defaults(func=intake)

    benchmark_parser = sub.add_parser(
        "benchmark", help="print the tier B quality axes with their sample sizes"
    )
    benchmark_parser.add_argument("--dsn", default=DEFAULT_DSN)
    benchmark_parser.add_argument(
        "--score-pair", dest="score_pair", default=None,
        help="a corpus specification naming a checkout, a staged vendor cache and one change; "
             "the pair is generated from it and the pipeline scored against its labels",
    )
    benchmark_parser.add_argument(
        "--score-dsn", dest="score_dsn", default=None,
        help="a database of its own for scoring, which truncates what it scores in; it must not "
             "name the database --dsn reads the corpus from",
    )
    benchmark_parser.set_defaults(func=benchmark)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
