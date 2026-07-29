"""Generate the corpus specifications from a stated rule, so the sample is not hand-picked.

The specifications this writes are committed and frozen; this script is how they were derived
and is the record of the rule, in the way `scripts/build_twilio_fixtures.py` is the record of how
its fixtures were built. Run it again and the same specifications come out of the same pinned
inputs.

Why a rule rather than a choice
-------------------------------
A corpus assembled by picking pairs that score well is a corpus that measures the picker. So the
selection is executable and the score is whatever it produces, including the pairs the harness
then refuses. The rule, in full:

  - **Which repositories.** Every entry in `benchmark/corpus/repositories.yaml`.
  - **Which operations.** Per repository, the two operations with the most indexed call sites
    where at least one call passes an object argument, ties broken by operation id ascending. An
    operation whose calls take no object argument is excluded because neither mutation can attach
    to one -- `stripe.customers.retrieve(id)` has nowhere to put a property.
  - **Which kinds.** `request-property-removed` and `response-property-removed` for each, which
    are the two mechanically different inversions `sync.benchmark.mutate` implements. The third
    supported kind, `request-parameter-removed`, mutates identically to the first and would add
    pairs without adding information.
  - **Which field.** The alphabetically first property of that operation in the pinned
    specification that no indexed call site in the repository already passes, for a request
    change, or already reads, for a response change. Real properties of the real operation, so
    the mutation writes something the vendor could actually have removed; alphabetically first
    so the choice is not a judgement.

`generate_pair` refuses a tree where any call site already carries the changed dependency, so the
"not already used anywhere" clause is not a nicety -- a field chosen without it produces a
specification that cannot be scored at all.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import yaml

from sync.cli import select_language_adapter
from sync.core import RepoRef
from sync.graph.store import GraphStore
from sync.signals.registry import VendorContext, load_vendor

MANIFEST = Path("benchmark/corpus/repositories.yaml")
CORPUS = Path(".cache/corpus")
SPECS = Path("benchmark/corpus/pairs")
CACHE = Path(".cache/specs")

# The pinned pair the specifications name. Both tags are in
# `scripts/fetch_measurement_inputs.py`, which is what puts the specification on disk; `v2320`
# and `v2330` are the one window the duplicate Stripe tags collapse to.
FROM_VERSION = "v2320"
TO_VERSION = "v2330"
OPERATIONS_PER_REPOSITORY = 2
KINDS = ("request-property-removed", "response-property-removed")

_REQUEST_MEDIA = "application/x-www-form-urlencoded"
_RESPONSE_MEDIA = "application/json"


def _resolve(document: dict, schema: dict) -> dict:
    """One level of `$ref`, which is as deep as a top-level property list needs."""
    ref = schema.get("$ref")
    if not ref or not ref.startswith("#/"):
        return schema
    node = document
    for segment in ref.removeprefix("#/").split("/"):
        node = node.get(segment, {})
    return node


def _operation_schemas(document: dict) -> dict[str, tuple[list[str], list[str]]]:
    """Every operation's request and response property names, by `operationId`."""
    schemas: dict[str, tuple[list[str], list[str]]] = {}
    for methods in document.get("paths", {}).values():
        for operation in methods.values():
            if not isinstance(operation, dict) or "operationId" not in operation:
                continue
            body = (operation.get("requestBody", {}).get("content", {})
                    .get(_REQUEST_MEDIA, {}).get("schema", {}))
            request = sorted(_resolve(document, body).get("properties", {}))

            ok = (operation.get("responses", {}).get("200", {}).get("content", {})
                  .get(_RESPONSE_MEDIA, {}).get("schema", {}))
            response = sorted(_resolve(document, ok).get("properties", {}))
            schemas[operation["operationId"]] = (request, response)
    return schemas


def _index(name: str, dsn: str):
    """Index one materialised checkout and return its call sites, grouped by operation."""
    root = CORPUS / name
    vendor = load_vendor("stripe", VendorContext(
        cache_dir=CACHE, from_version=FROM_VERSION, to_version=TO_VERSION))
    store = GraphStore(dsn)
    store.apply_schema()
    store.truncate_all()

    repo = RepoRef(repo_id=f"corpus:{name}", url=str(root),
                   local_path=str(root), head_sha="0" * 40)
    adapter = select_language_adapter(repo, vendor)

    by_operation = defaultdict(list)
    for site in adapter.index(repo):
        by_operation[site.operation_id].append(site)
    return by_operation


def _read_fields(sources_root: Path) -> set[str]:
    """Every identifier any source in the tree reads off a member expression.

    Deliberately coarse. `_already_depends` asks the precise question per call site, and this
    only has to avoid proposing a response field the repository mentions anywhere -- a field
    chosen wrongly makes the specification unscoreable rather than merely awkward.
    """
    seen: set[str] = set()
    for path in sorted(sources_root.rglob("*.ts")):
        for token in path.read_text(encoding="utf-8").replace("\n", " ").split("."):
            head = "".join(c for c in token[:64] if c.isalnum() or c == "_")
            if head:
                seen.add(head)
    return seen


def build(dsn: str) -> list[Path]:
    entries = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    document = json.loads((CACHE / f"{TO_VERSION}.json").read_text(encoding="utf-8"))
    schemas = _operation_schemas(document)

    SPECS.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for entry in entries:
        name = entry["name"]
        by_operation = _index(name, dsn)

        candidates = [
            (operation, sites) for operation, sites in by_operation.items()
            if operation and any(site.args_keys for site in sites)
        ]
        candidates.sort(key=lambda item: (-len(item[1]), item[0]))
        chosen = candidates[:OPERATIONS_PER_REPOSITORY]

        passed = {key.split(".")[0] for sites in by_operation.values()
                  for site in sites for key in site.args_keys or ()}
        read = _read_fields(CORPUS / name)

        for operation, sites in chosen:
            request_properties, response_properties = schemas.get(operation, ([], []))
            for kind in KINDS:
                available = request_properties if kind.startswith("request") else response_properties
                taken = passed if kind.startswith("request") else read
                field = next((p for p in available if p not in taken), None)
                if field is None:
                    print(f"{name}/{operation}/{kind}: no unused property; skipped")
                    continue

                spec = {
                    "repo": (CORPUS / name).as_posix(),
                    "vendor": "stripe",
                    "cache": CACHE.as_posix(),
                    "from_version": FROM_VERSION,
                    "to_version": TO_VERSION,
                    "change": {"kind": kind, "operation": operation, "field": field},
                }
                path = SPECS / f"{name}-{operation}-{kind}.yaml"
                path.write_text(
                    f"# {len(sites)} indexed call site(s) on {operation} in {name}, pinned at "
                    f"{entry['commit']}.\n"
                    f"# Field chosen by the rule in scripts/build_corpus_specs.py: the "
                    f"alphabetically first\n# property of this operation in {TO_VERSION} that no "
                    f"call site in this repository already uses.\n"
                    + yaml.safe_dump(spec, sort_keys=True),
                    encoding="utf-8",
                )
                written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dsn", required=True, help="a database to index into; it is truncated")
    args = parser.parse_args()

    for path in build(args.dsn):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
