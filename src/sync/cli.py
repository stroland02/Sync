"""Local driver for a Sync run. The only entry point at M0."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from langgraph.checkpoint.postgres import PostgresSaver

from sync.benchmark.report import render_report
from sync.core import CallSite, Finding, RepoRef, VendorChange
from sync.core.protocols import RequestCorrelator
from sync.detect.efficiency import EfficiencyDetector
from sync.detect.observed_drift import DeclaredField, ObservedDriftDetector
from sync.detect.parameter_deprecation import LinkedDeprecation, ParameterDeprecationDetector
from sync.detect.status_rate import StatusRateDetector
from sync.detect.vendor_change import VendorChangeDetector
from sync.forge.github import GitHubForge
from sync.graph.store import GraphStore
from sync.index.literals import index_operation_literals
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
    ANTHROPIC,
    OPENAI,
    DeprecationAdapter,
    DeprecationSource,
    ParameterDeprecation,
    http_fetch,
    parameters_to_vendor_changes,
    parse_parameter_deprecations,
)
from sync.signals.registry import (
    SYMBOL_MAP_FILENAME,
    VendorContext,
    available_vendors,
    load_vendor,
    prepare_vendor,
)
from sync.telemetry import ingest_payload

DEFAULT_DSN = "postgresql://sync:sync@localhost:5433/sync"

# Vendors whose parameter deprecations a scan reads. Both publish one page carrying both a model
# lifecycle table and a parameter table; `parse_parameter_deprecations` tells them apart.
DEPRECATION_SOURCES: tuple[DeprecationSource, ...] = (ANTHROPIC, OPENAI)

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
    """Every vendor's deprecated request parameters, skipping any vendor that cannot be reached.

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

    for source in DEPRECATION_SOURCES:
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
    """Every vendor's retired models as `VendorChange` rows, skipping a vendor that is unreachable.

    `DeprecationAdapter` was finished, tested, and constructed nowhere in `src/`, so no
    `ModelDeprecation` ever became a `VendorChange` and `LiteralSwapRemediator` sat in the
    cascade with nothing to act on. This is that call site.

    The cache path is the one `_page` writes for the parameter half, deliberately: both halves
    read the same page from the same vendor, and the adapter's own freshness window is the same
    twelve hours. `_parameter_deprecations` runs first and leaves the page there, so the adapter
    finds it fresh and the run downloads each vendor once rather than twice. That is the shared
    input, and the sharing is the file rather than a variable because the adapter fetches for
    itself and its signature is not this module's to change.

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

    for source in DEPRECATION_SOURCES:
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


def _literal_call_sites(repo: RepoRef) -> list[CallSite]:
    """Call sites for the model ids named as string literals in the repository.

    `typescript.py` finds SDK member chains, which is the right shape for `stripe.charges.create`
    and the wrong one for a model id: no member chain leads to a string in an options object.
    `index.literals` exists for that and nothing called it, so the parameter-deprecation detector
    had no rows to match against however many deprecations it was handed.

    The prefixes come from each vendor's own `DeprecationSource`, keeping vendor naming out of
    the index stage. `sdk_version` is unknown here and says so -- a model literal is named by the
    customer's code, not by a package the manifest pins.
    """
    root = Path(repo.local_path)
    sites: list[CallSite] = []

    for file_path in root.rglob("*.ts"):
        if "node_modules" in file_path.parts or file_path.name.endswith(".d.ts"):
            continue
        source = file_path.read_text(encoding="utf-8", errors="replace")
        relative = file_path.relative_to(root).as_posix()
        for vendor in DEPRECATION_SOURCES:
            sites.extend(
                index_operation_literals(
                    source, path=relative, repo_id=repo.repo_id, vendor_id=vendor.vendor_id,
                    sdk_version="unknown", prefixes=vendor.prefixes,
                )
            )

    return sites


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
    return [
        ("vendor_change", VendorChangeDetector(store)),
        ("parameter-deprecation", ParameterDeprecationDetector(deprecations, call_sites)),
        # Several documents rather than one: a vendor that publishes per product declares its
        # response fields across all of them, and taking only the first would report every field
        # in every other product as undeclared -- the detector's loudest finding, raised from
        # this file having read less than the vendor published.
        ("observed-drift", ObservedDriftDetector(store, _declared_fields(spec_documents), vendor_id)),
        *[
            (f"model-deprecation:{vendor}", VendorChangeDetector(store, vendor_id=vendor))
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
        print(f"{name}: {len(produced)} finding(s)")

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
    adapter = TypeScriptAdapter(vendor_adapter=vendor)

    store = GraphStore(args.dsn)
    store.apply_schema()

    with tempfile.TemporaryDirectory() as workdir:
        repo = _clone(args.repo, Path(workdir) / "repo")

        if not adapter.matches(repo):
            # What the indexer looks for, not what `--vendor` selected. `TypeScriptAdapter`
            # matches one hardcoded SDK package, so selection is data at the signal stage and
            # is not yet data at the index stage -- and a message naming `args.vendor` would
            # report a check that did not happen.
            print(f"{args.repo} declares no SDK the TypeScript indexer recognises", file=sys.stderr)
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
        # M0 has one entry point and no incremental indexing story: a stale row
        # from a previous invocation is indistinguishable from a real finding to
        # the detector, so every run starts from an empty graph. M2's incremental
        # indexing replaces this; a hosted control plane must never do this, since
        # it would erase other customers' state rather than just this one's.
        # Finding ids are stable hashes of (detector, call_site_id, vendor_change_id),
        # so a re-inserted finding gets the same id its checkpoint thread already
        # used -- checkpoint coordinates survive the truncate.
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
            store.truncate_all()

            # Kept as well as stored: `ParameterDeprecationDetector` takes call sites directly,
            # and the store answers `call_sites_for_operation` rather than "all of them". The id
            # comes back from the upsert, and a finding addresses its call site by id.
            call_sites = []
            for site in list(adapter.index(repo)) + _literal_call_sites(repo):
                site.id = store.upsert_call_site(site)
                call_sites.append(site)

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
                    deprecation_vendors=[source.vendor_id for source in DEPRECATION_SOURCES],
                ),
                store,
            )

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

    if args.payload == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))

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
    print(render_report(store.migration_outcomes()), end="")
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

    benchmark_parser = sub.add_parser(
        "benchmark", help="print the tier B quality axes with their sample sizes"
    )
    benchmark_parser.add_argument("--dsn", default=DEFAULT_DSN)
    benchmark_parser.set_defaults(func=benchmark)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
