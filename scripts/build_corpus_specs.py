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
  - **Which kinds.** `request-property-removed` and `response-property-removed`, which are the
    two mechanically different inversions `sync.benchmark.mutate` implements. The third supported
    kind, `request-parameter-removed`, mutates identically to the first and would add pairs
    without adding information.
  - **Which operations.** Per repository *and per kind*, the two operations with the most indexed
    call sites where at least one site carries a non-empty field list **on the side that kind's
    change is judged on** -- `args_keys` for a request change, `response_fields_read` for a
    response one -- ties broken by operation id ascending.

    Per kind, because the two mutations need different things and asking one question for both
    answered it wrong in both directions. A request-property mutation needs a call passing an
    object argument, so `stripe.customers.retrieve(id)` has nowhere to put a property and must
    not acquire a request pair. A response-property mutation needs a call binding a result
    something reads a field off, and that operation was excluded for the wrong reason: the rule
    asked the request question of it. `virtual-lab-GetProductsId` is the pair that cost --
    three positional `client.products.retrieve(cfg.product_id)` calls, two of them reading
    fields off the result, unproposable and written by hand.
  - **Which field.** The alphabetically first property of that operation in the pinned
    specification that no indexed call site in the repository already passes, for a request
    change, or already reads, for a response change. Real properties of the real operation, so
    the mutation writes something the vendor could actually have removed; alphabetically first
    so the choice is not a judgement.
  - **Which site is held back.** The first call site on the changed operation by position, when
    the operation has more than one and that site carries a non-empty field list on the side the
    change is on. One per specification and never more. `hold_back` below carries why each
    clause is there.

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
    return by_operation, adapter.language_id


def _judged_by(site, kind: str) -> list[str]:
    """The field list `VendorChangeDetector.scan` judges this call site on, for this kind.

    One function because two clauses need the same answer and had drifted apart: the hold-back
    already followed the side the change is on, and the selection above it did not.
    """
    return site.args_keys if kind.startswith("request-") else site.response_fields_read


def operations_for(by_operation: dict, kind: str, limit: int = OPERATIONS_PER_REPOSITORY):
    """The operations this repository contributes a pair of `kind` over, most call sites first.

    An operation qualifies on the field list the change's own side is judged on, and the two
    sides are asked separately. The rule used to ask one question for both: the operations with
    the most call sites where at least one passes an object argument, then a request pair and a
    response pair over each. That condition is request-side, so response coverage was a side
    effect of request coverage -- every response pair the corpus holds is there because its
    operation also happened to qualify on the other side.

    `virtual-lab-GetProductsId` is what that cost and why this changed. Three call sites, all
    `client.products.retrieve(cfg.product_id)`, so `args_keys` is empty at every one and no
    number of them could make it a candidate; two of the three read fields off the result, which
    is everything a response pair needs. It is the strongest pair in the corpus and it had to be
    written by hand.

    **Per side rather than either side.** Qualifying an operation on evidence from the other half
    and then generating both kinds is the defect running the other way: a request pair over calls
    passing no object argument has nowhere to write the mutation, so every target comes back
    unreachable and the pair contributes no positive while still moving `pairs_scored` and its
    floor. The cap is therefore per kind, which leaves the ceiling where it was -- two operations
    times two kinds -- while letting the four slots fall on up to four different operations.

    **Non-empty rather than "the result is bound".** A bound result the repository reads nothing
    off is a site the response mutation could still attach a guard to, so this is the stricter
    of the two available readings. It is the one that can be asked: `CallSite` records the fields
    read and not whether a name received the call, and the alternative -- asking
    `sync.benchmark.mutate` which sites it can break -- would make the corpus select exactly what
    the generator can currently mutate. A generator regression would then shrink the corpus
    silently instead of arriving as the refused pairs `score_corpus.py` counts and names.
    """
    candidates = [
        (operation, sites) for operation, sites in by_operation.items()
        if operation and any(_judged_by(site, kind) for site in sites)
    ]
    # Most call sites first, because a pair over one site has the least room to hide a miss;
    # ties by operation id ascending, so the choice is not the dictionary's insertion order.
    candidates.sort(key=lambda item: (-len(item[1]), item[0]))
    return candidates[:limit]


def hold_back(sites: list, kind: str) -> list[dict]:
    """The call sites this specification declares held out of the mutation, as positions.

    A corpus that breaks every site on the changed operation gives binding precision nothing to
    be wrong about: every same-operation site is either broken and labelled affected, or a target
    the mutation could not reach, and neither can produce a false positive.
    `2026-07-29-precision-has-no-negative-to-fail-on.md` measured that as zero candidates in all
    ten scored pairs. A site held back is never edited, so it is unaffected by construction, and
    it is still a site the detector reaches -- which is the negative the axis needs.

    **One, never more.** Every held-back site is a site recall no longer measures, and recall is
    the only genuine quality measurement this benchmark currently has.

    **The first by position.** Every insertion `mutate.py` makes lands at or after the call it
    breaks, and `upsert_call_site` keys a call site's identity on its position -- so the earliest
    site on the operation is the only one guaranteed to still be where this file says once its
    siblings have been mutated. `furever-GetCharges` is the pair that shows what the other choice
    costs: a response guard inserted above three later calls displaced all three labels and the
    whole pair left the score.

    **Only when its field list is non-empty on the side the change is on.** That is the branch
    `VendorChangeDetector.scan` takes, and `_deepest_match` over an empty list returns None for
    every change there has ever been -- so such a site is a negative nobody asked, costing a
    positive and buying no candidate.

    **Only when the operation has more than one.** Holding back the only site leaves the mutation
    no target, and a pair with no target is refused rather than scored.
    """
    if len(sites) < 2:
        return []
    first = min(sites, key=lambda site: (site.path, site.line, site.col))
    if not _judged_by(first, kind):
        return []
    return [{"path": first.path, "line": first.line, "col": first.col}]


# Which files this scan reads, by the language the adapter indexes the repository in. A
# repository is scanned in its own language and in no other: `furever` carries one `.py` script
# mentioning `amount` fifteen times, so a scan over both suffixes would move a TypeScript
# specification's chosen field -- a frozen pair changing because a Python repository was added
# somewhere else in the manifest.
_SOURCE_SUFFIXES = {"typescript": ("*.ts",), "python": ("*.py",)}


def _read_fields(sources_root: Path, language: str) -> set[str]:
    """Every identifier any source in the tree reads off a member expression.

    Deliberately coarse. `_already_depends` asks the precise question per call site, and this
    only has to avoid proposing a response field the repository mentions anywhere -- a field
    chosen wrongly makes the specification unscoreable rather than merely awkward.

    Coarse is not the same as blind. Scanning a Python repository for `*.ts` reads nothing at
    all, which is not a loose guard but an absent one: every response property would be
    available and the alphabetically first would be chosen however heavily the repository uses
    it.
    """
    seen: set[str] = set()
    patterns = _SOURCE_SUFFIXES[language]
    for path in sorted(p for pattern in patterns for p in sources_root.rglob(pattern)):
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
        by_operation, language = _index(name, dsn)

        passed = {key.split(".")[0] for sites in by_operation.values()
                  for site in sites for key in site.args_keys or ()}
        read = _read_fields(CORPUS / name, language)

        # Kind first, because the candidate set is now a property of the kind rather than one
        # list both kinds are taken over.
        for kind in KINDS:
            for operation, sites in operations_for(by_operation, kind):
                request_properties, response_properties = schemas.get(operation, ([], []))
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
                held = hold_back(sites, kind)
                # Written only when the rule selected one, so a specification the rule passed
                # over stays byte-identical to what it was before the rule existed.
                if held:
                    spec["hold_back"] = held

                header = (
                    f"# {len(sites)} indexed call site(s) on {operation} in {name}, pinned at "
                    f"{entry['commit']}.\n"
                    f"# Field chosen by the rule in scripts/build_corpus_specs.py: the "
                    f"alphabetically first\n# property of this operation in {TO_VERSION} that no "
                    f"call site in this repository already uses.\n"
                )
                if held:
                    header += (
                        "# Held back from targets by the rule in the same script: the first call "
                        "site on this\n# operation by position, which the mutation therefore "
                        "never edits. It is the negative\n# binding precision is measured "
                        "against, and a site binding recall no longer measures.\n"
                    )

                path = SPECS / f"{name}-{operation}-{kind}.yaml"
                path.write_text(header + yaml.safe_dump(spec, sort_keys=True), encoding="utf-8")
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
